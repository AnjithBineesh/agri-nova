"""State-based multi-season rotation simulator.

Each season's ending soil state (SOC stock, cumulative nutrient balances, residual legume N) is
the next season's starting state. Climate inputs come from the farm's historical climatology,
optionally shifted by a scenario. Results are comparative indications with explicit assumptions
and uncertainty ranges – not forecasts of yield or soil test values.
"""
import math
import statistics

from ..agriculture.climate_analyser import EnvironmentProfile
from ..agriculture.soil_analyser import TEXTURE_GROUP, estimated_awc
from ..recommendation_engine.crop_suitability import assess_crop
from ..recommendation_engine.seasons import season_label
from . import nutrient_balance, organic_matter_model as som
from .climate_scenarios import Scenario
from .soil_state import SoilState, initial_soc
from .water_balance import irrigation_supply, season_water

FALLOW = "fallow"
COVER_FACTOR = {"legume": 0.45, "cover_crop": 0.35, "cereal": 0.5, "oilseed": 0.7, "fibre": 0.7, "vegetable": 0.75,
                "cash": 0.4}
DENSE_LEGUMES = {"cowpea", "groundnut", "green_gram", "black_gram"}


def expand_rotation(rotation: list[dict], n_seasons: int) -> list[dict]:
    """Expand [{'crop','span'}] into one entry per season, cycling through the rotation."""
    unit = []
    for slot in rotation:
        span = max(1, int(slot.get("span", 1)))
        unit.append({"crop": slot["crop"], "span": span, "continuation": False})
        for _ in range(span - 1):
            unit.append({"crop": slot["crop"], "span": span, "continuation": True})
    out = []
    while len(out) < n_seasons:
        out.extend(dict(u) for u in unit)
    out = out[:n_seasons]
    if out and out[0]["continuation"]:
        out[0]["continuation"] = False
    return out


def combined_season(seasons: list[dict], idx: int, span: int) -> dict:
    s = dict(seasons[idx % len(seasons)])
    if span > 1:
        last = seasons[(idx + span - 1) % len(seasons)]
        s = {"name": " + ".join(seasons[(idx + k) % len(seasons)]["name"] for k in range(span)),
             "start_month": s["start_month"], "end_month": last["end_month"]}
    return s


def _slope_factor(slope: float | None) -> float:
    if slope is None:
        return 0.6
    return 0.3 if slope < 2 else (0.6 if slope < 5 else (1.0 if slope < 10 else 1.5))


def _class(v: float, lo: float, hi: float) -> str:
    return "low" if v < lo else ("moderate" if v <= hi else "high")


