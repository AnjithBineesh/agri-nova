"""Generates and ranks alternative crop rotation strategies for a farm."""
import itertools

from ..simulation.climate_scenarios import STRESS_TEST, Scenario
from ..simulation.rotation_simulator import FALLOW, combined_season, simulate
from . import rotation_rules
from .crop_suitability import assess_crop
from .priority_scoring import OBJECTIVE_LABELS, composite, normalise_weights, objective_scores

STRATEGY_PROFILES = {
    "soil_health": {"name": "Soil-health-oriented rotation",
                    "weights": {"soil_health": 60, "crop_diversity": 20, "water_conservation": 10,
                                "climate_resilience": 10}},
    "water_conscious": {"name": "Water-conscious rotation",
                        "weights": {"water_conservation": 60, "climate_resilience": 20, "soil_health": 10,
                                    "crop_diversity": 10}},
    "climate_resilient": {"name": "Climate-resilient rotation",
                          "weights": {"climate_resilience": 60, "water_conservation": 20, "soil_health": 10,
                                      "crop_diversity": 10}},
}
MAX_OPTIONS_PER_SEASON = 8
BEAM_WIDTH = 40
FINALISTS = 24
SELECTION_NON_HARVEST_PENALTY = 3.0


def non_harvest_seasons(rotation: list[dict], ctx: "Context") -> int:
    return sum(r.get("span", 1) for r in rotation
               if r["crop"] == FALLOW or ctx.crops[r["crop"]]["residue"].get("green_manure"))


class Context:
    def __init__(self, crops, profile, soil, farm, seasons, horizon_years=5, yields=None, economics=None,
                 history=None):
        self.crops, self.profile, self.soil, self.farm, self.seasons = crops, profile, soil, farm, seasons
        self.horizon_years, self.yields, self.economics, self.history = horizon_years, yields or {}, economics or {}, \
            history or []
        self.assess_cache: dict = {}
        self.stress = Scenario(temp_delta_c=STRESS_TEST["temp_delta_c"], rain_factor=STRESS_TEST["rain_factor"],
                               label="stress test")

    @property
    def cycle_len(self) -> int:
        return min(6, len(self.seasons) * 2)


def season_options(ctx: Context) -> list[list[dict]]:
    """Per season: candidate (crop, span) options that are not unsuitable, plus fallow."""
    out = []
    n = len(ctx.seasons)
    for i, season in enumerate(ctx.seasons):
        opts = []
        for slug, crop in ctx.crops.items():
            spans = [1] + ([2] if n >= 2 and crop["duration"]["typical_days"] > 140 else [])
            for span in spans:
                sea = combined_season(ctx.seasons, i, span)
                a = assess_crop(crop, sea, ctx.profile, ctx.soil, ctx.farm)
                if a["class"] in ("suitable", "moderately_suitable"):
                    st = assess_crop(crop, sea, ctx.profile, ctx.soil, ctx.farm, STRESS_TEST["temp_delta_c"],
                                     STRESS_TEST["rain_factor"])
                    water_ratio = (a["water"] or {}).get("supply_ratio_rainfed", 1.0) if a["water"] else 1.0
                    opts.append({"crop": slug, "span": span, "score": a["score"], "stress_score": st["score"] or 0,
                                 "stress_critical": bool(st["critical_constraints"]), "rainfed_ratio": water_ratio,
                                 "legume": crop["nitrogen_fixation"], "family": crop["crop_family"]})
        opts.sort(key=lambda o: -o["score"])
        out.append(opts[:MAX_OPTIONS_PER_SEASON] + [{"crop": FALLOW, "span": 1, "score": 50, "stress_score": 100,
                                                       "stress_critical": False, "rainfed_ratio": 1.0,
                                                       "legume": False, "family": None}])
    return out


