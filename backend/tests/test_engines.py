"""Crop suitability, rotation rules and simulator behaviour."""
import json
from pathlib import Path

import pytest

from app.agriculture.climate_analyser import EnvironmentProfile
from app.recommendation_engine.crop_suitability import assess_crop
from app.recommendation_engine.rotation_rules import evaluate
from app.simulation.climate_scenarios import Scenario
from app.simulation.rotation_simulator import expand_rotation, simulate

CROPS = {c["slug"]: c for c in json.loads((Path(__file__).resolve().parent.parent / "app" / "agriculture" / "data" /
                                           "crops.json").read_text())["crops"]}
SEASONS = [{"name": "Wet", "start_month": 6, "end_month": 10}, {"name": "Dry", "start_month": 11, "end_month": 3}]


def profile(t_mean=26.0, rain=(5, 5, 10, 20, 60, 180, 250, 220, 150, 60, 15, 5)):
    p = EnvironmentProfile(farm_id=1, latitude=18.5, longitude=73.8)
    for m in range(12):
        p.monthly.append({"month": m + 1, "t_mean": t_mean, "t_max": t_mean + 6, "t_min": t_mean - 6,
                          "precip_mm": rain[m], "et0_mm": 130.0, "rh": 60, "solar": 18, "wind": 2})
    p.annual_precip_mean = sum(rain)
    p.annual_precip_cv = 0.2
    return p


def test_crop_database_has_sources_and_required_fields():
    assert len(CROPS) >= 20
    for c in CROPS.values():
        assert c["sources"] and c["climate_requirements"]["temperature_c"]["optimal_min"] is not None
        assert c["water_requirement"]["kc"]["mid"] > 0


def test_critical_constraint_overrides_high_score():
    hot = profile(t_mean=33.0)
    res = assess_crop(CROPS["wheat"], SEASONS[0], hot, {"ph": 6.5, "soil_texture": "loam"}, {"irrigation_type": "full"})
    assert res["class"] == "unsuitable"
    assert any("temperature" in c.lower() for c in res["critical_constraints"])


def test_missing_soil_reduces_completeness_not_invents_values():
    res = assess_crop(CROPS["maize"], SEASONS[0], profile(), None, {"irrigation_type": "none"})
    names = {f["name"]: f for f in res["factors"]}
    assert names["soil_ph"]["available"] is False and names["soil_ph"]["score"] is None
    assert res["data_completeness"] < 1


def test_paddy_rice_needs_water():
    dry = profile(rain=(0, 0, 0, 5, 10, 30, 60, 50, 30, 10, 0, 0))
    res = assess_crop(CROPS["rice"], SEASONS[0], dry, {"ph": 6.5}, {"irrigation_type": "none"})
    assert res["class"] == "unsuitable"


def test_rotation_rules_flag_monoculture_and_reward_legume():
    mono = evaluate(["maize", "maize", "maize"], CROPS)
    mixed = evaluate(["maize", "green_gram", "sorghum", "chickpea"], CROPS)
    assert any(f["rule"] == "repeated_crop" for f in mono["findings"])
    assert any(f["rule"] == "legume_inclusion" for f in mixed["findings"])
    assert mixed["rotation_health_index"] > mono["rotation_health_index"]
    solanaceae = evaluate(["tomato", "potato"], CROPS)
    assert any(f["rule"] == "same_family" for f in solanaceae["findings"])


def test_expand_rotation_handles_multi_season_crop():
    plan = expand_rotation([{"crop": "cotton", "span": 2}, {"crop": "maize", "span": 1}], 5)
    assert [p["crop"] for p in plan] == ["cotton", "cotton", "maize", "cotton", "cotton"]
    assert plan[1]["continuation"] and not plan[2]["continuation"]


def test_simulator_state_carries_between_seasons():
    farm = {"irrigation_type": "none", "residue_management": "retained"}
    soil = {"organic_carbon": 0.6, "soil_texture": "loam"}
    res = simulate([{"crop": "maize", "span": 1}, {"crop": "chickpea", "span": 1}], CROPS, profile(), soil, farm,
                   SEASONS, Scenario(), horizon_years=2)
    rows = [r for r in res["seasons"] if not r["continuation"]]
    assert len(rows) == 4
    cum = 0.0
    for r in rows:
        cum += r["n_balance_kg_ha"]
        assert r["n_balance_cum"] == pytest.approx(cum, abs=0.2)
    # chickpea leaves an N credit that the following maize uses
    assert rows[2]["n_credit_used_kg_ha"] > 0
    assert res["summary"]["soc_initial_t_ha"] == pytest.approx(0.6 * 1.35 * 30)
    assert "organic_carbon_model" in res["assumptions"] and "organic_carbon" not in res["assumptions"]


def test_warmer_scenario_increases_water_demand():
    farm = {"irrigation_type": "none", "residue_management": "partial"}
    base = simulate([{"crop": "maize", "span": 1}], CROPS, profile(), None, farm, SEASONS[:1], Scenario(), 1)
    hot = simulate([{"crop": "maize", "span": 1}], CROPS, profile(), None, farm, SEASONS[:1],
                   Scenario(temp_delta_c=2.0), 1)
    assert hot["summary"]["total_crop_water_mm"] > base["summary"]["total_crop_water_mm"]
    assert "No measured organic carbon" in base["assumptions"]["organic_carbon"]
