"""Single-pool soil organic carbon model with humification of residue inputs.

ΔC = h_above × C_above + h_root × C_root − (1 − e^(−k·f)) × C
* Inputs: above-ground residue C = yield × residue:product ratio × retention × 0.45; root-derived C
  = 25 % of above-ground biomass C (root:shoot incl. rhizodeposition, after Bolinder et al. 2007).
* Humification coefficients after ICBM (Andrén & Kätterer 1997; Kätterer et al. 2011):
  h_above = 0.125, h_root = 0.35.
* Decomposition k = 0.02 yr⁻¹ at 15 °C scaled with Q10 = 2 by mean season temperature; f is the
  fraction of the year represented by the season.
* Low/high bounds vary h by ±30 % and k by ∓30 % to express parameter uncertainty.
The model gives directional, comparative estimates. It is not calibrated for any particular site.
"""
import math

H_ABOVE, H_ROOT = 0.125, 0.35
K_REF, T_REF, Q10 = 0.02, 15.0, 2.0
ROOT_FRACTION = 0.25
RETENTION = {"removed": 0.1, "partial": 0.5, "retained": 0.9}


def carbon_inputs(crop: dict | None, yield_t_ha: float, residue_management: str) -> dict:
    if crop is None:  # fallow
        return {"above_c": 0.0, "root_c": 0.0}
    res = crop["residue"]
    if res.get("green_manure"):
        biomass = yield_t_ha  # entire biomass is incorporated
        return {"above_c": biomass * res["carbon_fraction"], "root_c": biomass * ROOT_FRACTION * res["carbon_fraction"]}
    above_biomass = yield_t_ha * (1 + res["residue_to_product_ratio"])
    retained = yield_t_ha * res["residue_to_product_ratio"] * RETENTION.get(residue_management, 0.5)
    return {"above_c": retained * res["carbon_fraction"],
            "root_c": above_biomass * ROOT_FRACTION * res["carbon_fraction"]}


def decomposition_rate(t_mean_c: float | None) -> float:
    t = 20.0 if t_mean_c is None else t_mean_c
    return K_REF * Q10 ** ((t - T_REF) / 10)


def step(soc: float, inputs: dict, t_mean_c: float | None, fraction_of_year: float, h_mult: float = 1.0,
         k_mult: float = 1.0) -> float:
    k = decomposition_rate(t_mean_c) * k_mult
    loss = soc * (1 - math.exp(-k * fraction_of_year))
    gain = h_mult * (H_ABOVE * inputs["above_c"] + H_ROOT * inputs["root_c"])
    return soc - loss + gain
