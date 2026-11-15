from pydantic import BaseModel, Field, field_validator


class RotationSlot(BaseModel):
    crop: str
    span: int = Field(default=1, ge=1, le=2)


class EconomicsInput(BaseModel):
    price_per_t: float = Field(ge=0)
    cost_per_ha: float = Field(ge=0)


class ScenarioInput(BaseModel):
    preset: str | None = None
    temp_delta_c: float | None = Field(default=None, ge=-3, le=5)
    rain_factor: float | None = Field(default=None, ge=0.3, le=2.0)
    irrigation_type: str | None = None
    irrigation_capacity_mm: float | None = Field(default=None, ge=0, le=3000)

    @field_validator("irrigation_type")
    @classmethod
    def _irr(cls, v):
        if v is not None and v not in ("none", "supplemental", "full"):
            raise ValueError("irrigation_type must be none, supplemental or full")
        return v


class SuitabilityRequest(BaseModel):
    farm_id: int
    season: str | None = None
    scenario: ScenarioInput | None = None


class GenerateRequest(BaseModel):
    farm_id: int
    mode: str = "automatic"  # automatic | custom
    priorities: dict[str, float] | None = None
    horizon_years: int = Field(default=5, ge=1, le=10)
    yields: dict[str, float] = Field(default_factory=dict)
    economics: dict[str, EconomicsInput] = Field(default_factory=dict)
    custom_rotation: list[RotationSlot] | None = None

    @field_validator("mode")
    @classmethod
    def _mode(cls, v):
        if v not in ("automatic", "custom"):
            raise ValueError("mode must be automatic or custom")
        return v


class NamedRotation(BaseModel):
    name: str
    rotation: list[RotationSlot] | None = None
    strategy_id: int | None = None


class CompareRequest(BaseModel):
    farm_id: int
    rotations: list[NamedRotation] = Field(min_length=1, max_length=5)
    scenario: ScenarioInput | None = None
    horizon_years: int = Field(default=5, ge=1, le=10)
    yields: dict[str, float] = Field(default_factory=dict)
    economics: dict[str, EconomicsInput] = Field(default_factory=dict)


class SimulationRequest(BaseModel):
    farm_id: int
    strategy_id: int | None = None
    rotation: list[RotationSlot] | None = None
    planning_horizon: str = "five_year"  # seasonal | five_year
    scenario: ScenarioInput | None = None
    yields: dict[str, float] = Field(default_factory=dict)
    economics: dict[str, EconomicsInput] = Field(default_factory=dict)

    @field_validator("planning_horizon")
    @classmethod
    def _h(cls, v):
        if v not in ("seasonal", "five_year"):
            raise ValueError("planning_horizon must be seasonal or five_year")
        return v


class ReportRequest(BaseModel):
    farm_id: int
    report_type: str = "farmer"  # farmer | scientific
    batch_id: str | None = None

    @field_validator("report_type")
    @classmethod
    def _t(cls, v):
        if v not in ("farmer", "scientific"):
            raise ValueError("report_type must be farmer or scientific")
        return v
