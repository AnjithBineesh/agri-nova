from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..agriculture.crop_database import all_crops, load_seed, upsert_crop
from ..authentication.deps import get_current_user, get_farm_for_user, require_roles
from ..database import get_db
from ..models import Crop, User
from ..recommendation_engine.crop_suitability import DEFAULT_WEIGHTS, MODERATE, SUITABLE, assess_all
from ..recommendation_engine.seasons import season_label
from ..schemas.planning import SuitabilityRequest
from ..services.farm_context import build_context
from ..simulation.climate_scenarios import Scenario
from ..ml import predictor
from ..ml.features import SLUG_TO_LABEL, season_features
from ..agriculture.soil_analyser import to_kg_ha

router = APIRouter(prefix="/api/crops", tags=["crop intelligence"])


@router.get("")
def list_crops(category: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    crops = all_crops(db)
    if category:
        crops = [c for c in crops if c["category"] == category]
    return {"crops": crops, "sources": load_seed()["sources"]}


@router.get("/{crop_ref}")
def get_crop(crop_ref: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Crop).where(or_(Crop.slug == crop_ref, Crop.id == int(crop_ref) if crop_ref.isdigit() else False))
    crop = db.scalar(q)
    if crop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crop not found")
    return {**crop.data, "id": crop.id}


@router.put("/{slug}")
def update_crop(slug: str, record: dict, user: User = Depends(require_roles("researcher")),
                db: Session = Depends(get_db)):
    """Researchers can refine crop parameters. The record must keep the full schema."""
    required = {"slug", "crop_name", "crop_family", "category", "duration", "climate_requirements",
                "water_requirement", "soil_preferences", "nutrient_requirements", "nitrogen_fixation",
                "root_characteristics", "residue", "rotation", "sources"}
    missing = required - record.keys()
    if missing or record.get("slug") != slug:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Record must include {', '.join(sorted(missing)) or 'matching slug'}")
    if not record.get("sources"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Every crop record must cite its sources")
    record.setdefault("pest_disease_considerations", [])
    crop = upsert_crop(db, record)
    return {**crop.data, "id": crop.id}


@router.post("/suitability")
def suitability(body: SuitabilityRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    ctx = build_context(db, farm)
    seasons = [s for s in ctx.seasons if not body.season or s["name"] == body.season]
    if not seasons:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Season not found for this farm")
    sc = Scenario.from_inputs(body.scenario.model_dump() if body.scenario else None)
    farm_info = {**ctx.farm_info}
    if sc.irrigation_type:
        farm_info["irrigation_type"] = sc.irrigation_type
    if sc.irrigation_capacity_mm is not None:
        farm_info["irrigation_capacity_mm"] = sc.irrigation_capacity_mm
    results = assess_all(list(ctx.crops.values()), seasons, ctx.profile, ctx.soil, farm_info,
                         temp_delta=sc.temp_delta_c, rain_factor=sc.rain_factor)
    ai_status = _attach_ai_match(results, seasons, ctx, sc)
    results.sort(key=lambda r: (r["season"], {"suitable": 0, "moderately_suitable": 1, "insufficient_data": 2,
                                              "unsuitable": 3}[r["class"]], -(r["score"] or 0)))
    return {
        "farm_id": farm.id, "seasons": [{**s, "label": season_label(s)} for s in seasons],
        "seasons_source": ctx.seasons_source, "results": results, "scenario": sc.as_dict(),
        "methodology": {
            "weights": DEFAULT_WEIGHTS, "thresholds": {"suitable": SUITABLE, "moderately_suitable": MODERATE},
            "description": "Weighted sum of factor scores (0–1) over factors with data, scaled to 0–100. Factor "
                           "scores use ECOCROP trapezoidal ranges. Any critical constraint makes a crop unsuitable "
                           "regardless of its score. Data completeness is the share of weight backed by data.",
        },
        "data_gaps": ctx.profile.gaps + ([] if ctx.soil else ["No soil profile: soil factors excluded"]),
        "is_demo_basis": ctx.profile.is_demo,
        "ai_match": ai_status,
    }


def _attach_ai_match(results: list[dict], seasons: list[dict], ctx, sc: Scenario) -> dict:
    """Add the crop prediction model's probability to crops that the model also knows."""
    soil = ctx.soil or {}
    n = to_kg_ha(soil.get("nitrogen"), soil.get("nitrogen_unit"))
    p = to_kg_ha(soil.get("phosphorus"), soil.get("phosphorus_unit"))
    k = to_kg_ha(soil.get("potassium"), soil.get("potassium_unit"))
    if None in (n, p, k, soil.get("ph")) or not ctx.profile.has_climate:
        return {"available": False, "message": "Add soil N, P, K and pH (and retrieve weather data) to see the AI match."}
    try:
        for season in seasons:
            clim = season_features(ctx.profile.monthly, season["start_month"], season["end_month"])
            clim["temperature"] += sc.temp_delta_c
            clim["rainfall"] *= sc.rain_factor
            proba = predictor.probability_for("crop_model", {"N": n, "P": p, "K": k, "ph": soil["ph"], **clim})
            ranking = sorted(proba, key=proba.get, reverse=True)
            for r in results:
                label = SLUG_TO_LABEL.get(r["crop"])
                if r["season"] == season["name"] and label in proba:
                    r["ai_match"] = {"probability": round(proba[label], 3), "rank": ranking.index(label) + 1,
                                     "of": len(ranking)}
    except Exception as exc:
        return {"available": False, "message": f"AI match unavailable: {exc}"}
    return {"available": True, "message": "AI match: probability from the crop prediction model for crops it knows "
                                          "(rice, maize, chickpea, pigeon pea, green gram, black gram, lentil, cotton)."}
