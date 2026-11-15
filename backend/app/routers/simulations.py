from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..authentication.deps import get_current_user, get_farm_for_user
from ..database import get_db
from ..models import Recommendation, Simulation, User
from ..schemas.planning import CompareRequest, SimulationRequest
from ..services.farm_context import build_context
from ..simulation.climate_scenarios import PRESETS, Scenario
from ..simulation.rotation_simulator import simulate
from ..simulation.scenario_comparison import compare
from .rotations import engine_context, resolve_named, validate_rotation

router = APIRouter(prefix="/api/simulations", tags=["simulation"])


def sim_out(s: Simulation) -> dict:
    return {"id": s.id, "farm_id": s.farm_id, "strategy_id": s.strategy_id, "planning_horizon": s.planning_horizon,
            "scenario_inputs": s.scenario_inputs, "results": s.results, "assumptions": s.assumptions,
            "created_at": s.created_at.isoformat()}


@router.get("/presets")
def presets(user: User = Depends(get_current_user)):
    return {"presets": PRESETS}


@router.post("", status_code=201)
def run_simulation(body: SimulationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    fc = build_context(db, farm)
    if not fc.profile.has_climate:
        raise HTTPException(status.HTTP_409_CONFLICT, "Weather data is required. Open Field conditions and retrieve weather data first.")
    if body.strategy_id:
        rec = db.get(Recommendation, body.strategy_id)
        if rec is None or rec.farm_id != farm.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found for this farm")
        rotation = rec.explanation["rotation"]
    elif body.rotation:
        rotation = validate_rotation(body.rotation, fc)
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide strategy_id or rotation")
    ctx = engine_context(fc, 1, body.yields, body.economics)
    sc = Scenario.from_inputs(body.scenario.model_dump() if body.scenario else None)
    years = 1 if body.planning_horizon == "seasonal" else 5
    result = simulate(rotation, ctx.crops, fc.profile, fc.soil, fc.farm_info, fc.seasons, sc, years, ctx.yields,
                      ctx.economics, fc.history_slugs)
    sim = Simulation(farm_id=farm.id, strategy_id=body.strategy_id, planning_horizon=body.planning_horizon,
                     scenario_inputs={"scenario": sc.as_dict(), "rotation": rotation, "yields": body.yields,
                                      "economics": ctx.economics},
                     results={"seasons": result["seasons"], "summary": result["summary"]},
                     assumptions=result["assumptions"])
    db.add(sim)
    db.commit()
    db.refresh(sim)
    return sim_out(sim)


@router.get("/{simulation_id}")
def get_simulation(simulation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sim = db.get(Simulation, simulation_id)
    if sim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Simulation not found")
    get_farm_for_user(sim.farm_id, db, user)
    return sim_out(sim)


@router.post("/compare")
def compare_simulations(body: CompareRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(body.farm_id, db, user)
    fc = build_context(db, farm)
    if not fc.profile.has_climate:
        raise HTTPException(status.HTTP_409_CONFLICT, "Weather data is required. Open Field conditions and retrieve weather data first.")
    ctx = engine_context(fc, body.horizon_years, body.yields, body.economics)
    sc = Scenario.from_inputs(body.scenario.model_dump() if body.scenario else None)
    named = resolve_named(db, user, body.rotations, fc)
    sims = {}
    cache: dict = {}
    for name, rotation in named:
        sims[name] = simulate(rotation, ctx.crops, fc.profile, fc.soil, fc.farm_info, fc.seasons, sc,
                              body.horizon_years, ctx.yields, ctx.economics, fc.history_slugs, cache)
        sims[name]["rotation"] = rotation
    return {"simulations": sims, "comparison": compare(sims), "scenario": sc.as_dict(),
            "is_demo_basis": fc.profile.is_demo, "seasons": fc.seasons}
