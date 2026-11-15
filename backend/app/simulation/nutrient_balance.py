"""Partial nutrient balance per season, excluding fertiliser, manure and atmospheric inputs.

* Removal = yield × removal coefficient (kg per t harvested product, indicative IPNI/IFA values).
* Legumes draw (1 − %Ndfa) of their N removal from the soil; the fixed share is supplied
  biologically (Herridge et al. 2008 typical %Ndfa 50–70 %).
* Residual N credit to the next crop depends on residue management (Peoples et al. 2009 report
  small or negative net balances for high-harvest-index grain legumes). Credits are indicative.
A negative cumulative balance indicates nutrients that must come from fertiliser, manure or soil
reserves – it is not a prediction of soil test values.
"""


def season_balance(crop: dict | None, yield_t_ha: float, residue_management: str, n_credit_in: float) -> dict:
    if crop is None:
        return {"n": n_credit_in * 0.5, "p": 0.0, "k": 0.0, "n_credit_out": 0.0, "n_removed": 0.0,
                "n_fixed": 0.0, "n_credit_used": n_credit_in * 0.5}
    rem = crop["nutrient_requirements"]["removal_kg_per_t"]
    n_removed = rem["N"] * yield_t_ha
    fix = crop.get("fixation") or {}
    ndfa = fix.get("ndfa_fraction", 0.0) or 0.0
    soil_draw = n_removed * (1 - ndfa)
    n = -soil_draw + n_credit_in
    credits = fix.get("residual_n_credit_kg_ha") or {}
    if crop["residue"].get("green_manure"):
        credit_out = credits.get("residue_retained", 0.0)
    elif credits:
        credit_out = credits.get("residue_retained" if residue_management != "removed" else "residue_removed", 0.0)
        if residue_management == "partial":
            credit_out = (credits.get("residue_retained", 0) + credits.get("residue_removed", 0)) / 2
    else:
        credit_out = 0.0
    return {"n": n, "p": -rem["P2O5"] * yield_t_ha, "k": -rem["K2O"] * yield_t_ha, "n_credit_out": credit_out,
            "n_removed": n_removed, "n_fixed": n_removed * ndfa, "n_credit_used": n_credit_in}
