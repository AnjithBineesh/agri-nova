"""Seasonal crop water balance (FAO-56 single crop coefficient approach, monthly climatology).

ETc = Σ Kc(day) × ET0(day); effective rainfall from the FAO/AGLW monthly formula, pro-rated by
days; net irrigation requirement = max(0, ETc − Peff). Generic growth-stage proportions
(initial 15 %, development 25 %, mid-season 40 %, late 20 % of the crop duration) are assumed
because stage lengths are variety- and region-specific (FAO-56 Table 11).
"""
import calendar
from dataclasses import dataclass

from ..agriculture.et0 import effective_rainfall_monthly

STAGE_FRACTIONS = (0.15, 0.25, 0.40, 0.20)
STORAGE_AVAILABILITY = 0.6  # share of stored root-zone water assumed usable (gradual root growth, evaporation)
PADDY_EXTRA_MM_PER_DAY = 4.0  # percolation + seepage allowance for puddled rice (FAO-56/FAO IWM manuals: 4–8 mm/d)


@dataclass
class SeasonWater:
    etc_mm: float
    effective_rain_mm: float
    rain_mm: float
    net_irrigation_mm: float
    duration_days: int
    supply_ratio_rainfed: float  # (Peff + stored soil water) / ETc
    stored_soil_water_mm: float = 0.0

    def as_dict(self) -> dict:
        return {k: round(v, 1) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def kc_for_day(day: int, duration: int, kc: dict) -> float:
    f_ini, f_dev, f_mid, _ = STAGE_FRACTIONS
    t1, t2, t3 = duration * f_ini, duration * (f_ini + f_dev), duration * (f_ini + f_dev + f_mid)
    if day < t1:
        return kc["ini"]
    if day < t2:
        return kc["ini"] + (kc["mid"] - kc["ini"]) * (day - t1) / (t2 - t1)
    if day < t3:
        return kc["mid"]
    return kc["mid"] + (kc["end"] - kc["mid"]) * (day - t3) / max(duration - t3, 1)


def stored_soil_water(crop: dict, monthly: list[dict], start_month: int, awc_mm_per_m: float | None,
                      rain_factor: float = 1.0) -> float:
    """Plant-available water stored in the root zone at sowing (assumption-based).

    Storage = min(root-zone available water capacity, rainfall surplus P − ET0 of the 3 months before
    sowing) × STORAGE_AVAILABILITY. Relevant for post-rainy-season crops grown on residual moisture.
    """
    if not awc_mm_per_m:
        return 0.0
    capacity = awc_mm_per_m * crop["root_characteristics"]["max_depth_m"]["min"]
    surplus = 0.0
    for k in (1, 2, 3):
        row = monthly[(start_month - 1 - k) % 12]
        surplus += max(0.0, (row.get("precip_mm") or 0.0) * rain_factor - (row.get("et0_mm") or 0.0))
    return min(capacity, surplus) * STORAGE_AVAILABILITY


def season_water(crop: dict, monthly: list[dict], start_month: int, temp_delta: float = 0.0,
                 rain_factor: float = 1.0, duration_days: int | None = None,
                 awc_mm_per_m: float | None = None) -> SeasonWater | None:
    """Water balance for a crop sown on day 1 of start_month using monthly climatology rows."""
    if not monthly or any(m.get("et0_mm") is None for m in monthly):
        return None
    duration = duration_days or crop["duration"]["typical_days"]
    kc = crop["water_requirement"]["kc"]
    etc = rain = peff = 0.0
    month, day_in_month, year = start_month, 1, 2001
    for d in range(duration):
        row = monthly[month - 1]
        ndays = calendar.monthrange(year, month)[1]
        et0_day = row["et0_mm"] / ndays
        if temp_delta and row.get("t_mean") is not None:
            et0_day *= 1 + temp_delta / (row["t_mean"] + 17.8)
        etc += kc_for_day(d, duration, kc) * et0_day
        p_month = (row.get("precip_mm") or 0.0) * rain_factor
        rain += p_month / ndays
        peff += effective_rainfall_monthly(p_month) / ndays
        day_in_month += 1
        if day_in_month > ndays:
            day_in_month, month = 1, month % 12 + 1
    if crop["water_requirement"].get("requires_standing_water"):
        etc += PADDY_EXTRA_MM_PER_DAY * duration * 0.75  # percolation over the flooded period (~75 % of season)
        stored = 0.0
    else:
        stored = stored_soil_water(crop, monthly, start_month, awc_mm_per_m, rain_factor)
    supply = peff + stored
    return SeasonWater(etc_mm=etc, effective_rain_mm=peff, rain_mm=rain, net_irrigation_mm=max(0.0, etc - supply),
                       duration_days=duration, supply_ratio_rainfed=(supply / etc) if etc else 1.0,
                       stored_soil_water_mm=stored)


def irrigation_supply(irrigation_type: str, capacity_mm: float | None, demand_mm: float) -> tuple[float, str]:
    """Irrigation water assumed available to meet a seasonal deficit, with an explanation."""
    if irrigation_type == "none":
        return 0.0, "Rainfed: no irrigation assumed"
    if capacity_mm is not None:
        return min(capacity_mm, demand_mm), f"Up to {capacity_mm:.0f} mm per season (farmer-provided capacity)"
    if irrigation_type == "full":
        return demand_mm, "Full irrigation with unspecified capacity: deficit assumed fully met (assumption)"
    return 0.5 * demand_mm, "Supplemental irrigation with unspecified capacity: half the deficit assumed met (assumption)"
