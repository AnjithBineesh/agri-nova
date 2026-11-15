from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authentication.deps import get_current_user, get_farm_for_user
from ..database import get_db
from ..models import Recommendation, Report, User
from ..recommendation_engine.crop_suitability import assess_all
from ..reporting.pdf_report import build_report
from ..schemas.planning import ReportRequest
from ..services import earth_data_service as eds
from ..services.farm_context import build_context
from ..services.storage import get_storage
from ..simulation.rotation_simulator import simulate
from .predict import _run, farm_inputs

router = APIRouter(prefix="/api/reports", tags=["reports"])


def report_out(r: Report) -> dict:
    return {"id": r.id, "farm_id": r.farm_id, "report_type": r.report_type, "created_at": r.created_at.isoformat(),
            "download_url": f"/api/reports/{r.id}/download"}


@router.post("/generate", status_code=201)
def generate_report(body: ReportRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    ctx = build_context(db, farm)
    datasets = eds.status_summary(db, farm)
    suit = assess_all(list(ctx.crops.values()), ctx.seasons, ctx.profile, ctx.soil, ctx.farm_info) \
        if ctx.profile.has_climate else []
    suit.sort(key=lambda r: -(r["score"] or 0) if r["class"] != "unsuitable" else 1000)
    q = select(Recommendation).where(Recommendation.farm_id == farm.id)
    if body.batch_id:
        q = q.where(Recommendation.batch_id == body.batch_id)
    recs = db.scalars(q.order_by(Recommendation.created_at.desc(), Recommendation.id)).all()
    batch = recs[0].batch_id if recs else None
    strategies = [{"strategy_name": r.strategy_name, "scores": r.scores, "explanation": r.explanation,
                   "priority_weights": r.priority_weights, "saved": r.saved}
                  for r in recs if r.batch_id == batch]
    sims = {}
    if ctx.profile.has_climate:
        cache: dict = {}
        for s in strategies[:5]:
            sims[s["strategy_name"]] = simulate(s["explanation"]["rotation"], ctx.crops, ctx.profile, ctx.soil,
                                                ctx.farm_info, ctx.seasons, None, 5, history=ctx.history_slugs,
                                                assess_cache=cache)
    ai = farm_inputs(ctx)
    try:
        for s in ai["seasons"]:
            s["result"] = _run("crop_model", s["inputs"], 3) if s["complete"] else None
    except Exception:
        ai = None
    pdf = build_report(body.report_type, farm, ctx, datasets, suit, strategies, sims, ai)
    key = get_storage().save(pdf, f"reports/farm_{farm.id}", ".pdf")
    rep = Report(farm_id=farm.id, report_type=body.report_type, file_path=key)
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return report_out(rep)


@router.get("/farm/{farm_id}")
def list_reports(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    reps = db.scalars(select(Report).where(Report.farm_id == farm_id).order_by(Report.created_at.desc())).all()
    return {"reports": [report_out(r) for r in reps]}


def _get(report_id: int, db: Session, user: User) -> Report:
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    get_farm_for_user(r.farm_id, db, user)
    return r


@router.get("/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return report_out(_get(report_id, db, user))


@router.get("/{report_id}/download")
def download(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get(report_id, db, user)
    name = f"agrinova-{r.report_type}-report-farm{r.farm_id}-{r.id}.pdf"
    return Response(get_storage().read(r.file_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
