"""AppEEARS asynchronous workflow (submit -> poll -> ingest) with the HTTP client mocked."""
from app.earth_observation import modis_service, smap_service
from app.earth_observation.appeears import AppEEARSClient
from conftest import FARM, register


def test_appeears_submit_poll_ingest(client, monkeypatch):
    h = register(client, "appeears@example.com")
    farm = client.post("/api/farms", json=FARM, headers=h).json()
    submitted = []
    l3, qa, _, _ = smap_service.layers()
    ndvi, _, rel = modis_service.layers()
    csv_text = (f"ID,Latitude,Longitude,Date,{l3.column},{qa.column},{ndvi.column},{rel.column}\n"
                "farm,18.52,73.85,2025-07-01,0.33,0,0.71,0\n"
                "farm,18.52,73.85,2025-07-17,0.29,0,0.64,1\n")

    monkeypatch.setattr(AppEEARSClient, "configured", property(lambda self: True))
    monkeypatch.setattr(AppEEARSClient, "submit_point_task",
                        lambda self, name, layers, coords, start, end: submitted.append(name) or f"task-{len(submitted)}")
    state = {"status": "processing"}
    monkeypatch.setattr(AppEEARSClient, "task_status", lambda self, tid: state["status"])
    monkeypatch.setattr(AppEEARSClient, "bundle_csvs", lambda self, tid: {"results.csv": csv_text} if tid == "task-1" else {})

    r = client.post(f"/api/farms/{farm['id']}/earth-data/refresh", json={"datasets": ["smap", "modis", "srtm"]}, headers=h)
    st = {d["key"]: d for d in r.json()["datasets"]}
    assert st["smap"]["status"] == "pending" and st["srtm"]["status"] == "pending"
    assert len(submitted) == 2  # one time-series task, one terrain task

    st = {d["key"]: d for d in client.get(f"/api/farms/{farm['id']}/earth-data/status", headers=h).json()["datasets"]}
    assert st["smap"]["status"] == "processing"

    state["status"] = "done"
    ov = client.get(f"/api/farms/{farm['id']}/earth-data", headers=h).json()
    st = {d["key"]: d for d in ov["datasets"]}
    assert st["smap"]["status"] == "complete" and st["smap"]["record_count"] == 2
    assert st["modis"]["status"] == "complete"
    assert st["srtm"]["status"] == "no_data"  # empty bundle -> reported, not invented
    assert ov["profile"]["soil_moisture"]["surface"]["latest"] == 0.29
    assert ov["profile"]["is_demo"] is False
