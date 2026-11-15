"""Adapter parsing tests using response shapes of the real services (no network)."""
from datetime import date

from app.earth_observation import landsat_service, modis_service, smap_service, srtm_service
from app.earth_observation.base import DataType
from app.earth_observation.gpm_service import parse_giovanni_csv
from app.earth_observation.hls_common import fmask_clear
from app.earth_observation.nasa_power_service import parse_power_response
from app.soil_processing.parser import parse_report

POWER_MONTHLY = {
    "type": "Feature", "geometry": {"type": "Point", "coordinates": [73.85, 18.52, 560.0]},
    "properties": {"parameter": {
        "T2M": {"202301": 22.1, "202302": 24.0, "202313": 26.0},
        "PRECTOTCORR": {"202301": 0.5, "202302": -999.0, "202313": 2.9},
    }},
    "header": {"fill_value": -999.0},
    "parameters": {"T2M": {"units": "C"}, "PRECTOTCORR": {"units": "mm/day"}},
}


def test_power_monthly_parse_converts_rate_and_flags_fill():
    recs = parse_power_response(POWER_MONTHLY, "monthly", 18.52, 73.85, "https://power.larc.nasa.gov/x")
    t = [r for r in recs if r.variable == "T2M"]
    assert len(t) == 2  # annual (month 13) value skipped
    jan = next(r for r in recs if r.variable == "PRECTOTCORR" and r.observation_date == date(2023, 1, 1))
    assert jan.unit == "mm/month" and abs(jan.value - 0.5 * 31) < 1e-9
    feb = next(r for r in recs if r.variable == "PRECTOTCORR" and r.observation_date == date(2023, 2, 1))
    assert feb.value is None and feb.quality == "missing"
    assert all(r.data_type == DataType.WEATHER_CLIMATE_ESTIMATE for r in recs)


def test_giovanni_csv_parse():
    text = ("prod_name=GPM_3IMERGDF_07\nparam_short_name=precipitation\nunit=mm/day\nfill_value=-9999.9\n\n"
            "Timestamp (UTC),Data\n2023-01-01T00:00:00,1.25\n2023-01-02T00:00:00,-9999.9\n")
    meta, rows = parse_giovanni_csv(text)
    assert meta["unit"] == "mm/day"
    assert rows == [(date(2023, 1, 1), 1.25), (date(2023, 1, 2), None)]


def _row(d, **cols):
    return {"ID": "farm", "Date": d, **cols}


def test_smap_parser_quality_and_l4_daily_mean():
    l3, qa, l4s, l4r = smap_service.layers()
    rows = [_row("2024-06-01", **{l3.column: "0.31", qa.column: "0", l4s.column: "0.30", l4r.column: "0.25"}),
            _row("2024-06-01", **{l3.column: "-9999", qa.column: "1", l4s.column: "0.32", l4r.column: "0.27"})]
    recs = smap_service.parse(rows, 18.5, 73.8, "u")
    surface = [r for r in recs if r.variable == "surface_soil_moisture"]
    assert len(surface) == 1 and surface[0].quality == "recommended"
    root = next(r for r in recs if r.variable == "rootzone_soil_moisture")
    assert abs(root.value - 0.26) < 1e-9 and root.data_type == DataType.MODEL_ESTIMATE


def test_modis_parser_excludes_cloudy():
    ndvi, evi, rel = modis_service.layers()
    rows = [_row("2024-01-01", **{ndvi.column: "6500", evi.column: "4000", rel.column: "0"}),
            _row("2024-01-17", **{ndvi.column: "0.2", evi.column: "0.1", rel.column: "3"})]
    recs = modis_service.parse(rows, 0, 0, "u")
    assert [r.value for r in recs if r.variable == "ndvi"] == [0.65]