def simulate(rotation: list[dict], crops: dict[str, dict], profile: EnvironmentProfile, soil: dict | None,
             farm: dict, seasons: list[dict], scenario: Scenario | None = None, horizon_years: int = 5,
             yields: dict | None = None, economics: dict | None = None, history: list[str] | None = None,
             assess_cache: dict | None = None) -> dict:
    scenario = scenario or Scenario()
    assess_cache = assess_cache if assess_cache is not None else {}
    yields, economics, soil = yields or {}, economics or {}, soil or {}
    irr_type = scenario.irrigation_type or farm.get("irrigation_type", "none")
    irr_cap = scenario.irrigation_capacity_mm if scenario.irrigation_capacity_mm is not None \
        else farm.get("irrigation_capacity_mm")
    residue = farm.get("residue_management", "partial")
    tex_group = TEXTURE_GROUP.get((soil.get("soil_texture") or farm.get("soil_type") or "").lower())
    oc = soil.get("organic_carbon")
    if oc is None and soil.get("organic_matter") is not None:
        oc = soil["organic_matter"] / 1.724
    soc0, soc_assumptions = initial_soc(oc, tex_group)
    awc = soil.get("water_holding_capacity") or estimated_awc(soil.get("soil_texture") or farm.get("soil_type"))
    state = SoilState(soc_central=soc0, soc_low=soc0, soc_high=soc0)
    farm_for_assess = {**farm, "irrigation_type": irr_type, "irrigation_capacity_mm": irr_cap}
    n_seasons = len(seasons) * horizon_years
    plan = expand_rotation(rotation, n_seasons)
    cv = profile.annual_precip_cv or 0.2
    slope = (profile.terrain or {}).get("slope_deg")
    covered_months = set()
    for s in seasons:
        covered_months |= set(profile.season_months(s["start_month"], s["end_month"]))
    gap_months = [m for m in range(1, 13) if m not in covered_months]
    rows = []
    prev_crop = (history or [None])[-1]
    economics_available = bool(economics) and all(
        p["crop"] == FALLOW or p["crop"] in economics for p in plan)

    for g, slot in enumerate(plan):
        year = g // len(seasons) + 1
        s_idx = g % len(seasons)
        season = seasons[s_idx]
        slug = slot["crop"]
        if slot["continuation"]:
            rows.append({"index": g, "year": year, "season": season["name"], "crop": slug,
                         "crop_name": crops[slug]["crop_name"] if slug in crops else slug, "continuation": True})
            continue
        sea = combined_season(seasons, g, slot["span"])
        months = profile.season_months(sea["start_month"], sea["end_month"])
        frac = len(months) / 12
        t_mean = statistics.mean(profile.monthly[m - 1]["t_mean"] for m in months) + scenario.temp_delta_c \
            if profile.has_climate else None
        crop = crops.get(slug) if slug != FALLOW else None
        row = {"index": g, "year": year, "season": sea["name"], "season_label": season_label(sea), "crop": slug,
               "crop_name": crop["crop_name"] if crop else "Fallow", "family": crop["crop_family"] if crop else None,
               "span": slot["span"], "continuation": False}

        if crop:
            y = float(yields.get(slug) or crop["nutrient_requirements"]["reference_yield_t_ha"])
            row["yield_t_ha"] = y
            row["yield_source"] = "farmer-provided" if slug in yields else "reference (indicative) yield"
            water = season_water(crop, profile.monthly, sea["start_month"], scenario.temp_delta_c,
                                 scenario.rain_factor, awc_mm_per_m=awc) if profile.has_climate else None
            if water:
                supply, _ = irrigation_supply(irr_type, irr_cap, water.net_irrigation_mm)
                dry = season_water(crop, profile.monthly, sea["start_month"], scenario.temp_delta_c,
                                   scenario.rain_factor * max(0.3, 1 - cv), awc_mm_per_m=awc)
                wet = season_water(crop, profile.monthly, sea["start_month"], scenario.temp_delta_c,
                                   scenario.rain_factor * (1 + cv), awc_mm_per_m=awc)
                row["water"] = {"etc_mm": round(water.etc_mm), "effective_rain_mm": round(water.effective_rain_mm),
                                "stored_soil_water_mm": round(water.stored_soil_water_mm),
                                "irrigation_need_mm": round(water.net_irrigation_mm),
                                "irrigation_need_range_mm": [round(wet.net_irrigation_mm), round(dry.net_irrigation_mm)],
                                "irrigation_supplied_mm": round(supply),
                                "unmet_deficit_mm": round(max(0.0, water.net_irrigation_mm - supply))}
            key = (slug, sea["start_month"], sea["end_month"], scenario.temp_delta_c, scenario.rain_factor, irr_type,
                   irr_cap)
            if key not in assess_cache:
                assess_cache[key] = assess_crop(crop, sea, profile, soil, farm_for_assess, scenario.temp_delta_c,
                                                scenario.rain_factor)
            assessed = assess_cache[key]
            row["suitability_score"] = assessed["score"]
            row["critical_constraints"] = assessed["critical_constraints"]
            fscores = {f["name"]: f["score"] for f in assessed["factors"] if f["score"] is not None}
            stress = min(fscores.get("temperature", 1.0), fscores.get("water", 1.0))
            vuln = 1.0 if assessed["critical_constraints"] else 1 - stress
            nb = nutrient_balance.season_balance(crop, y, residue, state.pending_n_credit)
            inputs = som.carbon_inputs(crop, y, residue)
            cover = COVER_FACTOR.get(crop["category"], 0.6) * (0.85 if slug in DENSE_LEGUMES else 1.0)
            if economics_available:
                e = economics[slug]
                row["gross_margin"] = round(y * float(e.get("price_per_t", 0)) - float(e.get("cost_per_ha", 0)), 2)
            state.families_seen.append(crop["crop_family"])
            state.crops_seen.append(slug)
            if prev_crop == slug:
                vuln = min(1.0, vuln + 0.1)  # monoculture adds pest/disease exposure
            prev_crop = slug
        else:
            nb = nutrient_balance.season_balance(None, 0, residue, state.pending_n_credit)
            inputs = som.carbon_inputs(None, 0, residue)
            cover = 0.6 if residue == "retained" else 1.0
            vuln = 0.0
            row["water"] = {"etc_mm": 0, "effective_rain_mm": 0, "stored_soil_water_mm": 0, "irrigation_need_mm": 0,
                            "irrigation_need_range_mm": [0, 0], "irrigation_supplied_mm": 0, "unmet_deficit_mm": 0}
            if economics_available:
                row["gross_margin"] = 0.0
            prev_crop = None

        state.soc_central = som.step(state.soc_central, inputs, t_mean, frac)
        state.soc_low = som.step(state.soc_low, inputs, t_mean, frac, h_mult=0.7, k_mult=1.3)
        state.soc_high = som.step(state.soc_high, inputs, t_mean, frac, h_mult=1.3, k_mult=0.7)
        state.n_balance_cum += nb["n"]
        state.p_balance_cum += nb["p"]
        state.k_balance_cum += nb["k"]
        state.pending_n_credit = nb["n_credit_out"]

        # Decomposition continues during months outside all growing seasons (once per year, after last season).
        if s_idx == len(seasons) - 1 and gap_months and profile.has_climate:
            t_gap = statistics.mean(profile.monthly[m - 1]["t_mean"] for m in gap_months) + scenario.temp_delta_c
            zero = {"above_c": 0.0, "root_c": 0.0}
            state.soc_central = som.step(state.soc_central, zero, t_gap, len(gap_months) / 12)
            state.soc_low = som.step(state.soc_low, zero, t_gap, len(gap_months) / 12, k_mult=1.3)
            state.soc_high = som.step(state.soc_high, zero, t_gap, len(gap_months) / 12, k_mult=0.7)

        season_rain = sum((profile.monthly[m - 1]["precip_mm"] or 0) for m in months) * scenario.rain_factor \
            if profile.has_climate else 500
        erosion = cover * _slope_factor(slope) * min(2.0, season_rain / 500)
        counts = {f: state.families_seen.count(f) for f in set(state.families_seen)}
        total = sum(counts.values())
        shannon = -sum((c / total) * math.log(c / total) for c in counts.values()) if total else 0.0
        row.update({
            "n_balance_kg_ha": round(nb["n"], 1), "n_fixed_kg_ha": round(nb["n_fixed"], 1),
            "n_credit_used_kg_ha": round(nb["n_credit_used"], 1),
            "n_balance_cum": round(state.n_balance_cum, 1), "p2o5_balance_cum": round(state.p_balance_cum, 1),
            "k2o_balance_cum": round(state.k_balance_cum, 1),
            "carbon_input_t_ha": round(inputs["above_c"] + inputs["root_c"], 2),
            "soc_t_ha": {"central": round(state.soc_central, 2), "low": round(state.soc_low, 2),
                         "high": round(state.soc_high, 2)},
            "family_count": len(counts), "shannon_diversity": abs(round(shannon, 3)),
            "climate_vulnerability": round(vuln, 2), "climate_vulnerability_class": _class(vuln, 0.3, 0.6),
            "erosion_index": round(erosion, 2), "erosion_class": _class(erosion, 0.3, 0.7),
        })
        rows.append(row)

    planted = [r for r in rows if not r["continuation"]]
    crops_rows = [r for r in planted if r["crop"] != FALLOW]
    water_rows = [r["water"] for r in planted if r.get("water")]
    summary = {
        "seasons_simulated": n_seasons, "horizon_years": horizon_years,
        "soc_initial_t_ha": round(soc0, 2),
        "soc_final_t_ha": planted[-1]["soc_t_ha"] if planted else None,
        "soc_change_t_ha": {k: round(v - soc0, 2) for k, v in planted[-1]["soc_t_ha"].items()} if planted else None,
        "n_balance_cum_kg_ha": round(state.n_balance_cum, 1), "p2o5_balance_cum_kg_ha": round(state.p_balance_cum, 1),
        "k2o_balance_cum_kg_ha": round(state.k_balance_cum, 1),
        "total_crop_water_mm": sum(w["etc_mm"] for w in water_rows),
        "total_irrigation_need_mm": sum(w["irrigation_need_mm"] for w in water_rows),
        "total_unmet_deficit_mm": sum(w["unmet_deficit_mm"] for w in water_rows),
        # Share of crop water demand not requiring irrigation (rain + stored soil water), season by season.
        "rainfed_supply_fraction": round(1 - sum(w["irrigation_need_mm"] for w in water_rows) /
                                         max(1, sum(w["etc_mm"] for w in water_rows)), 3) if water_rows else None,
        "families": sorted(set(state.families_seen)), "family_count": len(set(state.families_seen)),
        "shannon_diversity": planted[-1]["shannon_diversity"] if planted else 0,
        "mean_climate_vulnerability": round(statistics.mean(r["climate_vulnerability"] for r in crops_rows), 2)
        if crops_rows else None,
        "high_vulnerability_seasons": sum(1 for r in crops_rows if r["climate_vulnerability_class"] == "high"),
        "high_erosion_seasons": sum(1 for r in planted if r["erosion_class"] == "high"),
        "critical_seasons": sum(1 for r in crops_rows if r.get("critical_constraints")),
        "gross_margin_total": round(sum(r.get("gross_margin", 0) for r in planted), 2) if economics_available else None,
        "is_demo_basis": profile.is_demo,
    }
    assumptions = {
        **soc_assumptions,
        "climate": "Ten-year monthly weather climatology for the farm (satellite rainfall when available) "
                   f"shifted by the scenario (ΔT = {scenario.temp_delta_c:+.1f} °C, rainfall × {scenario.rain_factor:.2f}). "
                   "Every year repeats the same climatology; year-to-year variability is expressed as a dry/wet "
                   f"range using the observed rainfall coefficient of variation ({cv:.2f}).",
        "water": "FAO-56 single crop coefficient ETc with generic stage lengths; FAO/AGLW effective rainfall; "
                 "stored soil water at sowing = min(root-zone available water, prior 3-month rainfall surplus) x 0.6 "
                 + ("(available water capacity from soil data). " if awc else "(not counted: soil texture unknown). ")
                 +
                 f"Irrigation: {irr_type}" + (f", capacity {irr_cap} mm/season" if irr_cap else "") + ".",
        "yields": "Reference (indicative) yields are used for nutrient removal and residue inputs unless the farmer "
                  "provides expected yields. Yields are not predicted or adjusted for stress.",
        "nutrients": "Partial balance excluding fertiliser, manure and atmospheric deposition; indicative removal "
                     "coefficients and legume %Ndfa.",
        "organic_carbon_model": "Single-pool model (ICBM-type humification, Q10 temperature-dependent decomposition) for "
                          "0–30 cm; low/high bounds vary parameters ±30%.",
        "residues": f"Residue management: {residue}.",
        "erosion": "Qualitative index = cover factor × slope class × seasonal rainfall; not a soil-loss model.",
        "economics": "Computed only from farmer-provided prices and costs." if economics_available
        else "Not computed: provide local prices and costs for every crop in the rotation.",
    }
    return {"seasons": rows, "summary": summary, "assumptions": assumptions, "scenario": scenario.as_dict()}
