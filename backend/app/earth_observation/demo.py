"""Explicitly labelled DEMONSTRATION data generator.

Used only when ENABLE_DEMO_DATA=true *and* a user explicitly requests it (for example when the
platform is shown offline). Values are synthetic, generated from simple latitude-based formulas.
They are never NASA observations: every record carries ``is_demo=True``,
``data_type=demonstration`` and a product identifier that says so. Every downstream result built on
them is flagged as demonstration output.
"""
import calendar
import math
import random
from datetime import date, timedelta

from .base import DataType, ObservationRecord

PRODUCT = "DEMONSTRATION – synthetic values, not real observations"
SRC = "about:demonstration-data"


def _rec(dataset, variable, value, unit, d, lat, lon, temporal, res="synthetic") -> ObservationRecord:
    return ObservationRecord(dataset=dataset, product_id=PRODUCT, variable=variable,
                             value=None if value is None else round(value, 3), unit=unit, observation_date=d,
                             latitude=lat, longitude=lon, spatial_resolution=res, temporal_resolution=temporal,
                             source_url=SRC, data_type=DataType.DEMONSTRATION, quality="demonstration",
                             is_demo=True)


def _climate(lat: float, month: int) -> tuple[float, float, float]:
    """Synthetic (mean temp °C, diurnal range °C, monthly rain mm)."""
    alat = abs(lat)
    t0 = 27.5 - 0.42 * max(0.0, alat - 12)
    amp = min(14.0, 1.2 + 0.28 * alat)
    peak = 5 if alat < 23 else 7
    if lat < 0:
        peak = (peak + 6 - 1) % 12 + 1
    t = t0 + amp * math.cos(2 * math.pi * (month - peak) / 12)
    annual_p = 1250 if alat < 23 else (750 if alat < 40 else 600)
    wet_peak = 7 if lat >= 0 else 1
    w = [math.exp(-((((m - wet_peak + 6) % 12) - 6) ** 2) / 4.5) + 0.12 for m in range(1, 13)]
    rain = annual_p * w[month - 1] / sum(w)
    dtr = 8 + 4 * (1 - w[month - 1] / max(w))
    return t, dtr, rain


def generate(lat: float, lon: float, today: date | None = None) -> dict[str, list[ObservationRecord]]:
    today = today or date.today()
    rng = random.Random(f"{lat:.3f},{lon:.3f}")
    out: dict[str, list[ObservationRecord]] = {k: [] for k in ("nasa_power", "gpm_imerg", "smap", "modis", "srtm")}
    for year in range(today.year - 10, today.year):
        for m in range(1, 13):
            t, dtr, rain = _climate(lat, m)
            t += rng.gauss(0, 0.6) + 0.03 * (year - today.year + 10)
            rain = max(0.0, rain * rng.lognormvariate(0, 0.3))
            d = date(year, m, 1)
            for var, val, unit in (("T2M", t, "C"), ("T2M_MAX", t + dtr / 2, "C"), ("T2M_MIN", t - dtr / 2, "C"),
                                   ("PRECTOTCORR", rain, "mm/month"), ("RH2M", 55 + rain / 12, "%"),
                                   ("ALLSKY_SFC_SW_DWN", 18 + 4 * math.cos(2 * math.pi * (m - 4) / 12), "MJ/m^2/day"),
                                   ("WS2M", 2.2 + rng.random(), "m/s")):
                out["nasa_power"].append(_rec("nasa_power", var, val, unit, d, lat, lon, "monthly"))
    start = today - timedelta(days=730)
    sm = 0.25
    for i in range(730):
        d = start + timedelta(days=i)
        t, dtr, rain_m = _climate(lat, d.month)
        days = calendar.monthrange(d.year, d.month)[1]
        wet_prob = min(0.85, rain_m / days / 6 + 0.05)
        rain = rng.expovariate(wet_prob / (rain_m / days + 0.01)) if rng.random() < wet_prob else 0.0
        tmax = t + dtr / 2 + rng.gauss(0, 1.5)
        out["nasa_power"] += [_rec("nasa_power", "T2M", t + rng.gauss(0, 1), "C", d, lat, lon, "daily"),
                              _rec("nasa_power", "T2M_MAX", tmax, "C", d, lat, lon, "daily"),
                              _rec("nasa_power", "T2M_MIN", t - dtr / 2 + rng.gauss(0, 1), "C", d, lat, lon, "daily"),
                              _rec("nasa_power", "PRECTOTCORR", rain, "mm/day", d, lat, lon, "daily"),
                              _rec("nasa_power", "RH2M", min(98, 50 + rain_m / 6 + rng.gauss(0, 6)), "%", d, lat, lon,
                                   "daily"),
                              _rec("nasa_power", "WS2M", max(0.3, 2.3 + rng.gauss(0, 0.8)), "m/s", d, lat, lon, "daily")]
        out["gpm_imerg"].append(_rec("gpm_imerg", "precipitation", rain * rng.uniform(0.8, 1.2), "mm/day", d, lat,
                                     lon, "daily"))
        sm = min(0.45, max(0.05, sm * 0.97 + rain * 0.004))
        if i % 3 == 0:
            out["smap"].append(_rec("smap", "surface_soil_moisture", sm, "m³/m³", d, lat, lon, "daily"))
        out["smap"].append(_rec("smap", "rootzone_soil_moisture", 0.6 * sm + 0.1, "m³/m³", d, lat, lon, "daily"))
        if i % 16 == 0:
            ndvi = 0.25 + 0.45 * max(0.0, math.sin(2 * math.pi * (d.month - 5) / 12)) + rng.gauss(0, 0.03)
            out["modis"].append(_rec("modis", "ndvi", ndvi, "index", d, lat, lon, "16-day"))
    out["srtm"] += [_rec("srtm", "elevation", 120 + rng.random() * 300, "m", date(2000, 2, 11), lat, lon, "static"),
                    _rec("srtm", "slope", rng.uniform(0.5, 6), "degrees", date(2000, 2, 11), lat, lon, "static")]
    return out
