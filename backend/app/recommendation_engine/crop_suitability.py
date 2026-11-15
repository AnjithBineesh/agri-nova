"""Transparent, rule-based crop suitability assessment.

Score = Σ (factor score × weight) / Σ weights of factors with data, scaled to 0–100.
Factor scores use ECOCROP-style trapezoidal membership functions (1 inside the optimal range,
linear decline to 0 at the absolute limits). Any critical constraint makes a crop *unsuitable*
regardless of its weighted score.
"""
from ..agriculture.climate_analyser import EnvironmentProfile
from ..agriculture.soil_analyser import TEXTURE_GROUP, estimated_awc, to_kg_ha
from ..simulation.water_balance import irrigation_supply, season_water
from .seasons import season_label, season_length_months

DEFAULT_WEIGHTS = {
    "temperature": 0.25, "water": 0.20, "growing_season": 0.15, "rainfall": 0.10, "soil_ph": 0.10,
    "soil_texture_drainage": 0.10, "nutrients": 0.05, "salinity": 0.05,
}
SUITABLE, MODERATE = 70, 45


def trapezoid(x: float, r: dict) -> float:
    lo, olo, ohi, hi = r["absolute_min"], r["optimal_min"], r["optimal_max"], r["absolute_max"]
    if x <= lo or x >= hi:
        return 0.0
    if olo <= x <= ohi:
        return 1.0
    if x < olo:
        return (x - lo) / (olo - lo) if olo > lo else 1.0
    return (hi - x) / (hi - ohi) if hi > ohi else 1.0


def _factor(name, score, value, explanation, available=True, critical=None):
    return {"name": name, "score": None if score is None else round(score, 3), "value": value,
            "explanation": explanation, "available": available, "critical": critical}