def _heuristic(seq: list[dict], weights: dict, ctx: Context) -> float:
    planted = [o for o in seq if o["crop"] != FALLOW]
    if not planted:
        return 0.0
    suit = sum(o["score"] for o in planted) / (100 * len(planted))
    stress = sum(0 if o["stress_critical"] else o["stress_score"] for o in planted) / (100 * len(planted))
    water = sum(min(1.0, o["rainfed_ratio"]) for o in seq) / len(seq)
    rules = rotation_rules.evaluate([o["crop"] for o in seq], ctx.crops, ctx.history)
    soil = rules["rotation_health_index"] + 0.1 * sum(o["legume"] for o in planted) / len(planted)
    diversity = min(1.0, len({o["family"] for o in planted}) / 4)
    green = sum(1 for o in planted if ctx.crops[o["crop"]]["residue"].get("green_manure"))
    fallow_pen = 0.08 * (len(seq) - len(planted)) + 0.05 * max(0, green - 1)
    w = {k: weights.get(k, 0) / 100 for k in weights}
    return (0.35 * suit + w.get("soil_health", 0) * soil + w.get("water_conservation", 0) * water
            + w.get("climate_resilience", 0) * stress + w.get("crop_diversity", 0) * diversity - fallow_pen)


def beam_search(options: list[list[dict]], weights: dict, ctx: Context) -> list[list[dict]]:
    n = len(ctx.seasons)
    beams: list[tuple[list[dict], int]] = [([], 0)]  # (slots, seasons consumed)
    complete: list[list[dict]] = []
    while beams:
        nxt = []
        for seq, used in beams:
            if used >= ctx.cycle_len:
                complete.append(seq)
                continue
            for opt in options[used % n]:
                if used + opt["span"] > ctx.cycle_len:
                    continue
                nxt.append((seq + [opt], used + opt["span"]))
        if not nxt:
            break
        nxt.sort(key=lambda t: -_heuristic(t[0], weights, ctx))
        beams = nxt[:BEAM_WIDTH]
    uniq, seen = [], set()
    for seq in sorted(complete, key=lambda s: -_heuristic(s, weights, ctx)):
        key = tuple((o["crop"], o["span"]) for o in seq)
        if key not in seen:
            seen.add(key)
            uniq.append(seq)
    return uniq[:FINALISTS]


def evaluate_sequence(rotation: list[dict], ctx: Context, scenario: Scenario | None = None) -> dict:
    base = simulate(rotation, ctx.crops, ctx.profile, ctx.soil, ctx.farm, ctx.seasons, scenario,
                    ctx.horizon_years, ctx.yields, ctx.economics, ctx.history, ctx.assess_cache)
    stress = simulate(rotation, ctx.crops, ctx.profile, ctx.soil, ctx.farm, ctx.seasons, ctx.stress,
                      ctx.horizon_years, ctx.yields, ctx.economics, ctx.history, ctx.assess_cache)
    rules = rotation_rules.evaluate([s["crop"] for s in rotation], ctx.crops, ctx.history)
    return {"rotation": rotation, "simulation": base, "stress_simulation": stress, "rules": rules}


