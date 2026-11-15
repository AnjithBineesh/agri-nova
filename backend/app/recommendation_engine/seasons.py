"""Resolve the growing seasons used for planning."""
from ..agriculture.climate_analyser import EnvironmentProfile

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def season_length_months(s: dict) -> int:
    return (s["end_month"] - s["start_month"]) % 12 + 1


def season_label(s: dict) -> str:
    return f"{s['name']} ({MONTH_NAMES[s['start_month'] - 1]}–{MONTH_NAMES[s['end_month'] - 1]})"


def resolve_seasons(farm_seasons: list[dict] | None, profile: EnvironmentProfile) -> tuple[list[dict], str]:
    if farm_seasons:
        return [dict(s) for s in farm_seasons], "farmer-defined growing seasons"
    if profile.has_climate:
        rain = [m["precip_mm"] or 0 for m in profile.monthly]
        best = max(range(12), key=lambda i: sum(rain[(i + k) % 12] for k in range(5)))
        s1 = best + 1
        s2 = (s1 + 4) % 12 + 1
        return ([{"name": "Main (wet) season", "start_month": s1, "end_month": (s1 + 3) % 12 + 1},
                 {"name": "Second season", "start_month": s2, "end_month": (s2 + 3) % 12 + 1}],
                "auto-detected: wettest 5-month window from climatology and the following 5 months "
                "(define your own seasons in the farm profile for better results)")
    if profile.latitude >= 0:
        default = [{"name": "Warm season", "start_month": 6, "end_month": 10},
                   {"name": "Cool season", "start_month": 11, "end_month": 3}]
    else:
        default = [{"name": "Warm season", "start_month": 11, "end_month": 3},
                   {"name": "Cool season", "start_month": 5, "end_month": 9}]
    return default, "hemisphere default (no climate data or farmer-defined seasons)"
