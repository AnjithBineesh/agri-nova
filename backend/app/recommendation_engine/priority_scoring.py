"""Farmer priority weights and multi-objective scoring of rotation strategies."""

OBJECTIVES = ("soil_health", "water_conservation", "climate_resilience", "economic_potential", "crop_diversity")
OBJECTIVE_LABELS = {
    "soil_health": "Soil health improvement", "water_conservation": "Water conservation",
    "climate_resilience": "Climate resilience", "economic_potential": "Economic potential",
    "crop_diversity": "Crop diversity",
}


def normalise_weights(w: dict) -> dict:
    """Integer percentages over the five objectives that always sum to 100."""
    raw = {k: max(0.0, float(w.get(k, 0) or 0)) for k in OBJECTIVES}
    total = sum(raw.values())
    if total <= 0:
        raw = {k: 1.0 for k in OBJECTIVES}
        total = 5.0
    scaled = {k: v * 100 / total for k, v in raw.items()}
    floors = {k: int(v) for k, v in scaled.items()}
    remainder = 100 - sum(floors.values())
    for k in sorted(OBJECTIVES, key=lambda k: scaled[k] - floors[k], reverse=True)[:remainder]:
        floors[k] += 1
    return floors


def automatic_weights(profile, soil_assessment: dict, farm: dict, economics_available: bool) -> tuple[dict, list[str]]:
    w = {k: 20.0 for k in OBJECTIVES}
    why = ["Start from equal weights (20% each)."]
    if not economics_available:
        w["economic_potential"] = 0
        why.append("Economic potential set to 0%: no local prices and costs were provided, so it cannot be "
                   "assessed reliably.")
    limits = soil_assessment.get("limitations", []) if soil_assessment else []
    if any("organic carbon" in lim.lower() or "nitrogen" in lim.lower() for lim in limits):
        w["soil_health"] += 15
        why.append("Soil health +15: soil test shows low organic carbon or nitrogen.")
    if profile.has_climate:
        rain_total = profile.annual_precip_mean or 0
        et0_total = sum(m["et0_mm"] or 0 for m in profile.monthly)
        if et0_total and rain_total / et0_total < 0.75 and farm.get("irrigation_type") != "full":
            w["water_conservation"] += 15
            why.append(f"Water conservation +15: annual rainfall ({rain_total:.0f} mm) is well below reference "
                       f"evapotranspiration ({et0_total:.0f} mm) and irrigation is limited.")
        if (profile.annual_precip_cv or 0) > 0.2 or (profile.temp_trend_c_per_decade or 0) > 0.2:
            w["climate_resilience"] += 10
            why.append("Climate resilience +10: high year-to-year rainfall variability or a warming trend in the "
                       "observed record.")
    else:
        why.append("No climate data: climate and water adjustments not applied.")
    return normalise_weights(w), why


def objective_scores(sim: dict, stress_sim: dict, rules: dict, gm_range: tuple[float, float] | None) -> dict:
    s, st = sim["summary"], stress_sim["summary"]
    soc0 = s["soc_initial_t_ha"] or 1
    d_soc = (s["soc_change_t_ha"] or {}).get("central", 0.0)
    soc_idx = min(1.0, max(0.0, 0.5 + d_soc / (0.05 * soc0 * 2)))
    n_per_season = s["n_balance_cum_kg_ha"] / max(1, s["seasons_simulated"])
    n_idx = min(1.0, max(0.0, 0.5 + n_per_season / 100))
    soil = 0.4 * soc_idx + 0.3 * n_idx + 0.3 * rules["rotation_health_index"]
    water = None
    if s["rainfed_supply_fraction"] is not None and s["total_crop_water_mm"]:
        water = 0.6 * min(1.0, s["rainfed_supply_fraction"]) + 0.4 * (1 - min(1.0, s["total_unmet_deficit_mm"] /
                                                                             s["total_crop_water_mm"]))
        water -= min(0.3, s["total_irrigation_need_mm"] / (s["total_crop_water_mm"] * 3))
        water = max(0.0, water)
    climate = None
    if st["mean_climate_vulnerability"] is not None:
        crit_share = st["critical_seasons"] / max(1, st["seasons_simulated"])
        climate = max(0.0, 1 - st["mean_climate_vulnerability"] - 0.5 * crit_share)
    econ = None
    if s["gross_margin_total"] is not None and gm_range:
        lo, hi = gm_range
        econ = 0.5 if hi == lo else (s["gross_margin_total"] - lo) / (hi - lo)
    diversity = 0.6 * min(1.0, s["family_count"] / 4) + 0.4 * min(1.0, s["shannon_diversity"] / 1.2)
    return {"soil_health": round(soil, 3), "water_conservation": None if water is None else round(water, 3),
            "climate_resilience": None if climate is None else round(climate, 3),
            "economic_potential": None if econ is None else round(econ, 3), "crop_diversity": round(diversity, 3)}


def composite(objectives: dict, weights: dict) -> tuple[float | None, list[str]]:
    notes = []
    used = {k: weights[k] for k in OBJECTIVES if objectives.get(k) is not None and weights.get(k, 0) > 0}
    missing = [OBJECTIVE_LABELS[k] for k in OBJECTIVES if objectives.get(k) is None and weights.get(k, 0) > 0]
    if missing:
        notes.append(f"Not assessable with available data (weight redistributed): {', '.join(missing)}.")
    total = sum(used.values())
    if not total:
        return None, notes
    return round(100 * sum(objectives[k] * w for k, w in used.items()) / total, 1), notes
