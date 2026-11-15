"""Simulation state carried from one season to the next."""
from dataclasses import dataclass, field

BULK_DENSITY_BY_GROUP = {"light": 1.50, "medium": 1.35, "heavy": 1.25, "organic": 0.50}
TOPSOIL_DEPTH_CM = 30.0
ASSUMED_OC_PERCENT = 0.75


@dataclass
class SoilState:
    soc_central: float  # t C/ha in 0–30 cm
    soc_low: float
    soc_high: float
    n_balance_cum: float = 0.0  # kg N/ha, excluding fertiliser & manure
    p_balance_cum: float = 0.0  # kg P2O5/ha
    k_balance_cum: float = 0.0  # kg K2O/ha
    pending_n_credit: float = 0.0  # legume / green-manure residual N available to the next crop
    families_seen: list[str] = field(default_factory=list)
    crops_seen: list[str] = field(default_factory=list)


def initial_soc(oc_percent: float | None, texture_group: str | None, bulk_density: float | None = None
                ) -> tuple[float, dict]:
    """SOC stock (t C/ha) = OC% × bulk density (g/cm3) × depth (cm)."""
    assumptions = {}
    if bulk_density is None:
        bulk_density = BULK_DENSITY_BY_GROUP.get(texture_group or "", 1.35)
        assumptions["bulk_density"] = f"{bulk_density} g/cm³ assumed from texture group ({texture_group or 'unknown'})"
    if oc_percent is None:
        oc_percent = ASSUMED_OC_PERCENT
        assumptions["organic_carbon"] = (f"No measured organic carbon: an illustrative baseline of {ASSUMED_OC_PERCENT}% "
                                         "is assumed. Only the relative change between strategies is meaningful.")
    return oc_percent * bulk_density * TOPSOIL_DEPTH_CM, assumptions
