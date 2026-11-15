"""NASA POWER (Prediction Of Worldwide Energy Resources) adapter.

Docs: https://power.larc.nasa.gov/docs/services/api/
No credentials are required. POWER meteorology is derived from the MERRA-2
assimilation model (~0.5° x 0.625°) and solar parameters from CERES/FLASHFlux
(~1° x 1°), so values describe a grid cell tens of kilometres wide – not an
individual field.

Two requests are made per farm:

* ``fetch_nasa_power`` – the daily point request for the current year
  (1 January to today, UTC time standard) with
  T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M and WS2M. This powers the
  "this year's weather" view and heat-stress day counts.
* a monthly point request for the last ten complete years, which provides the
  long-term climatology (including solar radiation for FAO-56 Penman–Monteith
  ET0) used by the suitability, rotation and simulation engines.
"""
import calendar
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from .base import AdapterResult, DataType, FetchState, ObservationRecord
from .cache import cache_get, cache_key, cache_set
from .http import UpstreamError, request_with_retries

DATASET = "nasa_power"
DAILY_URL_PATH = "/temporal/daily/point"
MONTHLY_URL_PATH = "/temporal/monthly/point"

# Daily request – exactly the parameter set used by the project's reference request.
DAILY_PARAMETERS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M"
# Monthly climatology additionally needs solar radiation for Penman–Monteith ET0.
MONTHLY_PARAMETERS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M,ALLSKY_SFC_SW_DWN"

SOLAR_PARAMS = {"ALLSKY_SFC_SW_DWN"}
MET_RES = "0.5° x 0.625° (MERRA-2 grid)"
SOLAR_RES = "1° x 1° (CERES/FLASHFlux grid)"


def _resolution(param: str) -> str:
    return SOLAR_RES if param in SOLAR_PARAMS else MET_RES


def _base() -> str:
    return get_settings().nasa_power_base_url.rstrip("/")


def _get(db: Session, url: str, params: dict) -> dict:
    """GET with database cache, timeouts and retries; raises UpstreamError with a readable message."""
    key = cache_key("power", url, sorted(params.items()))
    cached = cache_get(db, key)
    if cached is not None:
        return cached
    resp = request_with_retries("GET", url, params=params, timeout=60)
    if resp.status_code != 200:
        try:
            detail = resp.json().get("messages") or resp.json().get("message") or resp.text[:300]
        except ValueError:
            detail = resp.text[:300]
        raise UpstreamError(f"NASA POWER returned HTTP {resp.status_code}: {detail}", resp.status_code)
    data = resp.json()
    # Recent days change as POWER fills its near-real-time record, so cache the current year briefly.
    ttl = 6 if params.get("start", "")[:4] == str(datetime.now(timezone.utc).year) else None
    cache_set(db, key, data, ttl_hours=ttl)
    return data


def fetch_nasa_power(db: Session, latitude: float, longitude: float, start: date | None = None,
                     end: date | None = None) -> tuple[dict, str]:
    """Daily POWER point request (AG community, UTC time standard).

    Mirrors the reference request:
        GET https://power.larc.nasa.gov/api/temporal/daily/point
            ?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M&community=AG
            &longitude=..&latitude=..&start=YYYYMMDD&end=YYYYMMDD&format=JSON&time-standard=UTC
    Defaults to 1 January of the current year up to today (UTC). Returns (json, url).
    """
    today = datetime.now(timezone.utc).date()
    start = start or date(today.year, 1, 1)
    end = min(end or today, today)
    url = f"{_base()}{DAILY_URL_PATH}"
    params = {
        "parameters": DAILY_PARAMETERS,
        "community": get_settings().nasa_power_community,
        "longitude": round(longitude, 4),
        "latitude": round(latitude, 4),
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    data = _get(db, url, params)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return data, f"{url}?{query}"


def fetch_monthly(db: Session, latitude: float, longitude: float, start_year: int, end_year: int
                  ) -> tuple[dict, str]:
    url = f"{_base()}{MONTHLY_URL_PATH}"
    params = {"parameters": MONTHLY_PARAMETERS, "community": get_settings().nasa_power_community,
              "longitude": round(longitude, 4), "latitude": round(latitude, 4), "start": str(start_year),
              "end": str(end_year), "format": "JSON"}
    data = _get(db, url, params)
    return data, f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items())


