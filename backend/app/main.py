import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agriculture.crop_database import seed_crops
from .config import get_settings
from .database import SessionLocal, init_db
from .earth_observation.registry import DATASETS
from .ml.predictor import warm_up
from .routers import (auth, crops, earth, farms, organisations, power, predict, reports, research, rotations,
                      simulations, soil)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agrinova")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.environment == "production" and settings.jwt_secret_key == "change-me-in-production":
        raise RuntimeError("Set JWT_SECRET_KEY before running in production")
    init_db()
    with SessionLocal() as db:
        added = seed_crops(db)
        if added:
            log.info("Seeded %s crops", added)
    warm_up()
    yield


app = FastAPI(title="Agri Nova API", version="1.0.0", lifespan=lifespan,
              description="AI crop prediction, crop rotation strategy and soil health decision support.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    msg = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
    return JSONResponse(status_code=422, content={"detail": msg or "Invalid request", "errors": errors})


for r in (auth, farms, soil, earth, power, predict, crops, rotations, simulations, reports, research, organisations):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    s = get_settings()
    return {"status": "ok", "earthdata_configured": s.earthdata_configured, "demo_data_enabled": s.enable_demo_data,
            "datasets": {k: d.integration for k, d in DATASETS.items()}}
