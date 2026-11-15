"""Unit tests for the scientific building blocks against published reference values."""
import math

from app.agriculture.et0 import effective_rainfall_monthly, extraterrestrial_radiation, hargreaves, penman_monteith
from app.agriculture.soil_analyser import assess, ph_class, to_kg_ha
from app.earth_observation.srtm_service import horn_slope_deg
from app.recommendation_engine.crop_suitability import trapezoid
from app.recommendation_engine.priority_scoring import normalise_weights
from app.simulation import organic_matter_model as som
from app.simulation.water_balance import kc_for_day
from app.utils.geo import polygon_area_ha


def test_extraterrestrial_radiation_fao56_example8():
    # FAO-56 Example 8: 20°S on 3 September -> Ra = 32.2 MJ m-2 day-1
    assert abs(extraterrestrial_radiation(-20.0, 246) - 32.2) < 0.3


def test_penman_monteith_fao56_example18():
    # FAO-56 Example 18 (Brussels, 6 July): ET0 = 3.9 mm/day
    es = (0.6108 * math.exp(17.27 * 21.5 / (21.5 + 237.3)) + 0.6108 * math.exp(17.27 * 12.3 / (12.3 + 237.3))) / 2
    rh_mean = 1.409 / es * 100
    et0 = penman_monteith(21.5, 12.3, rh_mean, 2.078, 22.07, 50.8, 187, elevation_m=100)
    assert abs(et0 - 3.9) < 0.25


def test_hargreaves_positive_and_monotonic():
    ra = extraterrestrial_radiation(18.5, 135)
    assert 0 < hargreaves(25, 32, 18, ra) < hargreaves(30, 37, 23, ra)


def test_effective_rainfall_formula():
    assert effective_rainfall_monthly(100) == 55.0
    assert effective_rainfall_monthly(50) == 20.0
    assert effective_rainfall_monthly(10) == 0.0


def test_polygon_area():
    # ~0.002° x 0.002° at 18.5°N ≈ 222 m x 211 m ≈ 4.7 ha
    poly = {"type": "Polygon", "coordinates": [[[73.85, 18.52], [73.852, 18.52], [73.852, 18.522], [73.85, 18.522],
                                                [73.85, 18.52]]]}
    assert 4.5 < polygon_area_ha(poly) < 4.9


def test_trapezoid_membership():
    r = {"absolute_min": 10, "optimal_min": 20, "optimal_max": 30, "absolute_max": 40}
    assert trapezoid(25, r) == 1.0
    assert trapezoid(15, r) == 0.5
    assert trapezoid(10, r) == 0.0
    assert trapezoid(45, r) == 0.0


def test_horn_slope_flat_and_tilted():
    assert horn_slope_deg([[100] * 3] * 3, 30, 30) == 0
    tilted = [[100, 103, 106], [100, 103, 106], [100, 103, 106]]
    assert abs(horn_slope_deg(tilted, 30, 30) - math.degrees(math.atan(0.1))) < 0.01


def test_weights_always_sum_to_100():
    for w in ({"soil_health": 1, "water_conservation": 1, "climate_resilience": 1},
              {"soil_health": 33.3, "crop_diversity": 66.7}, {}):
        n = normalise_weights(w)
        assert sum(n.values()) == 100


def test_kc_curve():
    kc = {"ini": 0.3, "mid": 1.2, "end": 0.5}
    assert kc_for_day(0, 100, kc) == 0.3
    assert kc_for_day(50, 100, kc) == 1.2
    assert abs(kc_for_day(99, 100, kc) - 0.5) < 0.05


def test_soc_step_decays_without_inputs_and_grows_with_inputs():
    zero = {"above_c": 0, "root_c": 0}
    assert som.step(30, zero, 25, 0.5) < 30
    assert som.step(30, {"above_c": 3, "root_c": 1}, 25, 0.5) > 30


def test_soil_assessment_ratings():
    assert ph_class(7.0) == "neutral"
    assert ph_class(5.2) == "strongly acid"
    assert abs(to_kg_ha(10, "mg/kg") - 22.4) < 1e-9
    a = assess({"ph": 5.0, "organic_carbon": 0.4, "nitrogen": 200, "soil_texture": "sandy loam"})
    assert "Soil acidity" in a["limitations"] and "Low organic carbon" in a["limitations"]
    assert "single universal soil health score" in a["methodology"]
    assert assess(None)["available"] is False
