"""Orchestrates retrieval, polling and storage of Earth observation data for a farm."""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..earth_observation import (
    demo,
    ecostress_service,
    era5_service,
    gaez_service,
    gpm_service,
    landsat_service,
    modis_service,
    nasa_power_service,
    sentinel_service,
    smap_service,
    srtm_service,
)
from ..earth_observation.appeears import AppEEARSClient, parse_point_csv
from ..earth_observation.base import AdapterResult, FetchState, ObservationRecord
from ..earth_observation.http import UpstreamError
from ..earth_observation.registry import (APPEEARS_DATASETS, APPEEARS_TIMESERIES, DATASETS, DISPLAY_NAMES,
                                         DISPLAY_RESOLUTION, STATUS_MESSAGES)
from ..models import DatasetFetchStatus, EarthObservation, Farm

log = logging.getLogger("agrinova.earthdata")

APPEEARS_PARSERS = {
    "smap": smap_service, "modis": modis_service, "landsat": landsat_service, "sentinel2": sentinel_service,
    "ecostress": ecostress_service, "srtm": srtm_service,
}


def _status_row(db: Session, farm: Farm, dataset: str) -> DatasetFetchStatus:
    row = db.scalar(select(DatasetFetchStatus).where(DatasetFetchStatus.farm_id == farm.id,
                                                     DatasetFetchStatus.dataset == dataset))
    if row is None:
        row = DatasetFetchStatus(farm_id=farm.id, dataset=dataset, status="not_requested", record_count=0)
        db.add(row)
    return row


def store_records(db: Session, farm: Farm, dataset: str, records: list[ObservationRecord], is_demo: bool = False
                  ) -> int:
    # Replace previous records of the same dataset (and same demo flag); real data also removes demo data.
    q = delete(EarthObservation).where(EarthObservation.farm_id == farm.id, EarthObservation.dataset == dataset)
    if is_demo:
        q = q.where(EarthObservation.is_demo.is_(True))
    db.execute(q)
    seen = set()
    rows = []
    for r in records:
        key = (r.product_id, r.variable, r.observation_date, r.temporal_resolution)
        if key in seen:
            continue
        seen.add(key)
        rows.append(EarthObservation(
            farm_id=farm.id, dataset=r.dataset, product_id=r.product_id, variable=r.variable, value=r.value,
            unit=r.unit, observation_date=r.observation_date, latitude=r.latitude, longitude=r.longitude,
            resolution=r.spatial_resolution, temporal_resolution=r.temporal_resolution, quality_flag=r.quality,
            data_type=r.data_type.value, source_url=r.source_url[:600] if r.source_url else None,
            processing_status=r.processing_status, is_demo=r.is_demo))
    db.add_all(rows)
    return len(rows)


def _apply_result(db: Session, farm: Farm, result: AdapterResult) -> None:
    now = datetime.now(timezone.utc)
    row = _status_row(db, farm, result.dataset)
    row.last_attempt = now
    row.message = result.message
    row.external_task_id = result.external_task_id
    if result.state == FetchState.COMPLETE or (result.records and result.state == FetchState.NO_DATA):
        row.record_count = store_records(db, farm, result.dataset, result.records)
        dates = [r.observation_date for r in result.records if r.value is not None]
        row.coverage_start = min(dates) if dates else None
        row.coverage_end = max(dates) if dates else None
        row.last_success = now
        row.is_demo = False
    row.status = result.state.value


def refresh(db: Session, farm: Farm, datasets: list[str] | None = None) -> None:
    wanted = set(datasets or DATASETS.keys())
    lat, lon = farm.latitude, farm.longitude
    if "nasa_power" in wanted:
        _apply_result(db, farm, nasa_power_service.fetch(db, lat, lon))
        db.commit()
    if "gpm_imerg" in wanted:
        _apply_result(db, farm, gpm_service.fetch(db, lat, lon))
        db.commit()
    if wanted & set(APPEEARS_DATASETS):
        _submit_appeears(db, farm, wanted & set(APPEEARS_DATASETS))
        db.commit()
    if "era5" in wanted:
        _apply_result(db, farm, era5_service.fetch())
    if "gaez" in wanted:
        _apply_result(db, farm, gaez_service.fetch())
    db.commit()


