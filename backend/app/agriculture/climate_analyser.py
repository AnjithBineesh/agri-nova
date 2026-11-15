"""Builds a farm environmental profile from stored Earth observations.

The profile is the single input the suitability, rotation and simulation engines use for
climate, water and terrain conditions. Every value keeps its provenance.
"""
import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EarthObservation, Farm
from .et0 import MID_MONTH_DOY, extraterrestrial_radiation, hargreaves, penman_monteith

MONTHS = list(range(1, 13))


@dataclass
class EnvironmentProfile:
    farm_id: int
    latitude: float
    longitude: float
    is_demo: bool = False
    monthly: list[dict] = field(default_factory=list)  # 12 climatology rows
    annual: list[dict] = field(default_factory=list)
    annual_precip_mean: float | None = None
    annual_precip_cv: float | None = None
    temp_trend_c_per_decade: float | None = None
    precip_trend_mm_per_decade: float | None = None
    daily_tmax: list[tuple[date, float]] = field(default_factory=list)
    soil_moisture: dict = field(default_factory=dict)
    vegetation: dict = field(default_factory=dict)
    terrain: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    @property
    def has_climate(self) -> bool:
        return bool(self.monthly) and all(m.get("t_mean") is not None for m in self.monthly)

    def season_months(self, start: int, end: int) -> list[int]:
        n = (end - start) % 12 + 1
        return [((start - 1 + i) % 12) + 1 for i in range(n)]

    def season_stats(self, months: list[int], temp_delta: float = 0.0, rain_factor: float = 1.0) -> dict | None:
        if not self.has_climate:
            return None
        rows = [self.monthly[m - 1] for m in months]
        t_mean = statistics.mean(r["t_mean"] for r in rows) + temp_delta
        t_max = max(r["t_max"] for r in rows) + temp_delta
        t_min = min(r["t_min"] for r in rows) + temp_delta
        rain = sum((r["precip_mm"] or 0) for r in rows) * rain_factor
        et0 = sum(self._et0_scaled(r, temp_delta) for r in rows)
        return {"months": months, "t_mean": t_mean, "t_max_month": t_max, "t_min_month": t_min, "rain_mm": rain,
                "et0_mm": et0}

    def _et0_scaled(self, row: dict, temp_delta: float) -> float:
        et0 = row["et0_mm"] or 0.0
        if temp_delta and row["t_mean"] is not None:
            # Sensitivity of Hargreaves ET0 to mean temperature: d ln ET0 / dT = 1 / (T + 17.8)
            et0 *= 1 + temp_delta / (row["t_mean"] + 17.8)
        return et0

    def heat_stress_fraction(self, months: list[int], threshold_c: float, temp_delta: float = 0.0) -> float | None:
        days = [t for d, t in self.daily_tmax if d.month in months]
        if not days:
            return None
        return sum(1 for t in days if t + temp_delta > threshold_c) / len(days)

    def as_dict(self) -> dict:
        return {
            "farm_id": self.farm_id, "latitude": self.latitude, "longitude": self.longitude, "is_demo": self.is_demo,
            "monthly": self.monthly, "annual": self.annual, "annual_precip_mean": self.annual_precip_mean,
            "annual_precip_cv": self.annual_precip_cv, "temp_trend_c_per_decade": self.temp_trend_c_per_decade,
            "precip_trend_mm_per_decade": self.precip_trend_mm_per_decade, "soil_moisture": self.soil_moisture,
            "vegetation": self.vegetation, "terrain": self.terrain, "sources": self.sources, "gaps": self.gaps,
            "has_climate": self.has_climate,
        }


def _slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 5:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


