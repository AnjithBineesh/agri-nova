"""Machine-learning models: quality, explanations, robustness and API integration."""
from app.ml import predictor
from app.ml.features import WEATHER_REFERENCE, monthly_climatology, read_daily_weather_csv, season_features
from conftest import FARM, register

RICE_LIKE = {"N": 80, "P": 45, "K": 40, "temperature": 23.5, "humidity": 82, "ph": 6.5, "rainfall": 230}


def test_model_card_quality_and_honest_yield_verdict():
    card = predictor.model_card()
    assert card["crop_model"]["test_split"]["accuracy"] >= 0.95
    assert card["soil_model"]["test_split"]["accuracy"] >= 0.85
    assert len(card["crop_model"]["algorithm_comparison"]) >= 5
    assert card["yield_dataset"]["deployed"] is False and card["yield_dataset"]["best_cv_r2"] < 0.1
    assert card["weather_reference"]["examples"] and card["limitations"]


def test_prediction_is_explained_and_ranked():
    res = predictor.predict("crop_model", RICE_LIKE)
    top = res["predictions"][0]
    assert top["crop"] == "rice" and top["crop_db_slug"] == "rice"
    probs = [p["probability"] for p in res["predictions"]]
    assert probs == sorted(probs, reverse=True) and abs(sum(predictor.probability_for("crop_model", RICE_LIKE).values()) - 1) < 1e-6
    assert len(top["checks"]) == 7 and top["checks"][0]["status"] in ("typical", "below", "above")
    assert res["out_of_range"] == []


def test_out_of_range_inputs_are_flagged():
    res = predictor.predict("crop_model", {**RICE_LIKE, "rainfall": 900, "N": 400})
    flagged = {w["feature"] for w in res["out_of_range"]}
    assert {"rainfall", "N"} <= flagged and res["confidence"] != "high"


def test_weather_file_to_season_features():
    daily = read_daily_weather_csv(WEATHER_REFERENCE)
    assert len(daily) >= 2190 and daily["temperature"].notna().mean() > 0.99
    clim = monthly_climatology(daily)
    rows = [{"t_mean": r.temperature, "rh": r.humidity, "precip_mm": r.rainfall} for _, r in clim.iterrows()]
    f = season_features(rows, 6, 10)
    assert 24 < f["temperature"] < 30 and f["humidity"] > 80 and f["rainfall"] > 200  # Kerala monsoon


def test_prediction_api_and_farm_integration(client):
    h = register(client, "ml@example.com")
    r = client.post("/api/predict/crop", json=RICE_LIKE, headers=h)
    assert r.status_code == 200 and r.json()["predictions"][0]["name"] == "Rice"
    assert client.post("/api/predict/crop", json={**RICE_LIKE, "ph": 15}, headers=h).status_code == 422
    soil = {"N": 140, "P": 50, "K": 160, "ph": 6.1, "EC": 0.8, "S": 0.2, "Cu": 17, "Fe": 110, "Mn": 70, "Zn": 32, "B": 25}
    assert client.post("/api/predict/soil", json=soil, headers=h).json()["predictions"]
    info = client.get("/api/predict/models", headers=h).json()
    assert "profiles" not in info["crop_model"] and info["crop_model"]["selected_algorithm"]

    farm = client.post("/api/farms", json=FARM, headers=h).json()
    pre = client.get(f"/api/predict/farm/{farm['id']}/inputs", headers=h).json()
    assert pre["seasons"][0]["complete"] is False and pre["notes"]
    client.post(f"/api/farms/{farm['id']}/earth-data/demo", headers=h)
    client.post(f"/api/farms/{farm['id']}/soil", json={"ph": 6.8, "nitrogen": 90, "phosphorus": 40, "potassium": 45,
                                                       "soil_texture": "loam"}, headers=h)
    res = client.get(f"/api/predict/farm/{farm['id']}", headers=h).json()
    assert all(s["complete"] and s["result"]["predictions"] for s in res["seasons"])
    suit = client.post("/api/crops/suitability", json={"farm_id": farm["id"]}, headers=h).json()
    assert suit["ai_match"]["available"] is True
    assert any("ai_match" in r for r in suit["results"] if r["crop"] == "rice")
