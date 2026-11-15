import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agriculture import soil_analyser
from ..authentication.deps import get_current_user, get_farm_for_user
from ..config import get_settings
from ..database import get_db
from ..models import SoilProfile, SoilReport, User
from ..schemas.soil import VALUE_FIELDS, ReportConfirm, SoilInput
from ..services.farm_context import soil_dict
from ..services.storage import get_storage
from ..soil_processing.extraction import extract_text
from ..soil_processing.parser import parse_report

router = APIRouter(tags=["soil"])

MAGIC = {b"%PDF": "application/pdf", b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}


def _save_profile(db: Session, farm_id: int, body: SoilInput, source: str, report_id: int | None = None
                  ) -> SoilProfile:
    data = body.model_dump(exclude={"laboratory", "report_date"} if isinstance(body, ReportConfirm) else set())
    status_map = dict(data.pop("value_status") or {})
    for f in VALUE_FIELDS:
        if data.get(f) is not None and f not in status_map:
            status_map[f] = "measured"  # default; the UI lets users mark values as estimated
    sp = SoilProfile(farm_id=farm_id, data_source=source, value_status=status_map, report_id=report_id, **data)
    if all(data.get(f) is None for f in VALUE_FIELDS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide at least one soil value")
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


@router.post("/api/farms/{farm_id}/soil", status_code=201)
def add_soil(farm_id: int, body: SoilInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user, write=True)
    sp = _save_profile(db, farm_id, body, "manual")
    d = soil_dict(sp)
    return {"profile": d, "assessment": soil_analyser.assess(d)}


@router.get("/api/farms/{farm_id}/soil")
def get_soil(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user)
    profiles = db.scalars(select(SoilProfile).where(SoilProfile.farm_id == farm.id)
                          .order_by(SoilProfile.created_at.desc(), SoilProfile.id.desc())).all()
    reports = db.scalars(select(SoilReport).where(SoilReport.farm_id == farm.id)
                         .order_by(SoilReport.created_at.desc())).all()
    latest = soil_dict(profiles[0]) if profiles else None
    return {"latest": latest, "assessment": soil_analyser.assess(latest),
            "history": [soil_dict(p) for p in profiles],
            "reports": [_report_out(r, include_text=False) for r in reports],
            "textures": soil_analyser.TEXTURES}


def _report_out(r: SoilReport, include_text: bool = True) -> dict:
    out = {"id": r.id, "farm_id": r.farm_id, "original_filename": r.original_filename,
           "content_type": r.content_type, "report_date": r.report_date.isoformat() if r.report_date else None,
           "laboratory": r.laboratory, "extraction_method": r.extraction_method,
           "extracted_values": r.extracted_values, "verification_status": r.verification_status,
           "created_at": r.created_at.isoformat(), "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None}
    if include_text:
        out["extracted_text"] = (r.extracted_text or "")[:20000]
    return out


@router.post("/api/farms/{farm_id}/soil/upload", status_code=201)
async def upload_report(farm_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    s = get_settings()
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {s.max_upload_mb} MB")
    detected = next((ct for magic, ct in MAGIC.items() if data.startswith(magic)), None)
    if detected is None or detected not in s.upload_allowed_types:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, JPG and PNG files are accepted")
    suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}[detected]
    key = get_storage().save(data, f"soil_reports/farm_{farm.id}", suffix)
    report = SoilReport(farm_id=farm.id, file_path=key, original_filename=(file.filename or "report")[:255],
                        content_type=detected, sha256=hashlib.sha256(data).hexdigest(), verification_status="pending")
    try:
        text, method = extract_text(data, detected)
        parsed = parse_report(text)
        report.extracted_text, report.extraction_method = text, method
        report.extracted_values = parsed
        report.laboratory = parsed.get("laboratory")
        if parsed.get("report_date"):
            report.report_date = datetime.fromisoformat(parsed["report_date"]).date()
    except Exception as exc:  # extraction failure is not fatal: the user can still enter values manually
        report.extracted_values = {"parameters": {}, "error": f"Text extraction failed: {exc}"}
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_out(report)


def _get_report(report_id: int, db: Session, user: User, write: bool = False) -> SoilReport:
    report = db.get(SoilReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    get_farm_for_user(report.farm_id, db, user, write=write)
    return report


@router.get("/api/soil/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _report_out(_get_report(report_id, db, user))


@router.get("/api/soil/{report_id}/file")
def download_report_file(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get_report(report_id, db, user)
    return Response(get_storage().read(r.file_path), media_type=r.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{r.original_filename}"'})


@router.post("/api/soil/{report_id}/confirm")
def confirm_report(report_id: int, body: ReportConfirm, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """User-reviewed values become the farm's soil profile, marked as confirmed laboratory values."""
    r = _get_report(report_id, db, user, write=True)
    if r.verification_status == "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This report has already been confirmed")
    if body.measurement_date is None:
        body.measurement_date = body.report_date or r.report_date
    sp = _save_profile(db, r.farm_id, body, "lab_report_confirmed", report_id=r.id)
    r.verification_status = "confirmed"
    r.confirmed_at = datetime.now(timezone.utc)
    r.laboratory = body.laboratory or r.laboratory
    r.report_date = body.report_date or r.report_date
    db.commit()
    d = soil_dict(sp)
    return {"report": _report_out(r, include_text=False), "profile": d, "assessment": soil_analyser.assess(d)}


@router.post("/api/soil/{report_id}/reject")
def reject_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get_report(report_id, db, user, write=True)
    r.verification_status = "rejected"
    db.commit()
    return _report_out(r, include_text=False)
