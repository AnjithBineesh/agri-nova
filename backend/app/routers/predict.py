"""AI crop prediction endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agriculture.soil_analyser import to_kg_ha
from ..authentication.deps import get_current_user, get_farm_for_user
from ..database import get_db
from ..ml import predictor
from ..ml.features import season_features
from ..models import User
from ..recommendation_engine.seasons import season_label
from ..services.farm_context import build_context

router = APIRouter(prefix="/api/predict", tags=["AI crop prediction"])


class CropInputs(BaseModel):
    N: float = Field(ge=0, le=1000)
    P: float = Field(ge=0, le=1000)
    K: float = Field(ge=0, le=2000)
    temperature: float = Field(ge=-10, le=55)
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=2.5, le=11.5)
    rainfall: float = Field(ge=0, le=2000)
    top_k: int = Field(default=5, ge=1, le=10)


class SoilInputs(BaseModel):
    N: float = Field(ge=0, le=1000)
    P: float = Field(ge=0, le=1000)
    K: float = Field(ge=0, le=2000)
    ph: float = Field(ge=2.5, le=11.5)
    EC: float = Field(ge=0, le=60)
    S: float = Field(ge=0, le=500)
    Cu: float = Field(ge=0, le=500)
    Fe: float = Field(ge=0, le=2000)
    Mn: float = Field(ge=0, le=5000)
    Zn: float = Field(ge=0, le=500)
    B: float = Field(ge=0, le=500)
    top_k: int = Field(default=5, ge=1, le=6)


def _run(model_key: str, inputs: dict, top_k: int) -> dict:
    try:
        return predictor.predict(model_key, inputs, top_k)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"The prediction model is not available: {exc}")


@router.get("/models")
def models(user: User = Depends(get_current_user)):
    card = predictor.model_card()
    strip = lambda m: {k: v for k, v in m.items() if k != "profiles"}  # noqa: E731
    return {**card, "crop_model": strip(card["crop_model"]), "soil_model": strip(card["soil_model"])}


@router.post("/crop")
def predict_crop(body: CropInputs, user: User = Depends(get_current_user)):
    return _run("crop_model", body.model_dump(exclude={"top_k"}), body.top_k)


@router.post("/soil")
def predict_soil(body: SoilInputs, user: User = Depends(get_current_user)):
    return _run("soil_model", body.model_dump(exclude={"top_k"}), body.top_k)


def farm_inputs(ctx) -> dict:
    soil = ctx.soil or {}
    soil_vals = {
        "N": to_kg_ha(soil.get("nitrogen"), soil.get("nitrogen_unit")),
        "P": to_kg_ha(soil.get("phosphorus"), soil.get("phosphorus_unit")),
        "K": to_kg_ha(soil.get("potassium"), soil.get("potassium_unit")),
        "ph": soil.get("ph"),
    }
    seasons = []
    for s in ctx.seasons:
        clim = season_features(ctx.profile.monthly, s["start_month"], s["end_month"]) if ctx.profile.has_climate \
            else {"temperature": None, "humidity": None, "rainfall": None}
        inputs = {**{k: (round(v, 1) if v is not None else None) for k, v in soil_vals.items()}, **clim}
        sources = {k: ("soil test" if soil_vals[k] is not None else "missing") for k in ("N", "P", "K", "ph")}
        sources.update({k: ("farm weather record" if clim[k] is not None else "missing")
                        for k in ("temperature", "humidity", "rainfall")})
        seasons.append({"name": s["name"], "label": season_label(s), "inputs": inputs, "sources": sources,
                        "complete": all(v is not None for v in inputs.values())})
    notes = []
    if not ctx.profile.has_climate:
        notes.append("Weather data for this farm hasn't been retrieved yet, so temperature, humidity and rainfall are empty.")
    if not ctx.soil:
        notes.append("No soil test saved for this farm, so N, P, K and pH are empty.")
    return {"seasons": seasons, "seasons_source": ctx.seasons_source, "notes": notes,
            "is_demo_basis": ctx.profile.is_demo}


@router.get("/farm/{farm_id}/inputs")
def get_farm_inputs(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user)
    return farm_inputs(build_context(db, farm))


@router.get("/farm/{farm_id}")
def predict_farm(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Predictions for every growing season of a farm, using its saved soil test and weather record."""
    farm = get_farm_for_user(farm_id, db, user)
    data = farm_inputs(build_context(db, farm))
    for s in data["seasons"]:
        s["result"] = _run("crop_model", s["inputs"], 5) if s["complete"] else None
    return data
