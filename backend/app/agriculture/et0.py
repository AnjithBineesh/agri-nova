"""Reference evapotranspiration following FAO Irrigation & Drainage Paper 56 (Allen et al., 1998)."""
import math

GSC = 0.0820  # solar constant, MJ m-2 min-1
SIGMA = 4.903e-9  # Stefan-Boltzmann, MJ K-4 m-2 day-1


def extraterrestrial_radiation(lat_deg: float, doy: int) -> float:
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * GSC * dr * (ws * math.sin(phi) * math.sin(delta)
                                             + math.cos(phi) * math.cos(delta) * math.sin(ws))


def sat_vapour_pressure(t: float) -> float:
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def hargreaves(tmean: float, tmax: float, tmin: float, ra: float) -> float:
    """FAO-56 eq. 52, mm/day."""
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * ra * 0.408)


def penman_monteith(tmax: float, tmin: float, rh_mean: float, u2: float, rs: float, lat: float, doy: int,
                    elevation_m: float = 0.0) -> float:
    """FAO-56 Penman-Monteith (eq. 6) with G≈0, mm/day. rs in MJ m-2 day-1, rh in %, u2 in m/s."""
    tmean = (tmax + tmin) / 2
    p = 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * p
    es = (sat_vapour_pressure(tmax) + sat_vapour_pressure(tmin)) / 2
    ea = es * max(0.0, min(rh_mean, 100.0)) / 100
    delta = 4098 * sat_vapour_pressure(tmean) / (tmean + 237.3) ** 2
    ra = extraterrestrial_radiation(lat, doy)
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = 0.77 * rs
    ratio = min(rs / rso, 1.0) if rso > 0 else 0.5
    rnl = SIGMA * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * math.sqrt(ea)) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    return max(0.0, num / (delta + gamma * (1 + 0.34 * u2)))


MID_MONTH_DOY = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]


def effective_rainfall_monthly(p_mm: float) -> float:
    """FAO/AGLW empirical formula (Brouwer & Heibloem 1986) for monthly effective rainfall."""
    if p_mm <= 0:
        return 0.0
    return max(0.0, 0.8 * p_mm - 25) if p_mm > 75 else max(0.0, 0.6 * p_mm - 10)
