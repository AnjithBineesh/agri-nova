from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agriculture.climate_analyser import build_profile
from ..agriculture.weather_summary import summarise
from ..authentication.deps import get_current_user, get_farm_for_user
from ..config import get_settings
from ..database import get_db
from ..earth_observation.registry import DATASETS
from ..models import EarthObservation, User
from ..services import earth_data_service as eds

router = APIRouter(prefix="/api/farms/{farm_id}/earth-data", tags=["earth observation"])


class RefreshRequest(BaseModel):
    datasets: list[str] | None = None


def _series(db: Session, farm_id: int, dataset: str | None, variables: list[str], start: date | None,
            end: date | None, temporal: str | None = None) -> list[dict]:
    q = select(EarthObservation).where(EarthObservation.farm_id == farm_id, EarthObservation.variable.in_(variables))
    if dataset:
        q = q.where(EarthObservation.dataset == dataset)
    if temporal:
        q = q.where(EarthObservation.temporal_resolution == temporal)
    if start:
        q = q.where(EarthObservation.observation_date >= start)
    if end:
        q = q.where(EarthObservation.observation_date <= end)
    rows = db.scalars(q.order_by(EarthObservation.observation_date)).all()
    return [{"date": r.observation_date.isoformat(), "value": r.value, "unit": r.unit, "dataset": r.dataset,
             "product": r.product_id, "variable": r.variable, "quality": r.quality_flag, "data_type": r.data_type,
             "resolution": r.resolution, "temporal_resolution": r.temporal_resolution, "is_demo": r.is_demo,
             "source_url": r.source_url} for r in rows]


@router.get("")
def overview(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user)
    eds.poll_pending(db, farm)
    profile = build_profile(db, farm)
    return {"farm_id": farm.id, "datasets": eds.status_summary(db, farm), "profile": profile.as_dict(),
            "demo_enabled": get_settings().enable_demo_data,
            "earthdata_configured": get_settings().earthdata_configured,
            "spatial_note": "Weather, rainfall and soil moisture values describe the surrounding area (roughly 10–50 km), "
                            "not your exact field. Vegetation and terrain values are more local (30–250 m)."}