def assess_crop(crop: dict, season: dict, profile: EnvironmentProfile, soil: dict | None, farm: dict,
                temp_delta: float = 0.0, rain_factor: float = 1.0, weights: dict | None = None) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    soil = soil or {}
    factors: list[dict] = []
    critical: list[str] = []
    months = profile.season_months(season["start_month"], season["end_month"])
    duration = crop["duration"]["typical_days"]
    crop_months = profile.season_months(season["start_month"],
                                        (season["start_month"] - 1 + max(1, round(duration / 30.4)) - 1) % 12 + 1)
    temp = crop["climate_requirements"]["temperature_c"]

    # 1. Temperature over the crop's months
    stats = profile.season_stats(crop_months, temp_delta, rain_factor)
    if stats:
        month_scores = [trapezoid(profile.monthly[m - 1]["t_mean"] + temp_delta, temp) for m in crop_months]
        s = min(month_scores)
        coldest = min(profile.monthly[m - 1]["t_min"] for m in crop_months) + temp_delta
        hottest = max(profile.monthly[m - 1]["t_max"] for m in crop_months) + temp_delta
        expl = (f"Monthly mean temperature {min(profile.monthly[m - 1]['t_mean'] for m in crop_months) + temp_delta:.1f}–"
                f"{max(profile.monthly[m - 1]['t_mean'] for m in crop_months) + temp_delta:.1f} °C during the crop "
                f"period vs optimum {temp['optimal_min']:.0f}–{temp['optimal_max']:.0f} °C "
                f"(absolute {temp['absolute_min']:.0f}–{temp['absolute_max']:.0f} °C).")
        crit = None
        if s == 0:
            crit = "Mean monthly temperature outside the crop's absolute limits"
        kill = crop["climate_requirements"].get("killing_temperature_c")
        if kill is not None and coldest <= kill + 2:
            expl += f" Average monthly minimum {coldest:.1f} °C is close to the killing temperature ({kill:.0f} °C): frost risk."
            s *= 0.5
        heat = profile.heat_stress_fraction(crop_months, temp["absolute_max"], temp_delta)
        if heat is not None and heat > 0.1:
            expl += f" {heat * 100:.0f}% of recent days exceeded {temp['absolute_max']:.0f} °C (heat stress)."
            s *= 0.7 if heat < 0.3 else 0.4
        elif heat is None and hottest > temp["absolute_max"]:
            expl += f" Average monthly maximum reaches {hottest:.1f} °C, above the absolute maximum."
            s *= 0.7
        if crit:
            critical.append(crit)
        factors.append(_factor("temperature", s, round(stats["t_mean"], 1), expl, critical=crit))
    else:
        factors.append(_factor("temperature", None, None, "No climate data available", available=False))

    # 2. Annual rainfall vs ECOCROP range (adjusted by irrigation)
    irr = farm.get("irrigation_type", "none")
    rr = crop["climate_requirements"]["annual_rainfall_mm"]
    if profile.annual_precip_mean is not None:
        p = profile.annual_precip_mean * rain_factor
        s = trapezoid(p, rr)
        expl = (f"Mean annual rainfall {p:.0f} mm vs ECOCROP optimum {rr['optimal_min']:.0f}–{rr['optimal_max']:.0f} mm "
                f"(absolute {rr['absolute_min']:.0f}–{rr['absolute_max']:.0f} mm).")
        if p < rr["optimal_min"] and irr != "none":
            s = max(s, 1.0 if irr == "full" else 0.6)
            expl += f" Deficit side relaxed because {irr} irrigation is available."
        crit = None
        if p < rr["absolute_min"] and irr == "none":
            crit = "Annual rainfall below the crop's absolute minimum without irrigation"
            critical.append(crit)
        factors.append(_factor("rainfall", s, round(p), expl, critical=crit))
    else:
        factors.append(_factor("rainfall", None, None, "No rainfall data available", available=False))

    # 3. Seasonal water balance
    awc = soil.get("water_holding_capacity") or estimated_awc(soil.get("soil_texture") or farm.get("soil_type"))
    water = season_water(crop, profile.monthly, season["start_month"], temp_delta, rain_factor,
                         awc_mm_per_m=awc) if profile.has_climate else None
    water_out = None
    if water:
        supply, supply_note = irrigation_supply(irr, farm.get("irrigation_capacity_mm"), water.net_irrigation_mm)
        ratio = (water.effective_rain_mm + water.stored_soil_water_mm + supply) / water.etc_mm if water.etc_mm else 1.0
        s = max(0.0, min(1.0, (ratio - 0.5) / 0.5))
        expl = (f"Crop water use ≈ {water.etc_mm:.0f} mm (Kc × ET0) vs effective rainfall ≈ "
                f"{water.effective_rain_mm:.0f} mm"
                + (f" plus ≈ {water.stored_soil_water_mm:.0f} mm stored soil water" if water.stored_soil_water_mm else "")
                + f". {supply_note}. Supply covers {min(ratio, 9.99) * 100:.0f}% of demand.")
        crit = None
        if crop["water_requirement"].get("requires_standing_water") and ratio < 0.9:
            crit = "Paddy rice needs assured water for standing water; seasonal supply is insufficient"
        elif ratio < 0.5:
            crit = "Seasonal water supply covers less than half of crop water demand"
        if crit:
            critical.append(crit)
        factors.append(_factor("water", s, round(ratio, 2), expl, critical=crit))
        water_out = {**water.as_dict(), "irrigation_supplied_mm": round(supply, 1),
                     "unmet_deficit_mm": round(max(0.0, water.net_irrigation_mm - supply), 1),
                     "supply_ratio": round(ratio, 2)}
    else:
        factors.append(_factor("water", None, None, "Water balance needs weather data", available=False))

    # 4. Growing-season fit
    season_days = season_length_months(season) * 30.4
    if duration <= season_days + 5:
        s, expl, crit = 1.0, f"Typical duration {duration} days fits the {season_days:.0f}-day season.", None
    elif duration <= season_days + 25:
        s, expl, crit = 0.6, (f"Typical duration {duration} days slightly exceeds the {season_days:.0f}-day season; "
                              "a short-duration variety or earlier sowing would be needed."), None
    else:
        s, crit = 0.0, f"Crop duration ({duration} d) does not fit the season ({season_days:.0f} d)"
        expl = crit + "."
        critical.append(crit)
    factors.append(_factor("growing_season", s, duration, expl, critical=crit))

    # 5. Soil pH
    ph = soil.get("ph")
    phr = crop["soil_preferences"]["ph"]
    if ph is not None:
        s = trapezoid(ph, phr)
        crit = "Soil pH outside the crop's absolute range" if s == 0 else None
        if crit:
            critical.append(crit)
        factors.append(_factor("soil_ph", s, ph, f"pH {ph:.1f} vs optimum {phr['optimal_min']}–{phr['optimal_max']} "
                                                 f"(absolute {phr['absolute_min']}–{phr['absolute_max']}).", critical=crit))
    else:
        factors.append(_factor("soil_ph", None, None, "Soil pH not provided", available=False))

    # 6. Texture & drainage
    tex = (soil.get("soil_texture") or farm.get("soil_type") or "").lower()
    group = TEXTURE_GROUP.get(tex)
    drainage = (soil.get("drainage") or "").lower() or None
    if group or drainage:
        parts, scores = [], []
        sp = crop["soil_preferences"]
        if group:
            if group in sp["texture_optimal"] or "wide" in sp["texture_optimal"]:
                scores.append(1.0)
                parts.append(f"{tex} ({group}) is an optimal texture")
            elif group in sp["texture_range"] or "wide" in sp["texture_range"]:
                scores.append(0.7)
                parts.append(f"{tex} ({group}) is tolerated")
            else:
                scores.append(0.3)
                parts.append(f"{tex} ({group}) is outside the preferred textures ({', '.join(sp['texture_range'])})")
        if drainage:
            if drainage in sp["drainage_optimal"]:
                scores.append(1.0)
                parts.append(f"{drainage} drained soil is optimal")
            elif drainage in sp["drainage_range"]:
                scores.append(0.7)
                parts.append(f"{drainage} drained soil is tolerated")
            else:
                scores.append(0.2)
                parts.append(f"{drainage} drained soil is unfavourable (prefers {', '.join(sp['drainage_optimal'])})")
        factors.append(_factor("soil_texture_drainage", min(scores), tex or drainage, "; ".join(parts) + "."))
    else:
        factors.append(_factor("soil_texture_drainage", None, None, "Soil texture/drainage not provided",
                               available=False))

    # 7. Nutrients (soil supply vs crop demand)
    n = to_kg_ha(soil.get("nitrogen"), soil.get("nitrogen_unit"))
    p_ = to_kg_ha(soil.get("phosphorus"), soil.get("phosphorus_unit"))
    if n is not None or p_ is not None:
        s, notes = 1.0, []
        demand = crop["nutrient_requirements"]["nitrogen_demand"]
        if n is not None and n < 280 and demand == "high":
            s -= 0.3
            notes.append("low soil N for a high-N-demand crop (fertiliser or legume credit needed)")
        if p_ is not None and p_ < 10 and crop["soil_preferences"].get("fertility_requirement") == "high":
            s -= 0.2
            notes.append("low available P for a crop with high fertility requirement")
        factors.append(_factor("nutrients", max(s, 0.2), demand,
                               "Nutrient supply adequate relative to demand." if not notes else "; ".join(notes).capitalize() + "."))
    else:
        factors.append(_factor("nutrients", None, None, "Soil nutrient tests not provided", available=False))

    # 8. Salinity
    ec = soil.get("electrical_conductivity")
    if ec is not None:
        tol = crop["soil_preferences"].get("salinity_tolerance", "moderate")
        limit = {"low": 2.0, "moderate": 4.0, "high": 8.0}.get(tol, 4.0)
        s = 1.0 if ec <= limit else max(0.0, 1 - (ec - limit) / limit)
        crit = f"Soil salinity ({ec} dS/m) exceeds tolerance" if ec > 2 * limit else None
        if crit:
            critical.append(crit)
        factors.append(_factor("salinity", s, ec, f"EC {ec} dS/m vs {tol} salinity tolerance (~{limit} dS/m).",
                               critical=crit))
    else:
        factors.append(_factor("salinity", None, None, "Electrical conductivity not provided", available=False))

    for f in factors:
        f["weight"] = weights.get(f["name"], 0)
    avail = [f for f in factors if f["available"] and f["score"] is not None]
    wsum = sum(f["weight"] for f in avail)
    score = 100 * sum(f["score"] * f["weight"] for f in avail) / wsum if wsum else None
    completeness = wsum / sum(weights.values())
    if critical:
        cls = "unsuitable"
    elif score is None:
        cls = "insufficient_data"
    elif score >= SUITABLE:
        cls = "suitable"
    elif score >= MODERATE:
        cls = "moderately_suitable"
    else:
        cls = "unsuitable"
    reasons = [f["explanation"] for f in sorted(avail, key=lambda f: -f["score"]) if f["score"] >= 0.8][:3]
    limits = [f["explanation"] for f in sorted(avail, key=lambda f: f["score"]) if f["score"] < 0.7][:4]
    return {
        "crop": crop["slug"], "crop_name": crop["crop_name"], "family": crop["crop_family"],
        "category": crop["category"], "season": season["name"], "season_label": season_label(season),
        "score": round(score, 1) if score is not None else None, "class": cls, "critical_constraints": critical,
        "factors": factors, "reasons": reasons, "limitations": limits, "data_completeness": round(completeness, 2),
        "water": water_out, "is_demo_basis": profile.is_demo,
    }


def assess_all(crops: list[dict], seasons: list[dict], profile, soil, farm, **kw) -> list[dict]:
    results = []
    for season in seasons:
        for crop in crops:
            results.append(assess_crop(crop, season, profile, soil, farm, **kw))
    return results
