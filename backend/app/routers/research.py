import csv
import io
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authentication.deps import get_farm_for_user, require_roles
from ..database import get_db
from ..earth_observation.registry import DATASETS
from ..models import EarthObservation, Farm, User
from ..recommendation_engine.crop_suitability import DEFAULT_WEIGHTS, MODERATE, SUITABLE, assess_all
from ..recommendation_engine.priority_scoring import OBJECTIVES
from ..recommendation_engine.rotation_rules import SHARED_HOST_GROUPS
from ..services.farm_context import build_context
from ..simulation import organic_matter_model as som
from ..simulation.climate_scenarios import PRESETS, STRESS_TEST
from ..simulation.soil_state import ASSUMED_OC_PERCENT, BULK_DENSITY_BY_GROUP, TOPSOIL_DEPTH_CM
from ..simulation.water_balance import PADDY_EXTRA_MM_PER_DAY, STAGE_FRACTIONS

router = APIRouter(prefix="/api/research", tags=["researcher portal"])
researcher = require_roles("researcher")
MIN_GROUP = 3  # k-anonymity threshold for aggregated statistics


@router.get("/datasets")
def datasets(user: User = Depends(researcher)):
    from ..earth_observation.registry import DISPLAY_NAMES, DISPLAY_RESOLUTION
    return {"datasets": [{"key": d.key, "display_name": DISPLAY_NAMES.get(d.key, d.name),
                          "display_resolution": DISPLAY_RESOLUTION.get(d.key, d.spatial_resolution),
                          "temporal_resolution": d.temporal_resolution, "data_type": d.as_dict()["data_type"],
                          "integration": d.integration} for d in DATASETS.values()]}


@router.get("/model-assumptions")
def model_assumptions(user: User = Depends(researcher)):
    return {
        "suitability": {"weights": DEFAULT_WEIGHTS, "thresholds": {"suitable": SUITABLE, "moderate": MODERATE},
                        "membership": "ECOCROP trapezoid (1 within optimum, linear to 0 at absolute limits)"},
        "water_balance": {"stage_fractions": STAGE_FRACTIONS, "paddy_percolation_mm_day": PADDY_EXTRA_MM_PER_DAY,
                          "effective_rainfall": "FAO/AGLW: 0.8P−25 (P>75 mm/month), 0.6P−10 otherwise",
                          "et0": "FAO-56 Penman–Monteith from daily weather inputs; Hargreaves fallback"},
        "organic_carbon": {"h_above": som.H_ABOVE, "h_root": som.H_ROOT, "k_ref_per_year": som.K_REF,
                           "t_ref_c": som.T_REF, "q10": som.Q10, "root_fraction": som.ROOT_FRACTION,
                           "residue_retention": som.RETENTION, "topsoil_depth_cm": TOPSOIL_DEPTH_CM,
                           "bulk_density_by_texture": BULK_DENSITY_BY_GROUP,
                           "assumed_oc_when_missing_percent": ASSUMED_OC_PERCENT,
                           "uncertainty": "h ±30%, k ∓30% for low/high bounds"},
        "rotation_rules": {"shared_host_groups": {k: sorted(v) for k, v in SHARED_HOST_GROUPS.items()}},
        "scenarios": {"presets": PRESETS, "stress_test": STRESS_TEST},
        "objectives": OBJECTIVES,
    }


class SensitivityRequest(BaseModel):
    farm_id: int
    weights: dict[str, float]
    temp_delta_c: float = 0.0
    rain_factor: float = 1.0


@router.post("/suitability-sensitivity")
def sensitivity(body: SensitivityRequest, user: User = Depends(researcher), db: Session = Depends(get_db)):
    """Re-run suitability with researcher-defined factor weights and compare with the defaults."""
    farm = get_farm_for_user(body.farm_id, db, user)
    ctx = build_context(db, farm)
    weights = {k: max(0.0, float(body.weights.get(k, v))) for k, v in DEFAULT_WEIGHTS.items()}
    crops = list(ctx.crops.values())
    default = assess_all(crops, ctx.seasons, ctx.profile, ctx.soil, ctx.farm_info,
                         temp_delta=body.temp_delta_c, rain_factor=body.rain_factor)
    custom = assess_all(crops, ctx.seasons, ctx.profile, ctx.soil, ctx.farm_info, temp_delta=body.temp_delta_c,
                        rain_factor=body.rain_factor, weights=weights)
    rows = []
    for d, c in zip(default, custom):
        rows.append({"crop": d["crop_name"], "season": d["season"], "default_score": d["score"],
                     "custom_score": c["score"], "default_class": d["class"], "custom_class": c["class"],
                     "delta": None if d["score"] is None or c["score"] is None else round(c["score"] - d["score"], 1)})
    return {"weights": weights, "rows": rows, "is_demo_basis": ctx.profile.is_demo}


@router.get("/farms/{farm_id}/export")
def export_observations(farm_id: int, fmt: str = Query("csv", alias="format", pattern="^(csv|json)$"),
                        user: User = Depends(researcher), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user)
    rows = db.scalars(select(EarthObservation).where(EarthObservation.farm_id == farm.id)
                      .order_by(EarthObservation.dataset, EarthObservation.variable,
                                EarthObservation.observation_date)).all()
    cols = ["dataset", "product_id", "variable", "value", "unit", "observation_date", "latitude", "longitude",
            "resolution", "temporal_resolution", "quality_flag", "data_type", "is_demo", "source_url"]
    records = [{c: (getattr(r, c).isoformat() if c == "observation_date" else getattr(r, c)) for c in cols} for r in rows]
    if fmt == "json":
        return {"farm_id": farm.id, "count": len(records), "observations": records}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(records)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="agrinova-farm{farm.id}-observations.csv"'})


@router.get("/aggregate")
def aggregate(user: User = Depends(researcher), db: Session = Depends(get_db)):
    """Anonymised country-level indicators; groups with fewer than MIN_GROUP farms are suppressed."""
    farms = db.scalars(select(Farm)).all()
    groups = defaultdict(list)
    for f in farms:
        groups[f.country].append(f)
    out = []
    for country, fs in sorted(groups.items()):
        if len(fs) < MIN_GROUP:
            continue
        out.append({"country": country, "farm_count": len(fs),
                    "irrigated_share": round(sum(f.irrigation_type != "none" for f in fs) / len(fs), 2),
                    "median_area_ha": statistics.median([f.area_ha for f in fs if f.area_ha] or [0])})
    return {"groups": out, "suppressed_groups": sum(1 for v in groups.values() if len(v) < MIN_GROUP),
            "note": f"Groups with fewer than {MIN_GROUP} farms are suppressed to protect farmer privacy."}
