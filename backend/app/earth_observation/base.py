"""Standardised data structures shared by every Earth observation adapter."""
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum


class DataType(str, Enum):
    SATELLITE_OBSERVATION = "satellite_observation"
    DERIVED_SATELLITE_INDICATOR = "derived_satellite_indicator"
    WEATHER_CLIMATE_ESTIMATE = "weather_climate_estimate"
    FARMER_PROVIDED = "farmer_provided"
    MODEL_ESTIMATE = "model_estimate"
    DEMONSTRATION = "demonstration"


class FetchState(str, Enum):
    COMPLETE = "complete"
    PENDING = "pending"  # submitted to an asynchronous service
    PROCESSING = "processing"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"  # credentials missing
    NOT_INTEGRATED = "not_integrated"  # adapter interface exists, retrieval not implemented
    NO_DATA = "no_data"
    DEMO = "demonstration"


@dataclass
class ObservationRecord:
    dataset: str
    product_id: str
    variable: str
    value: float | None
    unit: str | None
    observation_date: date
    latitude: float | None
    longitude: float | None
    spatial_resolution: str
    temporal_resolution: str
    source_url: str
    data_type: DataType
    processing_status: str = "processed"
    quality: str | None = None
    is_demo: bool = False

    def as_dict(self) -> dict:
        d = asdict(self)
        d["data_type"] = self.data_type.value
        d["observation_date"] = self.observation_date.isoformat()
        return d


@dataclass
class AdapterResult:
    dataset: str
    state: FetchState
    records: list[ObservationRecord] = field(default_factory=list)
    message: str = ""
    external_task_id: str | None = None
    # Extra datasets that share one asynchronous request (e.g. one AppEEARS task)
    related_datasets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DatasetInfo:
    key: str
    name: str
    provider: str
    products: str
    spatial_resolution: str
    temporal_resolution: str
    coverage: str
    data_type: DataType
    access: str
    requires_credentials: bool
    integration: str  # integrated | interface_only
    documentation_url: str
    notes: str
    variables: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["data_type"] = self.data_type.value
        d["variables"] = list(self.variables)
        return d
