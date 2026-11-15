from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GrowingSeason(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    start_month: int = Field(ge=1, le=12)
    end_month: int = Field(ge=1, le=12)

    @property
    def length_months(self) -> int:
        return (self.end_month - self.start_month) % 12 + 1


class CropHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    crop_slug: str
    season: str
    year: int = Field(ge=1950, le=2100)


def _validate_polygon(geom: dict | None) -> dict | None:
    if geom is None:
        return None
    if geom.get("type") != "Polygon":
        raise ValueError("Farm boundary must be a GeoJSON Polygon")
    rings = geom.get("coordinates") or []
    if not rings or len(rings[0]) < 4:
        raise ValueError("Polygon needs at least three distinct vertices")
    for lon, lat, *_ in rings[0]:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Polygon coordinates out of range")
    if rings[0][0] != rings[0][-1]:
        rings[0].append(rings[0][0])
    return geom


class FarmBase(BaseModel):
    farm_name: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=2, max_length=100)
    state: str | None = None
    region: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_source: str = "map"
    boundary: dict | None = None
    boundary_status: str = "none"
    area_ha: float | None = Field(default=None, gt=0, le=1_000_000)
    soil_type: str | None = None
    current_crop: str | None = None
    previous_crops: list[str] = Field(default_factory=list)
    irrigation_type: str = "none"
    irrigation_capacity_mm: float | None = Field(default=None, ge=0, le=3000)
    growing_seasons: list[GrowingSeason] = Field(default_factory=list)
    farming_method: str | None = None
    residue_management: str = "partial"
    crop_history: list[CropHistoryItem] = Field(default_factory=list)

    @field_validator("location_source")
    @classmethod
    def _src(cls, v):
        if v not in ("gps", "map", "manual"):
            raise ValueError("location_source must be gps, map or manual")
        return v

    @field_validator("irrigation_type")
    @classmethod
    def _irr(cls, v):
        if v not in ("none", "supplemental", "full"):
            raise ValueError("irrigation_type must be none, supplemental or full")
        return v

    @field_validator("residue_management")
    @classmethod
    def _res(cls, v):
        if v not in ("removed", "partial", "retained"):
            raise ValueError("residue_management must be removed, partial or retained")
        return v

    @field_validator("boundary")
    @classmethod
    def _boundary(cls, v):
        return _validate_polygon(v)

    @model_validator(mode="after")
    def _boundary_status(self):
        if self.boundary is None:
            self.boundary_status = "none"
        elif self.boundary_status not in ("user_drawn", "verified"):
            self.boundary_status = "user_drawn"
        return self


class FarmCreate(FarmBase):
    pass


class FarmUpdate(FarmBase):
    pass


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    farm_name: str
    country: str
    state: str | None
    region: str | None
    latitude: float
    longitude: float
    location_source: str
    boundary: dict | None
    boundary_status: str
    area_ha: float | None
    area_source: str | None
    soil_type: str | None
    current_crop: str | None
    previous_crops: list[str] | None
    irrigation_type: str
    irrigation_capacity_mm: float | None
    growing_seasons: list[dict] | None
    farming_method: str | None
    residue_management: str
    crop_history: list[CropHistoryItem] = Field(default_factory=list)
    owner_name: str | None = None
    can_edit: bool = True
    created_at: datetime
    updated_at: datetime