def build_profile(db: Session, farm: Farm) -> EnvironmentProfile:
    obs = db.scalars(select(EarthObservation).where(EarthObservation.farm_id == farm.id,
                                                    EarthObservation.value.is_not(None))).all()
    prof = EnvironmentProfile(farm_id=farm.id, latitude=farm.latitude, longitude=farm.longitude)
    by: dict[tuple[str, str, str], list[EarthObservation]] = defaultdict(list)
    for o in obs:
        by[(o.dataset, o.variable, o.temporal_resolution)].append(o)
    used_demo = False

    # ---- POWER monthly climatology -------------------------------------------------------------
    def monthly_series(var: str) -> dict[tuple[int, int], float]:
        return {(o.observation_date.year, o.observation_date.month): o.value for o in by[("nasa_power", var, "monthly")]}

    power = {v: monthly_series(v) for v in ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN",
                                            "WS2M")}
    power_obs = by[("nasa_power", "T2M", "monthly")]
    if power_obs:
        used_demo |= any(o.is_demo for o in power_obs)
        solar_unit = next((o.unit for o in by[("nasa_power", "ALLSKY_SFC_SW_DWN", "monthly")]), None)
        prof.sources["climate"] = {
            "dataset": "Weather record" + (" (demonstration)" if used_demo else ""),
            "product": power_obs[0].product_id, "resolution": power_obs[0].resolution,
            "period": f"{min(k[0] for k in power['T2M'])}–{max(k[0] for k in power['T2M'])}",
            "data_type": power_obs[0].data_type}

    # ---- Rainfall: prefer GPM IMERG (satellite) monthly totals of complete months -----------------
    imerg = by[("gpm_imerg", "precipitation", "daily")]
    imerg_monthly: dict[tuple[int, int], float] = {}
    if imerg:
        acc: dict[tuple[int, int], list[float]] = defaultdict(list)
        for o in imerg:
            acc[(o.observation_date.year, o.observation_date.month)].append(o.value)
        for (y, m), vals in acc.items():
            if len(vals) >= calendar.monthrange(y, m)[1] - 1:
                imerg_monthly[(y, m)] = sum(vals)
    use_imerg = len(imerg_monthly) >= 12 and len({m for _, m in imerg_monthly}) == 12
    rain_series = imerg_monthly if use_imerg else power["PRECTOTCORR"]
    if use_imerg:
        used_demo |= any(o.is_demo for o in imerg)
        prof.sources["rainfall"] = {"dataset": "Observed rainfall record" + (" (demonstration)" if imerg[0].is_demo else ""),
                                    "product": imerg[0].product_id, "resolution": imerg[0].resolution,
                                    "months_used": len(imerg_monthly), "data_type": imerg[0].data_type}
    elif power["PRECTOTCORR"]:
        prof.sources["rainfall"] = {"dataset": "Weather record", "resolution": "about 50 km",
                                    "data_type": "weather_climate_estimate",
                                    "note": "Satellite rainfall not available; weather-record rainfall used"}

    elevation = next((o.value for o in by[("srtm", "elevation", "static (Feb 2000)")] + by[("srtm", "elevation", "static")]),
                     None)

    if power["T2M"]:
        for m in MONTHS:
            def clim(series: dict, month=m):
                vals = [v for (y, mm), v in series.items() if mm == month]
                return statistics.mean(vals) if vals else None

            row = {"month": m, "t_mean": clim(power["T2M"]), "t_max": clim(power["T2M_MAX"]),
                   "t_min": clim(power["T2M_MIN"]), "precip_mm": clim(rain_series), "rh": clim(power["RH2M"]),
                   "solar": clim(power["ALLSKY_SFC_SW_DWN"]), "wind": clim(power["WS2M"])}
            if row["solar"] is not None and solar_unit and "kw" in solar_unit.lower():
                row["solar"] *= 3.6  # kWh m-2 day-1 -> MJ m-2 day-1
            days = calendar.monthrange(2001, m)[1]
            et0_day, method = None, None
            if None not in (row["t_max"], row["t_min"], row["rh"], row["wind"], row["solar"]):
                et0_day = penman_monteith(row["t_max"], row["t_min"], row["rh"], row["wind"], row["solar"],
                                          farm.latitude, MID_MONTH_DOY[m - 1], elevation or 0.0)
                method = "FAO-56 Penman-Monteith"
            elif None not in (row["t_mean"], row["t_max"], row["t_min"]):
                et0_day = hargreaves(row["t_mean"], row["t_max"], row["t_min"],
                                     extraterrestrial_radiation(farm.latitude, MID_MONTH_DOY[m - 1]))
                method = "Hargreaves (FAO-56 eq. 52)"
            row["et0_mm"] = round(et0_day * days, 1) if et0_day is not None else None
            row["et0_method"] = method
            for k in ("t_mean", "t_max", "t_min", "precip_mm", "rh", "solar", "wind"):
                if row[k] is not None:
                    row[k] = round(row[k], 2)
            prof.monthly.append(row)
        years = sorted({y for y, _ in power["T2M"]})
        for y in years:
            temps = [power["T2M"].get((y, m)) for m in MONTHS]
            # Prefer IMERG months; fill months outside the IMERG record with POWER so years stay comparable.
            rains = [rain_series.get((y, m)) if rain_series.get((y, m)) is not None
                     else power["PRECTOTCORR"].get((y, m)) for m in MONTHS]
            prof.annual.append({
                "year": y,
                "t_mean": round(statistics.mean(temps), 2) if None not in temps else None,
                "precip_mm": round(sum(rains), 1) if None not in rains else None,
            })
        prec = [a["precip_mm"] for a in prof.annual if a["precip_mm"] is not None]
        if prec:
            prof.annual_precip_mean = round(statistics.mean(prec), 1)
            prof.annual_precip_cv = round(statistics.pstdev(prec) / statistics.mean(prec), 3) if len(prec) > 2 else None
        if not use_imerg and not prec and prof.monthly:
            prof.annual_precip_mean = round(sum(m["precip_mm"] or 0 for m in prof.monthly), 1)
        ty = [(a["year"], a["t_mean"]) for a in prof.annual if a["t_mean"] is not None]
        py = [(a["year"], a["precip_mm"]) for a in prof.annual if a["precip_mm"] is not None]
        s = _slope([x for x, _ in ty], [v for _, v in ty])
        prof.temp_trend_c_per_decade = round(s * 10, 2) if s is not None else None
        s = _slope([x for x, _ in py], [v for _, v in py])
        prof.precip_trend_mm_per_decade = round(s * 10, 1) if s is not None else None
        if prof.annual_precip_mean is None and prof.monthly:
            prof.annual_precip_mean = round(sum(m["precip_mm"] or 0 for m in prof.monthly), 1)
    else:
        prof.gaps.append("No weather data yet: temperature, rainfall and water-demand assessments are unavailable")

    prof.daily_tmax = sorted((o.observation_date, o.value) for o in by[("nasa_power", "T2M_MAX", "daily")])

    # ---- SMAP soil moisture ---------------------------------------------------------------------
    def series(dataset: str, variable: str) -> list[EarthObservation]:
        return sorted([o for (d, v, _), lst in by.items() if d == dataset and v == variable for o in lst],
                      key=lambda o: o.observation_date)

    surf = series("smap", "surface_soil_moisture")
    root = series("smap", "rootzone_soil_moisture")
    if surf or root:
        used_demo |= any(o.is_demo for o in surf + root)
        sm = {}
        if surf:
            monthly = defaultdict(list)
            for o in surf:
                monthly[o.observation_date.month].append(o.value)
            sm["surface"] = {"mean": round(statistics.mean(o.value for o in surf), 3),
                             "latest": surf[-1].value, "latest_date": surf[-1].observation_date.isoformat(),
                             "monthly_mean": {m: round(statistics.mean(v), 3) for m, v in sorted(monthly.items())},
                             "product": surf[-1].product_id, "resolution": surf[-1].resolution,
                             "depth": "~0–5 cm", "data_type": surf[-1].data_type}
        if root:
            sm["rootzone"] = {"mean": round(statistics.mean(o.value for o in root), 3), "latest": root[-1].value,
                              "latest_date": root[-1].observation_date.isoformat(), "product": root[-1].product_id,
                              "resolution": root[-1].resolution, "depth": "0–100 cm",
                              "data_type": root[-1].data_type}
        prof.soil_moisture = sm
    else:
        prof.gaps.append("No soil moisture data available")

    # ---- Vegetation -------------------------------------------------------------------------------
    ndvi = []
    for ds in ("sentinel2", "landsat", "modis"):
        ndvi += [(o, ds) for o in series(ds, "ndvi")]
    if ndvi:
        used_demo |= any(o.is_demo for o, _ in ndvi)
        latest, ds = max(ndvi, key=lambda t: t[0].observation_date)
        prof.vegetation = {"ndvi_latest": latest.value, "ndvi_latest_date": latest.observation_date.isoformat(),
                           "source": ds, "source_label": {"modis": "250 m", "landsat": "30 m", "sentinel2": "30 m"}[ds], "product": latest.product_id, "resolution": latest.resolution,
                           "count": len(ndvi)}
    else:
        prof.gaps.append("No cloud-free vegetation index observations available")

    # ---- Terrain ----------------------------------------------------------------------------------
    slope = next((o for o in series("srtm", "slope")), None)
    elev = next((o for o in series("srtm", "elevation")), None)
    if elev or slope:
        used_demo |= any(o.is_demo for o in (elev, slope) if o)
        prof.terrain = {"elevation_m": elev.value if elev else None, "slope_deg": slope.value if slope else None,
                        "resolution": (slope or elev).resolution, "product": (slope or elev).product_id}
    else:
        prof.gaps.append("No terrain data: slope-related erosion considerations use farmer input only")

    prof.is_demo = used_demo
    return prof
