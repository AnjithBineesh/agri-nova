"""Compare simulated strategies indicator by indicator and describe trade-offs."""

INDICATORS = [
    ("soc_change", "Soil organic carbon change (t C/ha)", "higher"),
    ("n_balance", "Cumulative N balance before fertiliser (kg N/ha)", "higher"),
    ("irrigation_need", "Total irrigation need (mm)", "lower"),
    ("unmet_deficit", "Unmet water deficit (mm)", "lower"),
    ("family_count", "Crop families", "higher"),
    ("vulnerability", "Mean climate vulnerability (0–1)", "lower"),
    ("erosion", "High erosion-risk seasons", "lower"),
    ("gross_margin", "Gross margin (farmer prices)", "higher"),
]


def _values(sim: dict) -> dict:
    s = sim["summary"]
    return {
        "soc_change": (s["soc_change_t_ha"] or {}).get("central"),
        "n_balance": s["n_balance_cum_kg_ha"],
        "irrigation_need": s["total_irrigation_need_mm"],
        "unmet_deficit": s["total_unmet_deficit_mm"],
        "family_count": s["family_count"],
        "vulnerability": s["mean_climate_vulnerability"],
        "erosion": s["high_erosion_seasons"],
        "gross_margin": s["gross_margin_total"],
    }


def compare(named: dict[str, dict]) -> dict:
    table = []
    best_by: dict[str, list[str]] = {}
    vals = {name: _values(sim) for name, sim in named.items()}
    for key, label, direction in INDICATORS:
        row = {"indicator": key, "label": label, "better": direction, "values": {n: v[key] for n, v in vals.items()}}
        present = {n: v for n, v in row["values"].items() if v is not None}
        if len(present) >= 2 and len(set(present.values())) > 1:
            target = max(present.values()) if direction == "higher" else min(present.values())
            row["best"] = [n for n, v in present.items() if v == target]
            for n in row["best"]:
                best_by.setdefault(n, []).append(label)
        table.append(row)
    tradeoffs = []
    for name, labels in best_by.items():
        tradeoffs.append(f"{name} performs best on: {', '.join(labels)}.")
    if len(best_by) > 1:
        tradeoffs.append("No strategy is best on every indicator – the right choice depends on which objectives "
                         "matter most for this farm.")
    return {"table": table, "tradeoffs": tradeoffs}
