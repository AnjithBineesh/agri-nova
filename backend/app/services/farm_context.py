"""Assemble everything the engines need for one farm."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agriculture import soil_analyser
from ..agriculture.climate_analyser import EnvironmentProfile, build_profile
from ..agriculture.crop_database import crop_map
from ..models import Farm, SoilProfile
from ..recommendation_engine.seasons import resolve_seasons

SOIL_FIELDS = ("ph", "nitrogen", "nitrogen_unit", "phosphorus", "phosphorus_unit", "phosphorus_method", "potassium",
               "potassium_unit", "organic_carbon", "organic_matter", "soil_texture", "soil_depth_cm",
               "water_holding_capacity", "drainage", "electrical_conductivity")


def soil_dict(sp: SoilProfile | None) -> dict | None:
    if sp is None:
        return None
    d = {k: getattr(sp, k) for k in SOIL_FIELDS}
    d.update({"id": sp.id, "measurement_date": sp.measurement_date.isoformat() if sp.measurement_date else None,
              "data_source": sp.data_source, "value_status": sp.value_status or {}, "report_id": sp.report_id,
              "created_at": sp.created_at.isoformat() if sp.created_at else None})
    return d


def latest_soil(db: Session, farm: Farm) -> SoilProfile | None:
    return db.scalar(select(SoilProfile).where(SoilProfile.farm_id == farm.id)
                     .order_by(SoilProfile.created_at.desc(), SoilProfile.id.desc()).limit(1))


def farm_dict(farm: Farm) -> dict:
    return {"id": farm.id, "farm_name": farm.farm_name, "irrigation_type": farm.irrigation_type,
            "irrigation_capacity_mm": farm.irrigation_capacity_mm, "soil_type": farm.soil_type,
            "residue_management": farm.residue_management, "current_crop": farm.current_crop,
            "area_ha": farm.area_ha, "latitude": farm.latitude, "longitude": farm.longitude}


@dataclass
class FarmContext:
    farm: Farm
    crops: dict
    profile: EnvironmentProfile
    soil: dict | None
    soil_assessment: dict
    farm_info: dict
    seasons: list[dict]
    seasons_source: str
    history: list[dict]

    @property
    def history_slugs(self) -> list[str]:
        return [h["crop_slug"] for h in self.history]


def build_context(db: Session, farm: Farm) -> FarmContext:
    profile = build_profile(db, farm)
    soil = soil_dict(latest_soil(db, farm))
    seasons, source = resolve_seasons(farm.growing_seasons, profile)
    history = [{"crop_slug": h.crop_slug, "season": h.season, "year": h.year}
               for h in sorted(farm.crop_history, key=lambda h: (h.year, h.id))]
    return FarmContext(farm=farm, crops=crop_map(db), profile=profile, soil=soil,
                       soil_assessment=soil_analyser.assess(soil), farm_info=farm_dict(farm), seasons=seasons,
                       seasons_source=source, history=history)
