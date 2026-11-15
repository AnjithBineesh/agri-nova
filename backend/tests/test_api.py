"""End-to-end API workflow, access control and data-provenance guarantees."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from conftest import FARM, register


def _farm(client, headers, **overrides):
    r = client.post("/api/farms", json={**FARM, **overrides}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_auth_flow_and_logout(client):
    h = register(client, "auth@example.com")
    assert client.get("/api/auth/me", headers=h).json()["role"] == "farmer"
    assert client.post("/api/auth/login", json={"email": "auth@example.com", "password": "wrongpass"}).status_code == 401
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_farm_boundary_vs_point(client):
    h = register(client, "geo@example.com")
    point = _farm(client, h)
    assert point["boundary_status"] == "none" and point["area_source"] is None
    poly = {"type": "Polygon", "coordinates": [[[73.85, 18.52], [73.852, 18.52], [73.852, 18.522], [73.85, 18.522]]]}
    drawn = _farm(client, h, boundary=poly)
    assert drawn["boundary_status"] == "user_drawn" and drawn["area_source"] == "computed_from_boundary"
    assert client.post("/api/farms", json={**FARM, "latitude": 95}, headers=h).status_code == 422


def test_rbac_farm_isolation_and_organisation_access(client):
    org_h = register(client, "officer@coop.org", role="organisation", org="Green Coop")
    member_h = register(client, "member@example.com", org="Green Coop")
    outsider_h = register(client, "outsider@example.com")
    farm = _farm(client, member_h)
    assert client.get(f"/api/farms/{farm['id']}", headers=outsider_h).status_code == 404
    seen = client.get(f"/api/farms/{farm['id']}", headers=org_h)
    assert seen.status_code == 200 and seen.json()["can_edit"] is False
    assert client.put(f"/api/farms/{farm['id']}", json=FARM, headers=org_h).status_code == 403
    assert client.get("/api/organisations/me/farms", headers=org_h).json()["farms"][0]["farm_id"] == farm["id"]
    assert client.get("/api/organisations/me/farms", headers=member_h).status_code == 403
    assert client.get("/api/research/model-assumptions", headers=member_h).status_code == 403


def test_nasa_failure_is_reported_not_faked(client):
    h = register(client, "nofake@example.com")
    farm = _farm(client, h)
    r = client.post(f"/api/farms/{farm['id']}/earth-data/refresh", json={"datasets": ["nasa_power", "gpm_imerg", "smap"]},
                    headers=h)
    st = {d["key"]: d for d in r.json()["datasets"]}
    assert st["nasa_power"]["status"] == "failed" and st["nasa_power"]["record_count"] == 0
    assert st["gpm_imerg"]["status"] == "not_configured"
    assert st["smap"]["status"] == "not_configured"
    assert st["era5"]["status"] == "not_integrated"
    overview = client.get(f"/api/farms/{farm['id']}/earth-data", headers=h).json()
    assert overview["profile"]["has_climate"] is False
    # planning endpoints refuse to run without climate data instead of inventing it
    assert client.post("/api/rotations/generate", json={"farm_id": farm["id"]}, headers=h).status_code == 409


def test_full_farmer_workflow_with_labelled_demo_data(client):
    h = register(client, "workflow@example.com")
    farm = _farm(client, h)
    fid = farm["id"]
    r = client.post(f"/api/farms/{fid}/soil", json={"ph": 7.6, "organic_carbon": 0.45, "nitrogen": 210,
                                                    "phosphorus": 14, "potassium": 320, "soil_texture": "clay loam",
                                                    "value_status": {"ph": "measured", "organic_carbon": "estimated"}},
                    headers=h)
    assert r.status_code == 201 and r.json()["profile"]["value_status"]["organic_carbon"] == "estimated"

    demo = client.post(f"/api/farms/{fid}/earth-data/demo", headers=h).json()
    assert "nasa_power" in demo["loaded"]
    ov = client.get(f"/api/farms/{fid}/earth-data", headers=h).json()
    assert ov["profile"]["is_demo"] is True
    power = next(d for d in ov["datasets"] if d["key"] == "nasa_power")
    assert power["status"] == "demonstration" and power["is_demo"] is True
    rain = client.get(f"/api/farms/{fid}/earth-data/rainfall", headers=h).json()
    assert all(m["is_demo"] for m in rain["gpm_imerg_monthly"])

    suit = client.post("/api/crops/suitability", json={"farm_id": fid}, headers=h).json()
    assert suit["is_demo_basis"] is True and len(suit["results"]) == 2 * 25
    assert {r["class"] for r in suit["results"]} <= {"suitable", "moderately_suitable", "unsuitable",
                                                     "insufficient_data"}

    gen = client.post("/api/rotations/generate", json={"farm_id": fid}, headers=h).json()
    keys = [s["key"] for s in gen["strategies"]]
    assert len(gen["strategies"]) >= 3 and "existing" in keys
    assert sum(gen["priority_weights"].values()) == 100
    assert gen["priority_weights"]["economic_potential"] == 0  # no prices -> not assessed
    assert any("DEMONSTRATION" in lim for lim in gen["strategies"][0]["explanation"]["limitations"])

    custom = client.post("/api/rotations/generate", json={
        "farm_id": fid, "mode": "custom",
        "priorities": {"soil_health": 40, "water_conservation": 25, "climate_resilience": 20, "economic_potential": 10,
                       "crop_diversity": 5},
        "economics": {"maize": {"price_per_t": 220, "cost_per_ha": 400}},
        "custom_rotation": [{"crop": "maize"}, {"crop": "chickpea"}]}, headers=h)
    assert custom.status_code == 200
    assert custom.json()["priority_weights"]["soil_health"] == 40
    assert any(s["key"] == "custom" for s in custom.json()["strategies"])

    sid = gen["strategies"][1]["id"]
    sim = client.post("/api/simulations", json={"farm_id": fid, "strategy_id": sid, "planning_horizon": "five_year",
                                                "scenario": {"preset": "hot_dry"}}, headers=h)
    assert sim.status_code == 201
    body = sim.json()
    assert body["results"]["summary"]["seasons_simulated"] == 10 and body["assumptions"]["climate"]
    assert client.get(f"/api/simulations/{body['id']}", headers=h).status_code == 200

    cmp_ = client.post("/api/simulations/compare", json={
        "farm_id": fid, "rotations": [{"name": "A", "rotation": [{"crop": "maize"}, {"crop": "maize"}]},
                                      {"name": "B", "rotation": [{"crop": "maize"}, {"crop": "chickpea"}]}]},
        headers=h).json()
    assert cmp_["comparison"]["table"] and "A" in cmp_["simulations"]
    bad = client.post("/api/simulations/compare", json={"farm_id": fid, "rotations": [
        {"name": "X", "rotation": [{"crop": "unobtainium"}]}]}, headers=h)
    assert bad.status_code == 422

    for kind in ("farmer", "scientific"):
        rep = client.post("/api/reports/generate", json={"farm_id": fid, "report_type": kind}, headers=h)
        assert rep.status_code == 201
        pdf = client.get(rep.json()["download_url"], headers=h)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # demonstration data can be removed again
    client.delete(f"/api/farms/{fid}/earth-data/demo", headers=h)
    assert client.get(f"/api/farms/{fid}/earth-data", headers=h).json()["profile"]["has_climate"] is False


def test_soil_report_upload_requires_confirmation(client):
    h = register(client, "upload@example.com")
    farm = _farm(client, h)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i, line in enumerate(["Regional Soil Testing Laboratory", "Report date: 10/01/2024", "pH 6.8",
                              "Organic Carbon 0.71 %", "Available Nitrogen 300 kg/ha",
                              "Available Phosphorus (Olsen) 21 kg/ha", "Available Potassium 250 kg/ha",
                              "Texture: Loam"]):
        c.drawString(72, 780 - i * 18, line)
    c.save()
    r = client.post(f"/api/farms/{farm['id']}/soil/upload", files={"file": ("report.pdf", buf.getvalue(), "application/pdf")},
                    headers=h)
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["verification_status"] == "pending" and rep["extraction_method"] == "pdf_text"
    assert rep["extracted_values"]["parameters"]["ph"]["value"] == 6.8
    # Unconfirmed OCR values are not a soil profile yet
    assert client.get(f"/api/farms/{farm['id']}/soil", headers=h).json()["latest"] is None
    conf = client.post(f"/api/soil/{rep['id']}/confirm", json={"ph": 6.8, "organic_carbon": 0.71,
                                                               "soil_texture": "loam"}, headers=h)
    assert conf.status_code == 200 and conf.json()["profile"]["data_source"] == "lab_report_confirmed"
    assert client.post(f"/api/soil/{rep['id']}/confirm", json={"ph": 6.8}, headers=h).status_code == 409
    bad = client.post(f"/api/farms/{farm['id']}/soil/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")},
                      headers=h)
    assert bad.status_code == 415
    assert client.get(f"/api/soil/{rep['id']}/file", headers=h).content.startswith(b"%PDF")


def test_weather_this_year_endpoint(client):
    h = register(client, "weather@example.com")
    farm = _farm(client, h)
    assert client.get(f"/api/farms/{farm['id']}/earth-data/weather", headers=h).json()["available"] is False
    client.post(f"/api/farms/{farm['id']}/earth-data/demo", headers=h)
    w = client.get(f"/api/farms/{farm['id']}/earth-data/weather", headers=h).json()
    assert w["available"] and w["is_demo"] and w["days"] and w["rain_percent_of_normal"] is not None
    # preview endpoint reports NASA being unreachable (tests never call NASA) instead of inventing data
    r = client.get("/api/power/preview?latitude=18.5&longitude=73.8", headers=h)
    assert r.status_code == 502
