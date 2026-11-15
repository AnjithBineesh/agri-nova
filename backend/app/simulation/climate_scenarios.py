"""Climate and water scenarios applied to the historical climatology (sensitivity tests, not forecasts)."""
from dataclasses import asdict, dataclass

PRESETS = {
    "baseline": {"temp_delta_c": 0.0, "rain_factor": 1.0, "label": "Recent climate (baseline climatology)"},
    "warmer": {"temp_delta_c": 1.5, "rain_factor": 1.0, "label": "+1.5 °C warmer"},
    "drier": {"temp_delta_c": 0.0, "rain_factor": 0.8, "label": "20% less rainfall"},
    "hot_dry": {"temp_delta_c": 2.0, "rain_factor": 0.8, "label": "+2 °C and 20% less rainfall"},
    "wetter": {"temp_delta_c": 0.0, "rain_factor": 1.2, "label": "20% more rainfall"},
}
STRESS_TEST = {"temp_delta_c": 1.5, "rain_factor": 0.85}


@dataclass
class Scenario:
    temp_delta_c: float = 0.0
    rain_factor: float = 1.0
    irrigation_type: str | None = None  # override farm setting
    irrigation_capacity_mm: float | None = None
    label: str = "custom"

    @classmethod
    def from_inputs(cls, d: dict | None) -> "Scenario":
        d = dict(d or {})
        preset = d.pop("preset", None)
        base = dict(PRESETS.get(preset, {})) if preset else {}
        base.update({k: v for k, v in d.items() if v is not None})
        base.setdefault("label", preset or "custom")
        return cls(temp_delta_c=float(base.get("temp_delta_c", 0.0)), rain_factor=float(base.get("rain_factor", 1.0)),
                   irrigation_type=base.get("irrigation_type"), irrigation_capacity_mm=base.get("irrigation_capacity_mm"),
                   label=base["label"])

    def as_dict(self) -> dict:
        return asdict(self)
