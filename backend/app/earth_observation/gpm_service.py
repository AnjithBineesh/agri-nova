"""GPM IMERG precipitation adapter (via the GES DISC "Giovanni in the Cloud" time-series API).

* IMERG Final Run (GPM_3IMERGDF V07): research-quality, gauge-adjusted, ~3.5 month latency.
* IMERG Late Run (GPM_3IMERGDL V07): near-real-time (~14 h latency), no monthly gauge
  adjustment – used only to fill the period not yet covered by the Final Run.
Both are 0.1° x 0.1° (~11 km at the equator) daily accumulations derived from half-hourly data.
Requires an Earthdata Login bearer token.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..config import get_settings
from .base import AdapterResult, DataType, FetchState, ObservationRecord
from .cache import cache_get, cache_key, cache_set
from .earthdata_auth import get_edl_token
from .http import UpstreamError, request_with_retries

DATASET = "gpm_imerg"
RESOLUTION = "0.1° x 0.1° (~11 km)"


def parse_giovanni_csv(text: str) -> tuple[dict, list[tuple[date, float | None]]]:
    """Parse a Giovanni time-series CSV (metadata key=value lines, then a Timestamp header)."""
    meta: dict[str, str] = {}
    rows: list[tuple[date, float | None]] = []
    in_data = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not in_data:
            if line.lower().startswith("timestamp"):
                in_data = True
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip().lower()] = v.strip()
            elif "," in line:
                k, v = line.split(",", 1)
                meta[k.strip().lower()] = v.strip()
            continue
        ts, _, val = line.partition(",")
        try:
            d = datetime.fromisoformat(ts.strip().replace("Z", "")).date()
        except ValueError:
            continue
        try:
            v = float(val)
            fill = meta.get("fill_value") or meta.get("fillvalue")
            if v < -999 or (fill and abs(v - float(fill)) < 1e-6):
                v = None
        except ValueError:
            v = None
        rows.append((d, v))
    return meta, rows


def _query(db: Session, token: str, variable: str, lat: float, lon: float, start: date, end: date
           ) -> tuple[str, dict, list]:
    s = get_settings()
    params = {"data": variable, "location": f"[{lat:.4f},{lon:.4f}]",
              "time": f"{start.isoformat()}T00:00:00/{end.isoformat()}T23:59:59"}
    source_url = (f"{s.giovanni_timeseries_url}?data={variable}&location={params['location']}"
                  f"&time={params['time']}")
    key = cache_key("giovanni", source_url)
    cached = cache_get(db, key)
    if cached is None:
        resp = request_with_retries("GET", s.giovanni_timeseries_url, params=params,
                                    headers={"Authorization": f"Bearer {token}"}, timeout=120)
        if resp.status_code in (401, 403):
            raise UpstreamError("Giovanni rejected the Earthdata token (check EDL credentials and that GES DISC "
                                "applications are authorised for your account)", resp.status_code)
        if resp.status_code != 200:
            raise UpstreamError(f"Giovanni returned HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)
        cached = resp.text
        cache_set(db, key, cached)
    meta, rows = parse_giovanni_csv(cached)
    return source_url, meta, rows


def fetch(db: Session, lat: float, lon: float, today: date | None = None) -> AdapterResult:
    s = get_settings()
    today = today or date.today()
    try:
        token = get_edl_token()
    except UpstreamError as exc:
        return AdapterResult(DATASET, FetchState.FAILED, message=str(exc))
    if not token:
        return AdapterResult(DATASET, FetchState.NOT_CONFIGURED,
                             message="Set EARTHDATA_TOKEN or EARTHDATA_USERNAME/PASSWORD to retrieve IMERG rainfall")
    final_end = today - timedelta(days=110)  # Final Run latency is ~3.5 months
    final_start = date(final_end.year - 3, 1, 1)
    records: list[ObservationRecord] = []
    messages = []
    try:
        url, meta, rows = _query(db, token, s.gpm_imerg_final_variable, lat, lon, final_start, final_end)
        unit = meta.get("unit") or meta.get("units") or "mm/day"
        for d, v in rows:
            records.append(ObservationRecord(
                dataset=DATASET, product_id="GPM_3IMERGDF.07 (Final Run)", variable="precipitation", value=v,
                unit="mm/day" if "mm" in unit else unit, observation_date=d, latitude=lat, longitude=lon,
                spatial_resolution=RESOLUTION, temporal_resolution="daily", source_url=url,
                data_type=DataType.SATELLITE_OBSERVATION, quality="final_run" if v is not None else "missing"))
        messages.append(f"Final Run {final_start}–{final_end}: {len(rows)} days")
        last_final = max((d for d, _ in rows), default=final_end)
        late_start = last_final + timedelta(days=1)
        late_end = today - timedelta(days=2)
        if late_start <= late_end:
            try:
                url, meta, rows = _query(db, token, s.gpm_imerg_late_variable, lat, lon, late_start, late_end)
                for d, v in rows:
                    records.append(ObservationRecord(
                        dataset=DATASET, product_id="GPM_3IMERGDL.07 (Late Run, near-real-time)",
                        variable="precipitation", value=v, unit="mm/day", observation_date=d, latitude=lat,
                        longitude=lon, spatial_resolution=RESOLUTION, temporal_resolution="daily", source_url=url,
                        data_type=DataType.SATELLITE_OBSERVATION,
                        quality="late_run_provisional" if v is not None else "missing"))
                messages.append(f"Late Run {late_start}–{late_end}: {len(rows)} days (provisional)")
            except UpstreamError as exc:
                messages.append(f"Late Run unavailable: {exc}")
    except UpstreamError as exc:
        return AdapterResult(DATASET, FetchState.FAILED, message=str(exc))
    if not any(r.value is not None for r in records):
        return AdapterResult(DATASET, FetchState.NO_DATA, records=records, message="; ".join(messages))
    return AdapterResult(DATASET, FetchState.COMPLETE, records=records, message="; ".join(messages))
