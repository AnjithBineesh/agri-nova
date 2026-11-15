from datetime import date

from pydantic import BaseModel, Field, field_validator

from ..agriculture.soil_analyser import TEXTURES

VALUE_FIELDS = ("ph", "nitrogen", "phosphorus", "potassium", "organic_carbon", "organic_matter", "soil_texture",
                "soil_depth_cm", "water_holding_capacity", "drainage", "electrical_conductivity")
NUTRIENT_UNITS = ("kg/ha", "mg/kg", "ppm", "lb/acre")


class SoilInput(BaseModel):
    ph: float | None = Field(default=None, ge=2.5, le=11.5)
    nitrogen: float | None = Field(default=None, ge=0, le=5000)
    nitrogen_unit: str | None = "kg/ha"
    phosphorus: float | None = Field(default=None, ge=0, le=2000)
    phosphorus_unit: str | None = "kg/ha"
    phosphorus_method: str | None = "unknown"
    potassium: float | None = Field(default=None, ge=0, le=10000)
    potassium_unit: str | None = "kg/ha"
    organic_carbon: float | None = Field(default=None, ge=0, le=60)
    organic_matter: float | None = Field(default=None, ge=0, le=100)
    soil_texture: str | None = None
    soil_depth_cm: float | None = Field(default=None, gt=0, le=1000)
    water_holding_capacity: float | None = Field(default=None, ge=0, le=400)
    drainage: str | None = None
    electrical_conductivity: float | None = Field(default=None, ge=0, le=60)
    measurement_date: date | None = None
    value_status: dict[str, str] = Field(default_factory=dict)

    @field_validator("nitrogen_unit", "phosphorus_unit", "potassium_unit")
    @classmethod
    def _unit(cls, v):
        if v is not None and v not in NUTRIENT_UNITS:
            raise ValueError(f"unit must be one of {', '.join(NUTRIENT_UNITS)}")
        return v

    @field_validator("phosphorus_method")
    @classmethod
    def _pm(cls, v):
        if v is not None and v not in ("olsen", "bray1", "mehlich3", "unknown"):
            raise ValueError("phosphorus_method must be olsen, bray1, mehlich3 or unknown")
        return v

    @field_validator("soil_texture")
    @classmethod
    def _tex(cls, v):
        if v is None or v == "":
            return None
        v = v.lower().strip()
        if v not in TEXTURES:
            raise ValueError(f"soil_texture must be a USDA texture class: {', '.join(TEXTURES)}")
        return v

    @field_validator("drainage")
    @classmethod
    def _dr(cls, v):
        if v is None or v == "":
            return None
        if v not in ("poorly", "imperfectly", "well", "excessively"):
            raise ValueError("drainage must be poorly, imperfectly, well or excessively")
        return v

    @field_validator("value_status")
    @classmethod
    def _vs(cls, v):
        for k, status in v.items():
            if k not in VALUE_FIELDS or status not in ("measured", "estimated"):
                raise ValueError("value_status maps soil fields to 'measured' or 'estimated'")
        return v


class ReportConfirm(SoilInput):
    laboratory: str | None = None
    report_date: date | None = None