@router.post("/refresh")
def refresh(farm_id: int, body: RefreshRequest | None = None, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    datasets = body.datasets if body else None
    if datasets:
        unknown = [d for d in datasets if d not in DATASETS]
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown datasets: {', '.join(unknown)}")
    eds.refresh(db, farm, datasets)
    return {"datasets": eds.status_summary(db, farm)}


@router.get("/status")
def fetch_status(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user)
    eds.poll_pending(db, farm)
    return {"datasets": eds.status_summary(db, farm)}


@router.post("/demo")
def load_demo(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    try:
        loaded = eds.load_demo(db, farm)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return {"loaded": loaded, "warning": "DEMONSTRATION DATA – synthetic values, not real observations.",
            "datasets": eds.status_summary(db, farm)}


@router.delete("/demo")
def clear_demo(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    from sqlalchemy import delete

    from ..models import DatasetFetchStatus
    db.execute(delete(EarthObservation).where(EarthObservation.farm_id == farm.id, EarthObservation.is_demo.is_(True)))
    db.execute(delete(DatasetFetchStatus).where(DatasetFetchStatus.farm_id == farm.id,
                                                DatasetFetchStatus.is_demo.is_(True)))
    db.commit()
    return {"datasets": eds.status_summary(db, farm)}


@router.get("/rainfall")
def rainfall(farm_id: int, start: date | None = None, end: date | None = None,
             aggregate: str = Query("monthly", pattern="^(daily|monthly)$"), user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    imerg = _series(db, farm_id, "gpm_imerg", ["precipitation"], start, end)
    power_m = _series(db, farm_id, "nasa_power", ["PRECTOTCORR"], start, end, "monthly")
    power_d = _series(db, farm_id, "nasa_power", ["PRECTOTCORR"], start, end, "daily")
    if aggregate == "daily":
        return {"gpm_imerg": imerg, "nasa_power": power_d}
    acc = defaultdict(lambda: {"sum": 0.0, "n": 0, "final": 0, "demo": False})
    for r in imerg:
        if r["value"] is None:
            continue
        k = r["date"][:7]
        acc[k]["sum"] += r["value"]
        acc[k]["n"] += 1
        acc[k]["final"] += 1 if "Final" in (r["product"] or "") else 0
        acc[k]["demo"] |= r["is_demo"]
    imerg_monthly = [{"month": k, "value": round(v["sum"], 1), "days": v["n"],
                      "quality": "final_run" if v["final"] == v["n"] else "includes_late_run",
                      "is_demo": v["demo"]} for k, v in sorted(acc.items())]
    return {"gpm_imerg_monthly": imerg_monthly,
            "nasa_power_monthly": [{"month": r["date"][:7], "value": None if r["value"] is None else round(r["value"], 1),
                                    "is_demo": r["is_demo"]} for r in power_m],
            "units": "mm/month"}


@router.get("/temperature")
def temperature(farm_id: int, start: date | None = None, end: date | None = None,
                temporal: str = Query("monthly", pattern="^(daily|monthly)$"), user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    out = {v: _series(db, farm_id, "nasa_power", [v], start, end, temporal) for v in ("T2M", "T2M_MAX", "T2M_MIN")}
    lst = _series(db, farm_id, "ecostress", ["land_surface_temperature"], start, end)
    return {"air_temperature": out, "land_surface_temperature": lst, "units": "°C"}


@router.get("/soil-moisture")
def soil_moisture(farm_id: int, start: date | None = None, end: date | None = None,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    return {"surface": _series(db, farm_id, "smap", ["surface_soil_moisture"], start, end),
            "l4_surface": _series(db, farm_id, "smap", ["l4_surface_soil_moisture"], start, end),
            "rootzone": _series(db, farm_id, "smap", ["rootzone_soil_moisture"], start, end),
            "units": "m³/m³", "note": "Surface (~0–5 cm) soil moisture at 9 km; root zone (0–100 cm) is a model "
                                      "estimate. Neither equals laboratory water-holding capacity."}


@router.get("/vegetation")
def vegetation(farm_id: int, start: date | None = None, end: date | None = None,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    return {"modis_ndvi": _series(db, farm_id, "modis", ["ndvi"], start, end),
            "modis_evi": _series(db, farm_id, "modis", ["evi"], start, end),
            "landsat_ndvi": _series(db, farm_id, "landsat", ["ndvi"], start, end),
            "sentinel2_ndvi": _series(db, farm_id, "sentinel2", ["ndvi"], start, end),
            "evapotranspiration": _series(db, farm_id, "ecostress", ["evapotranspiration"], start, end)}


@router.get("/terrain")
def terrain(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    return {"terrain": _series(db, farm_id, "srtm", ["elevation", "slope"], None, None)}


@router.get("/weather")
def weather_this_year(farm_id: int, year: int | None = None, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Daily NASA POWER weather for the current (or given) year, compared with the farm's 10-year normal."""
    farm = get_farm_for_user(farm_id, db, user)
    today = datetime.now(timezone.utc).date()
    year = year or today.year
    rows = db.scalars(select(EarthObservation).where(
        EarthObservation.farm_id == farm.id, EarthObservation.dataset == "nasa_power",
        EarthObservation.temporal_resolution == "daily",
        EarthObservation.observation_date >= date(year, 1, 1),
        EarthObservation.observation_date <= date(year, 12, 31))).all()
    if not rows:
        # Fall back to the most recent year that has daily data (e.g. demonstration data or early January).
        latest = db.scalar(select(EarthObservation.observation_date).where(
            EarthObservation.farm_id == farm.id, EarthObservation.dataset == "nasa_power",
            EarthObservation.temporal_resolution == "daily").order_by(EarthObservation.observation_date.desc()).limit(1))
        if latest and latest.year != year:
            return weather_this_year(farm_id, latest.year, user, db)
    daily: dict = defaultdict(dict)
    for r in rows:
        daily[r.observation_date][r.variable] = r.value
    profile = build_profile(db, farm)
    out = summarise(daily, profile.monthly if profile.has_climate else None, min(today, date(year, 12, 31)))
    out.update({"year": year, "is_demo": any(r.is_demo for r in rows),
                "source": "Daily weather record", "resolution": "about 50 km",
                "note": "Daily values (UTC days) describe the surrounding area of about 50 km, not your exact field. "
                        "The most recent days can be missing until they are processed."})
    return out