def test_hls_ndvi_and_fmask():
    assert fmask_clear(0) and fmask_clear(64)  # aerosol bits only
    assert not fmask_clear(2) and not fmask_clear(8)
    red, nir, fm = landsat_service.layers()
    rows = [_row("2024-03-03", **{red.column: "0.05", nir.column: "0.35", fm.column: "64"}),
            _row("2024-03-19", **{red.column: "0.05", nir.column: "0.35", fm.column: "2"})]
    recs = landsat_service.parse(rows, 0, 0, "u")
    assert len(recs) == 1 and abs(recs[0].value - 0.75) < 1e-4


def test_srtm_slope_from_grid():
    lyr = srtm_service.layers()[0]
    coords = srtm_service.grid_coordinates(10.0, 76.0)
    rows = [{"ID": c["id"], "Date": "2000-02-11", lyr.column: str(100 + int(c["id"][2]) * 3)} for c in coords]
    recs = {r.variable: r for r in srtm_service.parse(rows, 10.0, 76.0, "u")}
    assert recs["elevation"].value == 103
    assert 5 < recs["slope"].value < 7


def test_soil_report_parser():
    text = ("Soil Testing Laboratory\nDate of report: 05/02/2024\npH 6.4\nOrganic Carbon 0.62 %\n"
            "Available Nitrogen 245 kg/ha\nAvailable Phosphorus (Olsen) 18 kg/ha\nAvailable Potassium 190 kg/ha\n"
            "Texture: Clay Loam")
    out = parse_report(text)
    p = out["parameters"]
    assert p["ph"]["value"] == 6.4 and p["organic_carbon"]["value"] == 0.62
    assert p["nitrogen"]["unit"] == "kg/ha" and p["phosphorus"]["method"] == "olsen"
    assert p["soil_texture"]["value"] == "clay loam" and out["report_date"] == "2024-02-05"


def test_daily_power_request_matches_reference(monkeypatch):
    """The daily call uses the reference parameter set, AG community, JSON and the UTC time standard."""
    from datetime import datetime, timezone

    import httpx

    from app.database import SessionLocal, init_db
    from app.earth_observation import nasa_power_service

    captured = {}

    def fake_request(method, url, **kw):
        captured.update(url=url, params=kw["params"])
        return httpx.Response(200, json={"properties": {"parameter": {"T2M": {"20260101": 21.0}}},
                                         "header": {"fill_value": -999}, "parameters": {"T2M": {"units": "C"}}})

    monkeypatch.setattr(nasa_power_service, "request_with_retries", fake_request)
    init_db()
    with SessionLocal() as db:
        data, url = nasa_power_service.fetch_nasa_power(db, 18.52, 73.85)
    p = captured["params"]
    assert captured["url"].endswith("/temporal/daily/point")
    assert p["parameters"] == "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M"
    assert p["community"] == "AG" and p["format"] == "JSON" and p["time-standard"] == "UTC"
    today = datetime.now(timezone.utc).date()
    assert p["start"] == f"{today.year}0101" and p["end"] == today.strftime("%Y%m%d")
    assert "time-standard=UTC" in url and data["properties"]["parameter"]["T2M"]["20260101"] == 21.0


def test_weather_summary_against_normal():
    from datetime import date

    from app.agriculture.weather_summary import summarise

    daily = {date(2026, 1, d): {"T2M": 22.0, "T2M_MAX": 36.0 if d == 5 else 30.0, "T2M_MIN": 14.0,
                                "PRECTOTCORR": 5.0 if d in (1, 2) else 0.0} for d in range(1, 11)}
    daily[date(2026, 1, 11)] = {"T2M": None, "T2M_MAX": None, "T2M_MIN": None, "PRECTOTCORR": None}
    clim = [{"precip_mm": 31.0, "t_mean": 21.0}] * 12
    s = summarise(daily, clim, date(2026, 1, 12))
    assert s["rain_total_mm"] == 10.0 and s["rain_normal_mm"] == 10.0 and s["rain_percent_of_normal"] == 100
    assert s["last_day"] == "2026-01-10" and s["days_pending"] == 2
    assert s["hot_days"] == 1 and s["longest_dry_spell_days"] == 8 and s["temp_anomaly_c"] == 1.0