def _submit_appeears(db: Session, farm: Farm, wanted: set[str]) -> None:
    client = AppEEARSClient()
    now = datetime.now(timezone.utc)
    if not client.configured:
        for ds in wanted:
            row = _status_row(db, farm, ds)
            row.status, row.last_attempt = FetchState.NOT_CONFIGURED.value, now
            row.message = "Configure EARTHDATA_USERNAME and EARTHDATA_PASSWORD to request this dataset via AppEEARS"
        return
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=730)
    point = [{"id": "farm", "latitude": round(farm.latitude, 6), "longitude": round(farm.longitude, 6),
              "category": "farm"}]
    ts = [d for d in APPEEARS_TIMESERIES if d in wanted]
    try:
        if ts:
            layers = [lyr for d in ts for lyr in APPEEARS_PARSERS[d].layers()]
            task_id = client.submit_point_task(f"agrinova-farm{farm.id}-timeseries", layers, point, start, end)
            for d in ts:
                row = _status_row(db, farm, d)
                row.status, row.external_task_id, row.last_attempt = FetchState.PENDING.value, task_id, now
                row.message = f"AppEEARS task {task_id} submitted for {start}–{end}. Processing typically takes " \
                              f"minutes to hours; results are ingested automatically on the next status check."
        if "srtm" in wanted:
            coords = srtm_service.grid_coordinates(farm.latitude, farm.longitude)
            task_id = client.submit_point_task(f"agrinova-farm{farm.id}-terrain", srtm_service.layers(), coords,
                                               date(2000, 2, 11), date(2000, 2, 21))
            row = _status_row(db, farm, "srtm")
            row.status, row.external_task_id, row.last_attempt = FetchState.PENDING.value, task_id, now
            row.message = f"AppEEARS terrain task {task_id} submitted (3x3 SRTM window)."
    except UpstreamError as exc:
        for d in wanted:
            row = _status_row(db, farm, d)
            row.status, row.last_attempt, row.message = FetchState.FAILED.value, now, str(exc)


def poll_pending(db: Session, farm: Farm) -> None:
    rows = db.scalars(select(DatasetFetchStatus).where(
        DatasetFetchStatus.farm_id == farm.id, DatasetFetchStatus.status.in_(["pending", "processing"]))).all()
    if not rows:
        return
    client = AppEEARSClient()
    if not client.configured:
        return
    by_task: dict[str, list[DatasetFetchStatus]] = {}
    for r in rows:
        if r.external_task_id:
            by_task.setdefault(r.external_task_id, []).append(r)
    for task_id, status_rows in by_task.items():
        try:
            state = client.task_status(task_id)
            if state in ("queued", "pending", "processing"):
                for r in status_rows:
                    r.status = "processing" if state == "processing" else "pending"
                continue
            if state != "done":
                for r in status_rows:
                    r.status, r.message = "failed", f"AppEEARS task {task_id} ended with status '{state}'"
                continue
            csvs = client.bundle_csvs(task_id)
            all_rows = [row for text in csvs.values() for row in parse_point_csv(text)]
            for r in status_rows:
                parser = APPEEARS_PARSERS[r.dataset]
                recs = parser.parse(all_rows, farm.latitude, farm.longitude, client.task_url(task_id))
                state_out = FetchState.COMPLETE if recs else FetchState.NO_DATA
                msg = f"AppEEARS task {task_id}: {len(recs)} quality-screened values"
                if not recs:
                    msg += " (no usable observations – e.g. persistent cloud, outside coverage, or no overpass)"
                _apply_result(db, farm, AdapterResult(r.dataset, state_out, recs, msg, task_id))
        except UpstreamError as exc:
            for r in status_rows:
                r.message = f"Status check failed, will retry: {exc}"
    db.commit()


def load_demo(db: Session, farm: Farm) -> list[str]:
    """Load demonstration data only for datasets that have no real observations."""
    if not get_settings().enable_demo_data:
        raise PermissionError("Demonstration data is disabled (ENABLE_DEMO_DATA=false)")
    generated = demo.generate(farm.latitude, farm.longitude)
    loaded = []
    for ds, recs in generated.items():
        real = db.scalar(select(EarthObservation.id).where(EarthObservation.farm_id == farm.id,
                                                           EarthObservation.dataset == ds,
                                                           EarthObservation.is_demo.is_(False)).limit(1))
        if real:
            continue
        row = _status_row(db, farm, ds)
        row.record_count = store_records(db, farm, ds, recs, is_demo=True)
        dates = [r.observation_date for r in recs if r.value is not None]
        row.coverage_start, row.coverage_end = (min(dates), max(dates)) if dates else (None, None)
        row.status, row.is_demo = FetchState.DEMO.value, True
        row.message = "DEMONSTRATION DATA – synthetic values generated locally, not real observations."
        row.last_attempt = datetime.now(timezone.utc)
        loaded.append(ds)
    db.commit()
    return loaded


def status_summary(db: Session, farm: Farm) -> list[dict]:
    rows = {r.dataset: r for r in db.scalars(select(DatasetFetchStatus).where(DatasetFetchStatus.farm_id == farm.id))}
    out = []
    for key, info in DATASETS.items():
        r = rows.get(key)
        default_status = "not_integrated" if info.integration == "interface_only" else "not_requested"
        st = r.status if r else default_status
        out.append({
            **info.as_dict(),
            "display_name": DISPLAY_NAMES.get(key, info.name),
            "display_resolution": DISPLAY_RESOLUTION.get(key, info.spatial_resolution),
            "display_message": STATUS_MESSAGES.get(st, ""),
            "status": st,
            "message": r.message if r else None,
            "last_attempt": r.last_attempt.isoformat() if r and r.last_attempt else None,
            "last_success": r.last_success.isoformat() if r and r.last_success else None,
            "coverage_start": r.coverage_start.isoformat() if r and r.coverage_start else None,
            "coverage_end": r.coverage_end.isoformat() if r and r.coverage_end else None,
            "record_count": r.record_count if r else 0,
            "is_demo": bool(r and r.is_demo),
            "external_task_id": r.external_task_id if r else None,
        })
    return out