def _explain(key: str, name: str, ev: dict, obj: dict, ctx: Context, comp_notes: list[str], reason: str) -> dict:
    s = ev["simulation"]["summary"]
    rot = ev["rotation"]
    years = ctx.horizon_years
    crops_txt = [ctx.crops[r["crop"]]["crop_name"] if r["crop"] != FALLOW else "Fallow" for r in rot]
    positives = [f["message"] for f in ev["rules"]["findings"] if f["severity"] == "positive"]
    warnings = [f["message"] for f in ev["rules"]["findings"] if f["severity"] in ("warning", "critical")]
    legumes = [r["crop"] for r in rot if r["crop"] != FALLOW and ctx.crops[r["crop"]]["nitrogen_fixation"]]
    d_soc = s["soc_change_t_ha"] or {}
    climate_risks = []
    st = ev["stress_simulation"]["summary"]
    if st["critical_seasons"]:
        climate_risks.append(f"{st['critical_seasons']} season(s) hit a critical constraint under the stress test "
                             "(+1.5 °C, −15% rainfall).")
    if st["high_vulnerability_seasons"]:
        climate_risks.append(f"{st['high_vulnerability_seasons']} season(s) show high climate vulnerability under "
                             "the stress test.")
    if not climate_risks:
        climate_risks.append("No critical temperature or water constraints under the stress test.")
    crit_seasons = [r for r in ev["simulation"]["seasons"] if r.get("critical_constraints")]
    for r in crit_seasons[:2]:
        climate_risks.append(f"{r['crop_name']} in {r['season']}: {r['critical_constraints'][0]}.")
    return {
        "reason": reason,
        "sequence_text": " → ".join(crops_txt),
        "water": {"total_crop_water_mm": s["total_crop_water_mm"],
                  "average_annual_crop_water_mm": round(s["total_crop_water_mm"] / years),
                  "average_annual_irrigation_need_mm": round(s["total_irrigation_need_mm"] / years),
                  "rainfed_supply_fraction": s["rainfed_supply_fraction"],
                  "unmet_deficit_mm": s["total_unmet_deficit_mm"]},
        "soil_health": positives + [f"Estimated topsoil organic carbon change over {years} years: "
                                    f"{d_soc.get('central', 0):+.2f} t C/ha (range {d_soc.get('low', 0):+.2f} to "
                                    f"{d_soc.get('high', 0):+.2f})."],
        "nutrients": [f"Cumulative N balance before fertiliser: {s['n_balance_cum_kg_ha']:+.0f} kg N/ha over {years} "
                      f"years (negative = must be supplied by fertiliser, manure or soil reserves).",
                      f"P2O5 {s['p2o5_balance_cum_kg_ha']:+.0f} and K2O {s['k2o_balance_cum_kg_ha']:+.0f} kg/ha removed "
                      "in harvests."] + (["Legumes fix part of their own N; net benefit to following crops depends on "
                                          "residue management."] if legumes else []),
        "climate_risks": climate_risks,
        "economics": (f"Gross margin over {years} years: {s['gross_margin_total']:,.0f} (farmer-provided prices/costs)."
                      if s["gross_margin_total"] is not None else
                      "Not assessed: add local prices, costs and expected yields to compare economic performance."),
        "rotation_warnings": warnings,
        "limitations": ["Recommendations are decision support, not guarantees of yield or soil improvement.",
                        "Based on regional-resolution satellite and climate data; confirm with local extension "
                        "officers or agronomists before major changes."] + comp_notes
                       + (["Built on DEMONSTRATION data – not real observations."] if ctx.profile.is_demo else []),
        "objective_breakdown": {OBJECTIVE_LABELS[k]: v for k, v in obj.items()},
    }


def existing_practice(ctx: Context, farm_history: list[dict], current_crop: str | None) -> list[dict] | None:
    n = len(ctx.seasons)
    names = [s["name"] for s in ctx.seasons]
    seq: list[str] = []
    if farm_history:
        hist = sorted(farm_history, key=lambda h: (h["year"], names.index(h["season"]) if h["season"] in names else 0))
        seq = [h["crop_slug"] for h in hist if h["crop_slug"] in ctx.crops or h["crop_slug"] == FALLOW][-n:]
    if not seq and current_crop in ctx.crops:
        seq = [current_crop] * n
    if not seq:
        return None
    while len(seq) < ctx.cycle_len:
        seq = seq + seq
    return [{"crop": c, "span": 1} for c in seq[:ctx.cycle_len]]


