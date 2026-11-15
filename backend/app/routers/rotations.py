import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authentication.deps import get_current_user, get_farm_for_user
from ..database import get_db
from ..models import Recommendation, User
from ..recommendation_engine.priority_scoring import OBJECTIVE_LABELS, automatic_weights, normalise_weights
from ..recommendation_engine.recommendation_generator import Context, evaluate_sequence, generate
from ..schemas.planning import CompareRequest, GenerateRequest, RotationSlot
from ..services.farm_context import FarmContext, build_context
from ..simulation.climate_scenarios import Scenario
from ..simulation.scenario_comparison import compare

router = APIRouter(prefix="/api/rotations", tags=["rotation planning"])


def validate_rotation(rotation: list[RotationSlot], ctx: FarmContext) -> list[dict]:
    out = []
    for slot in rotation:
        if slot.crop != "fallow" and slot.crop not in ctx.crops:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown crop '{slot.crop}'")
        out.append({"crop": slot.crop, "span": slot.span})
    return out


def engine_context(fc: FarmContext, horizon_years: int, yields: dict, economics: dict) -> Context:
    unknown = [k for k in list(yields) + list(economics) if k not in fc.crops]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown crops: {', '.join(unknown)}")
    return Context(fc.crops, fc.profile, fc.soil, fc.farm_info, fc.seasons, horizon_years, yields,
                   {k: v.model_dump() for k, v in economics.items()}, fc.history_slugs)


def rec_out(r: Recommendation) -> dict:
    return {"id": r.id, "farm_id": r.farm_id, "batch_id": r.batch_id, "strategy_key": r.strategy_key,
            "strategy_name": r.strategy_name, "crop_sequence": r.crop_sequence,
            "suitability_score": r.suitability_score, "priority_weights": r.priority_weights, "scores": r.scores,
            "explanation": r.explanation, "saved": r.saved, "created_at": r.created_at.isoformat()}


@router.post("/generate")
def generate_rotations(body: GenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    fc = build_context(db, farm)
    if not fc.profile.has_climate:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Weather data is required. Open Field conditions and retrieve weather data first.")
    ctx = engine_context(fc, body.horizon_years, body.yields, body.economics)
    econ_ok = bool(body.economics)
    auto_w, auto_why = automatic_weights(fc.profile, fc.soil_assessment, fc.farm_info, econ_ok)
    if body.mode == "custom":
        if not body.priorities:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Custom mode needs priority weights")
        weights, why = normalise_weights(body.priorities), ["Weights set by the farmer (custom mode)."]
    else:
        weights, why = auto_w, auto_why
    custom = validate_rotation(body.custom_rotation, fc) if body.custom_rotation else None
    result = generate(ctx, weights, fc.history, farm.current_crop, custom)
    batch = uuid.uuid4().hex[:12]
    for s in result["strategies"]:
        rec = Recommendation(farm_id=farm.id, batch_id=batch, strategy_key=s["key"], strategy_name=s["name"],
                             crop_sequence=s["crop_sequence"], suitability_score=s["mean_suitability"],
                             priority_weights=weights,
                             scores={"objectives": s["objectives"], "priority_score": s["priority_score"],
                                     "rank": s.get("rank"), "simulation_summary": s["simulation_summary"],
                                     "stress_summary": s["stress_summary"]},
                             explanation={**s["explanation"], "rules": s["rules"], "rotation": s["rotation"]})
        db.add(rec)
        db.flush()
        s["id"] = rec.id
    db.commit()
    return {**result, "batch_id": batch, "mode": body.mode, "weights_explanation": why,
            "automatic_weights": auto_w, "objective_labels": OBJECTIVE_LABELS, "seasons_source": fc.seasons_source,
            "is_demo_basis": fc.profile.is_demo, "data_gaps": fc.profile.gaps}


@router.get("/farm/{farm_id}")
def list_for_farm(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_for_user(farm_id, db, user)
    recs = db.scalars(select(Recommendation).where(Recommendation.farm_id == farm_id)
                      .order_by(Recommendation.created_at.desc(), Recommendation.id)).all()
    latest_batch = recs[0].batch_id if recs else None
    return {"latest_batch": latest_batch,
            "latest": [rec_out(r) for r in recs if r.batch_id == latest_batch],
            "saved": [rec_out(r) for r in recs if r.saved]}


@router.get("/{rotation_id}")
def get_rotation(rotation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Recommendation, rotation_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rotation not found")
    get_farm_for_user(r.farm_id, db, user)
    return rec_out(r)


@router.post("/{rotation_id}/save")
def save_rotation(rotation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Recommendation, rotation_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rotation not found")
    get_farm_for_user(r.farm_id, db, user, write=True)
    r.saved = not r.saved
    db.commit()
    return rec_out(r)


def resolve_named(db: Session, user: User, items, fc: FarmContext) -> list[tuple[str, list[dict]]]:
    out = []
    for item in items:
        if item.strategy_id:
            r = db.get(Recommendation, item.strategy_id)
            if r is None or r.farm_id != fc.farm.id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Strategy {item.strategy_id} not found for this farm")
            out.append((item.name or r.strategy_name, r.explanation["rotation"]))
        elif item.rotation:
            out.append((item.name, validate_rotation(item.rotation, fc)))
        else:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Each item needs a rotation or strategy_id")
    return out


@router.post("/compare")
def compare_rotations(body: CompareRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    fc = build_context(db, farm)
    if not fc.profile.has_climate:
        raise HTTPException(status.HTTP_409_CONFLICT, "Climate data is required to compare rotations")
    ctx = engine_context(fc, body.horizon_years, body.yields, body.economics)
    sc = Scenario.from_inputs(body.scenario.model_dump() if body.scenario else None)
    named = resolve_named(db, user, body.rotations, fc)
    results = {}
    for name, rotation in named:
        ev = evaluate_sequence(rotation, ctx, sc)
        results[name] = {"rotation": rotation, "simulation": ev["simulation"], "rules": ev["rules"]}
    return {"results": results, "comparison": compare({n: r["simulation"] for n, r in results.items()}),
            "scenario": sc.as_dict(), "is_demo_basis": fc.profile.is_demo}
