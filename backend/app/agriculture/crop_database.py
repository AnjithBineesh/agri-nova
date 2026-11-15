"""Crop knowledge base: seeded from data/crops.json and editable through the API."""
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Crop

DATA_FILE = Path(__file__).resolve().parent / "data" / "crops.json"


@lru_cache
def load_seed() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _to_model_fields(rec: dict) -> dict:
    return dict(
        slug=rec["slug"], crop_name=rec["crop_name"], crop_family=rec["crop_family"], category=rec["category"],
        duration=rec["duration"], water_requirement=rec["water_requirement"],
        nutrient_requirements=rec["nutrient_requirements"], climate_requirements=rec["climate_requirements"],
        soil_preferences=rec["soil_preferences"], nitrogen_fixation=rec["nitrogen_fixation"],
        root_characteristics=rec["root_characteristics"], data=rec,
    )


def seed_crops(db: Session) -> int:
    """Insert crops missing from the database. Existing (possibly edited) records are left untouched."""
    existing = set(db.scalars(select(Crop.slug)).all())
    added = 0
    for rec in load_seed()["crops"]:
        if rec["slug"] not in existing:
            db.add(Crop(**_to_model_fields(rec)))
            added += 1
    db.commit()
    return added


def upsert_crop(db: Session, rec: dict) -> Crop:
    crop = db.scalar(select(Crop).where(Crop.slug == rec["slug"]))
    fields = _to_model_fields(rec)
    if crop is None:
        crop = Crop(**fields)
        db.add(crop)
    else:
        for k, v in fields.items():
            setattr(crop, k, v)
    db.commit()
    db.refresh(crop)
    return crop


def all_crops(db: Session) -> list[dict]:
    rows = db.scalars(select(Crop).order_by(Crop.category, Crop.crop_name)).all()
    return [{**r.data, "id": r.id} for r in rows]


def crop_map(db: Session) -> dict[str, dict]:
    return {c["slug"]: c for c in all_crops(db)}