def generate(ctx: Context, farmer_weights: dict, farm_history: list[dict], current_crop: str | None,
             custom: list[dict] | None = None) -> dict:
    farmer_weights = normalise_weights(farmer_weights)
    options = season_options(ctx)
    evaluated: dict[tuple, dict] = {}

    def ev_of(rotation):
        key = tuple((r["crop"], r.get("span", 1)) for r in rotation)
        if key not in evaluated:
            evaluated[key] = evaluate_sequence(rotation, ctx)
        return evaluated[key]

    strategies = []
    existing = existing_practice(ctx, farm_history, current_crop)
    plans: list[tuple[str, str, list[dict], str]] = []
    if existing:
        plans.append(("existing", "Existing practice", existing,
                      "Your recorded crop history (or current crop) repeated, as a baseline for comparison."))
    used_keys = {tuple((r["crop"], r["span"]) for r in existing)} if existing else set()
    candidate_pool: list[list[dict]] = []
    for key, prof in [*STRATEGY_PROFILES.items(), ("balanced", {"name": "Balanced for your priorities",
                                                                "weights": farmer_weights})]:
        finalists = beam_search(options, prof["weights"], ctx)
        candidate_pool += finalists
        ranked = []
        for seq in finalists:
            rotation = [{"crop": o["crop"], "span": o["span"]} for o in seq]
            ev = ev_of(rotation)
            ranked.append((rotation, ev))
        gm = [e["simulation"]["summary"]["gross_margin_total"] for _, e in ranked
              if e["simulation"]["summary"]["gross_margin_total"] is not None]
        gm_range = (min(gm), max(gm)) if gm else None
        scored = []
        for rotation, ev in ranked:
            obj = objective_scores(ev["simulation"], ev["stress_simulation"], ev["rules"], gm_range)
            score, _ = composite(obj, normalise_weights(prof["weights"]))
            # Selection only (not the farmer-facing ranking): without economic data, keep harvested crops in the
            # rotation by discounting cycles with more than one non-harvest (fallow / green manure) season.
            if gm_range is None:
                score = (score or 0) - SELECTION_NON_HARVEST_PENALTY * max(0, non_harvest_seasons(rotation, ctx) - 1)
            scored.append((score or 0, rotation))
        scored.sort(key=lambda t: -t[0])
        pick = next((r for _, r in scored if tuple((x["crop"], x["span"]) for x in r) not in used_keys),
                    scored[0][1] if scored else None)
        if pick is None:
            continue
        used_keys.add(tuple((x["crop"], x["span"]) for x in pick))
        reason = {
            "soil_health": "Selected to maximise rotation health: legumes, family breaks, residue carbon inputs and "
                           "nutrient balance.",
            "water_conscious": "Selected to minimise irrigation need and unmet water deficit relative to rainfall.",
            "climate_resilient": "Selected for crops that stay within temperature and water limits under a warmer, "
                                 "drier stress test (+1.5 °C, −15% rainfall).",
            "balanced": "Best overall match to your current priority weights.",
        }[key]
        plans.append((key, prof["name"], pick, reason))
    if custom:
        plans.append(("custom", "Custom rotation", custom, "Your own sequence, evaluated with the same models."))

    all_evs = [ev_of(p[2]) for p in plans]
    gm = [e["simulation"]["summary"]["gross_margin_total"] for e in all_evs
          if e["simulation"]["summary"]["gross_margin_total"] is not None]
    gm_range = (min(gm), max(gm)) if gm else None
    for (key, name, rotation, reason), ev in zip(plans, all_evs):
        obj = objective_scores(ev["simulation"], ev["stress_simulation"], ev["rules"], gm_range)
        score, notes = composite(obj, farmer_weights)
        suit = [r["suitability_score"] for r in ev["simulation"]["seasons"]
                if not r["continuation"] and r["crop"] != FALLOW and r.get("suitability_score") is not None]
        strategies.append({
            "key": key, "name": name, "rotation": rotation,
            "crop_sequence": [{"crop": r["crop"], "span": r.get("span", 1),
                               "crop_name": ctx.crops[r["crop"]]["crop_name"] if r["crop"] != FALLOW else "Fallow",
                               "season": combined_season(ctx.seasons, i_season, r.get("span", 1))["name"]}
                              for r, i_season in zip(rotation, itertools.accumulate([0] + [x.get("span", 1)
                                                                                           for x in rotation[:-1]]))],
            "mean_suitability": round(sum(suit) / len(suit), 1) if suit else None,
            "harvested_seasons": ctx.cycle_len - non_harvest_seasons(rotation, ctx),
            "cycle_seasons": ctx.cycle_len,
            "objectives": obj, "priority_score": score,
            "rules": ev["rules"], "simulation_summary": ev["simulation"]["summary"],
            "stress_summary": ev["stress_simulation"]["summary"],
            "explanation": _explain(key, name, ev, obj, ctx, notes, reason),
        })
    ranked = sorted([s for s in strategies if s["priority_score"] is not None], key=lambda s: -s["priority_score"])
    for i, s in enumerate(ranked, 1):
        s["rank"] = i
    return {"strategies": strategies, "priority_weights": farmer_weights,
            "cycle_seasons": ctx.cycle_len, "seasons": ctx.seasons,
            "note": "Ranking reflects your priority weights. The top-ranked rotation is not universally best: "
                    "compare the trade-offs below and consult local agronomists for high-impact decisions."}
