"""Year-to-date weather summary from NASA POWER daily data, compared with the farm's climatology."""
import calendar
import statistics
from datetime import date

HEAT_THRESHOLD_C = 35.0
WET_DAY_MM = 1.0


def summarise(daily: dict[date, dict], monthly_climatology: list[dict] | None, today: date) -> dict:
    """daily: {date: {"T2M":.., "T2M_MAX":.., "T2M_MIN":.., "PRECTOTCORR":.., "RH2M":.., "WS2M":..}}"""
    days = sorted(d for d, v in daily.items() if any(x is not None for x in v.values()))
    if not days:
        return {"available": False, "days": [], "message": "No daily weather values for this year yet."}
    first, last = days[0], days[-1]
    rows = []
    rain_total, wet_days, dry_run, longest_dry = 0.0, 0, 0, 0
    tmeans, hot_days = [], 0
    hottest = coldest = None
    for d in days:
        v = daily[d]
        p = v.get("PRECTOTCORR")
        if p is not None:
            rain_total += p
            if p >= WET_DAY_MM:
                wet_days += 1
                dry_run = 0
            else:
                dry_run += 1
                longest_dry = max(longest_dry, dry_run)
        if v.get("T2M") is not None:
            tmeans.append(v["T2M"])
        tx, tn = v.get("T2M_MAX"), v.get("T2M_MIN")
        if tx is not None:
            hot_days += tx > HEAT_THRESHOLD_C
            if hottest is None or tx > hottest[1]:
                hottest = (d, tx)
        if tn is not None and (coldest is None or tn < coldest[1]):
            coldest = (d, tn)
        rows.append({"date": d.isoformat(), "t2m": v.get("T2M"), "tmax": tx, "tmin": tn, "precip": p,
                     "rh": v.get("RH2M"), "wind": v.get("WS2M")})
    # Normal rainfall and temperature for the same calendar period, from the 10-year monthly climatology.
    normal_rain = normal_temp = None
    if monthly_climatology and all(m.get("precip_mm") is not None for m in monthly_climatology):
        normal_rain, temps, n = 0.0, [], 0
        for m in range(first.month, last.month + 1):
            mdays = calendar.monthrange(last.year, m)[1]
            covered = mdays if m < last.month else last.day
            if m == first.month:
                covered -= first.day - 1
            normal_rain += monthly_climatology[m - 1]["precip_mm"] * covered / mdays
            if monthly_climatology[m - 1].get("t_mean") is not None:
                temps += [monthly_climatology[m - 1]["t_mean"]] * covered
            n += covered
        normal_temp = statistics.mean(temps) if temps else None
    mean_t = statistics.mean(tmeans) if tmeans else None
    rain_pct = round(100 * rain_total / normal_rain) if normal_rain else None
    if rain_pct is None:
        rain_note = "No long-term normal available for comparison."
    elif rain_pct < 80:
        rain_note = f"Drier than normal: {rain_pct}% of the usual rainfall for this period."
    elif rain_pct > 120:
        rain_note = f"Wetter than normal: {rain_pct}% of the usual rainfall for this period."
    else:
        rain_note = f"Close to normal: {rain_pct}% of the usual rainfall for this period."
    return {
        "available": True, "first_day": first.isoformat(), "last_day": last.isoformat(),
        "days_pending": max(0, (today - last).days),
        "rain_total_mm": round(rain_total, 1), "rain_normal_mm": round(normal_rain, 1) if normal_rain else None,
        "rain_percent_of_normal": rain_pct, "rain_note": rain_note, "wet_days": wet_days,
        "longest_dry_spell_days": longest_dry, "mean_temp_c": round(mean_t, 1) if mean_t is not None else None,
        "normal_temp_c": round(normal_temp, 1) if normal_temp is not None else None,
        "temp_anomaly_c": round(mean_t - normal_temp, 1) if mean_t is not None and normal_temp is not None else None,
        "hot_days": hot_days, "heat_threshold_c": HEAT_THRESHOLD_C,
        "hottest": {"date": hottest[0].isoformat(), "value": round(hottest[1], 1)} if hottest else None,
        "coldest": {"date": coldest[0].isoformat(), "value": round(coldest[1], 1)} if coldest else None,
        "days": rows,
    }