def parse_power_response(payload: dict, temporal: str, lat: float, lon: float, source_url: str
                         ) -> list[ObservationRecord]:
    """Convert a POWER JSON point response into standard records.

    Monthly responses use keys YYYYMM where MM=13 is the annual value (skipped).
    Monthly precipitation in mm/day is converted to a monthly total in mm.
    Fill values (-999) – including the last few days that POWER has not processed yet –
    become missing values, never zeros.
    """
    fill = payload.get("header", {}).get("fill_value", -999)
    units = {k: v.get("units") for k, v in payload.get("parameters", {}).items()}
    params = payload.get("properties", {}).get("parameter", {})
    records: list[ObservationRecord] = []
    product = f"POWER {temporal} point ({get_settings().nasa_power_community}" + \
              (", UTC)" if temporal == "daily" else ")")
    for name, series in params.items():
        unit = units.get(name)
        for key, value in series.items():
            if temporal == "monthly":
                year, month = int(key[:4]), int(key[4:6])
                if month == 13:
                    continue
                obs_date = date(year, month, 1)
            else:
                obs_date = date(int(key[:4]), int(key[4:6]), int(key[6:8]))
            missing = value is None or value == fill or value <= -998
            v = None if missing else float(value)
            out_unit = unit
            if name == "PRECTOTCORR" and temporal == "monthly" and v is not None and unit in ("mm/day", "mm day-1"):
                v = v * calendar.monthrange(obs_date.year, obs_date.month)[1]
                out_unit = "mm/month"
            records.append(ObservationRecord(
                dataset=DATASET, product_id=product, variable=name, value=v, unit=out_unit,
                observation_date=obs_date, latitude=lat, longitude=lon, spatial_resolution=_resolution(name),
                temporal_resolution=temporal, source_url=source_url, data_type=DataType.WEATHER_CLIMATE_ESTIMATE,
                quality="missing" if missing else "ok", processing_status="missing" if missing else "processed",
            ))
    return records


def fetch(db: Session, lat: float, lon: float, today: date | None = None) -> AdapterResult:
    today = today or datetime.now(timezone.utc).date()
    last_full_year = today.year - 1
    start_year = last_full_year - 9  # ten complete years for climatology and trends
    records: list[ObservationRecord] = []
    messages = []
    try:
        monthly, monthly_url = fetch_monthly(db, lat, lon, start_year, last_full_year)
        records += parse_power_response(monthly, "monthly", lat, lon, monthly_url)
        messages.append(f"Monthly climatology {start_year}–{last_full_year}")
    except UpstreamError as exc:
        return AdapterResult(DATASET, FetchState.FAILED, message=str(exc))
    except (ValueError, KeyError) as exc:
        return AdapterResult(DATASET, FetchState.FAILED, message=f"Unexpected POWER response format: {exc}")
    try:
        daily, daily_url = fetch_nasa_power(db, lat, lon, date(today.year, 1, 1), today)
        daily_recs = parse_power_response(daily, "daily", lat, lon, daily_url)
        records += daily_recs
        valid_days = sorted({r.observation_date for r in daily_recs if r.value is not None})
        if valid_days:
            messages.append(f"daily {valid_days[0]} to {valid_days[-1]} (UTC)")
            pending = (today - valid_days[-1]).days
            if pending > 0:
                messages.append(f"latest {pending} day(s) not yet processed by POWER")
        else:
            messages.append("daily request returned no processed days yet")
    except UpstreamError as exc:
        messages.append(f"daily request failed ({exc})")
    except (ValueError, KeyError) as exc:
        messages.append(f"daily response not understood ({exc})")
    if not any(r.value is not None for r in records):
        return AdapterResult(DATASET, FetchState.NO_DATA, message="POWER returned only fill values for this location")
    return AdapterResult(DATASET, FetchState.COMPLETE, records=records, message="; ".join(messages))
