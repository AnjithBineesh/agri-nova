import csv
import io
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agriculture.climate_analyser import build_profile
from ..authentication.deps import require_roles
from ..database import get_db
from ..models import DatasetFetchStatus, Farm, Organisation, Recommendation, User
from ..services.farm_context import latest_soil, soil_dict
from ..agriculture import soil_analyser

router = APIRouter(prefix="/api/organisations", tags=["organisation portal"])
org_staff = require_roles("organisation")


def _org(user: User, db: Session) -> Organisation:
    if user.organisation_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Your account is not linked to an organisation")
    return db.get(Organisation, user.organisation_id)


def _farms(org: Organisation, db: Session) -> list[Farm]:
    return db.scalars(select(Farm).join(User, Farm.user_id == User.id)
                      .where(User.organisation_id == org.id).order_by(Farm.country, Farm.farm_name)).all()


def _summary(f: Farm, db: Session) -> dict:
    prof = build_profile(db, f)
    soil = soil_dict(latest_soil(db, f))
    sa = soil_analyser.assess(soil)
    statuses = db.scalars(select(DatasetFetchStatus).where(DatasetFetchStatus.farm_id == f.id)).all()
    rec = db.scalar(select(Recommendation).where(Recommendation.farm_id == f.id)
                    .order_by(Recommendation.saved.desc(), Recommendation.created_at.desc()).limit(1))
    t_ann = statistics.mean(m["t_mean"] for m in prof.monthly) if prof.has_climate else None
    return {"farm_id": f.id, "farm_name": f.farm_name, "owner": f.owner.name, "country": f.country, "state": f.state,
            "region": f.region, "latitude": f.latitude, "longitude": f.longitude, "area_ha": f.area_ha,
            "irrigation_type": f.irrigation_type, "current_crop": f.current_crop,
            "annual_rainfall_mm": prof.annual_precip_mean, "mean_temperature_c": round(t_ann, 1) if t_ann else None,
            "surface_soil_moisture": (prof.soil_moisture.get("surface") or {}).get("mean"),
            "soil_limitations": sa.get("limitations", []), "soil_data": bool(soil),
            "datasets_complete": sum(1 for s in statuses if s.status == "complete"),
            "uses_demo_data": prof.is_demo,
            "latest_strategy": ({"name": rec.strategy_name, "sequence": rec.explanation.get("sequence_text"),
                                 "saved": rec.saved} if rec else None)}


@router.get("/me")
def my_org(user: User = Depends(org_staff), db: Session = Depends(get_db)):
    org = _org(user, db)
    members = db.scalars(select(User).where(User.organisation_id == org.id)).all()
    return {"id": org.id, "name": org.name, "country": org.country,
            "members": [{"id": m.id, "name": m.name, "role": m.role, "farms": len(m.farms)} for m in members]}


@router.get("/me/farms")
def org_farms(user: User = Depends(org_staff), db: Session = Depends(get_db)):
    org = _org(user, db)
    return {"farms": [_summary(f, db) for f in _farms(org, db)]}


@router.get("/me/regional")
def regional(user: User = Depends(org_staff), db: Session = Depends(get_db)):
    org = _org(user, db)
    groups = defaultdict(list)
    for s in (_summary(f, db) for f in _farms(org, db)):
        groups[(s["country"], s["state"] or "—")].append(s)
    out = []
    for (country, state), fs in sorted(groups.items()):
        rain = [f["annual_rainfall_mm"] for f in fs if f["annual_rainfall_mm"] is not None]
        temp = [f["mean_temperature_c"] for f in fs if f["mean_temperature_c"] is not None]
        lims = defaultdict(int)
        for f in fs:
            for lim in f["soil_limitations"]:
                lims[lim] += 1
        out.append({"country": country, "state": state, "farm_count": len(fs),
                    "total_area_ha": round(sum(f["area_ha"] or 0 for f in fs), 1),
                    "mean_annual_rainfall_mm": round(statistics.mean(rain)) if rain else None,
                    "mean_temperature_c": round(statistics.mean(temp), 1) if temp else None,
                    "irrigated_farms": sum(1 for f in fs if f["irrigation_type"] != "none"),
                    "common_soil_limitations": sorted(lims.items(), key=lambda t: -t[1])[:3],
                    "farms_with_soil_data": sum(1 for f in fs if f["soil_data"])})
    return {"regions": out}


@router.get("/me/report.csv")
def org_report(user: User = Depends(org_staff), db: Session = Depends(get_db)):
    org = _org(user, db)
    rows = [_summary(f, db) for f in _farms(org, db)]
    cols = ["farm_id", "farm_name", "owner", "country", "state", "region", "area_ha", "irrigation_type",
            "current_crop", "annual_rainfall_mm", "mean_temperature_c", "surface_soil_moisture", "soil_limitations",
            "datasets_complete", "uses_demo_data", "latest_strategy"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        r = dict(r)
        r["soil_limitations"] = "; ".join(r["soil_limitations"])
        r["latest_strategy"] = (r["latest_strategy"] or {}).get("sequence") or ""
        w.writerow(r)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="agrinova-{org.id}-farms.csv"'})
