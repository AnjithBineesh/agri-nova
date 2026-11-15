"""MODIS Terra vegetation indices (MOD13Q1 v061, 250 m, 16-day composites) via AppEEARS."""
from ..config import get_settings
from .appeears import Layer, find_value, row_date
from .base import DataType, ObservationRecord

DATASET = "modis"
RES = "250 m"
RELIABILITY = {0: "good", 1: "marginal", 2: "snow_ice", 3: "cloudy", -1: "fill"}


def layers() -> list[Layer]:
    p = get_settings().modis_vi_product
    return [Layer(p, "_250m_16_days_NDVI"), Layer(p, "_250m_16_days_EVI"), Layer(p, "_250m_16_days_pixel_reliability")]


def _scale(v: float | None) -> float | None:
    if v is None or v <= -2999:
        return None
    if abs(v) > 1.5:  # raw integer value, apply MOD13 scale factor 0.0001
        v = v * 0.0001
    return round(v, 4) if -0.2 <= v <= 1.0 else None


def parse(rows: list[dict], lat: float, lon: float, source_url: str) -> list[ObservationRecord]:
    p = get_settings().modis_vi_product
    ndvi_l, evi_l, rel_l = layers()
    out = []
    for row in rows:
        d = row_date(row)
        if d is None:
            continue
        rel = find_value(row, rel_l)
        quality = RELIABILITY.get(int(rel), "unknown") if rel is not None else "unknown"
        if quality not in ("good", "marginal"):
            continue  # cloud, snow or fill: excluded rather than shown as a vegetation signal
        for lyr, var in ((ndvi_l, "ndvi"), (evi_l, "evi")):
            v = _scale(find_value(row, lyr))
            if v is not None:
                out.append(ObservationRecord(
                    dataset=DATASET, product_id=p, variable=var, value=v, unit="index", observation_date=d,
                    latitude=lat, longitude=lon, spatial_resolution=RES, temporal_resolution="16-day composite",
                    source_url=source_url, data_type=DataType.DERIVED_SATELLITE_INDICATOR, quality=quality))
    return out
