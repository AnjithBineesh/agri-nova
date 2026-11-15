"""SMAP soil moisture via AppEEARS.

* SPL3SMP_E (Enhanced L3 radiometer, 9 km EASE-Grid 2.0, daily AM overpass): surface soil
  moisture (~0–5 cm) retrieved from L-band brightness temperature. Satellite retrieval.
* SPL4SMGP (L4 Surface & Root-Zone, 9 km, 3-hourly): output of a land-surface model that
  assimilates SMAP brightness temperatures – a model estimate, not a direct measurement.
  Root zone = 0–100 cm.
SMAP volumetric soil moisture (m³/m³) is NOT a laboratory water-holding-capacity measurement
and represents a ~9 km grid cell, not an individual field.
"""
from collections import defaultdict
from statistics import mean

from ..config import get_settings
from .appeears import Layer, find_value, row_date
from .base import DataType, ObservationRecord

DATASET = "smap"
RES = "9 km EASE-Grid 2.0"


def layers() -> list[Layer]:
    s = get_settings()
    return [Layer(s.smap_l3_product, s.smap_l3_layer), Layer(s.smap_l3_product, s.smap_l3_qa_layer),
            Layer(s.smap_l4_product, s.smap_l4_surface_layer), Layer(s.smap_l4_product, s.smap_l4_rootzone_layer)]


def _valid_sm(v: float | None) -> bool:
    return v is not None and 0.0 <= v <= 0.8


def parse(rows: list[dict], lat: float, lon: float, source_url: str) -> list[ObservationRecord]:
    s = get_settings()
    l3, qa, l4s, l4r = layers()
    out: list[ObservationRecord] = []
    l4_daily: dict = defaultdict(lambda: {"surface": [], "rootzone": []})
    for row in rows:
        d = row_date(row)
        if d is None:
            continue
        v = find_value(row, l3)
        if _valid_sm(v):
            flag = find_value(row, qa)
            recommended = flag is not None and (int(flag) & 1) == 0
            out.append(ObservationRecord(
                dataset=DATASET, product_id=s.smap_l3_product, variable="surface_soil_moisture", value=v,
                unit="m³/m³", observation_date=d, latitude=lat, longitude=lon, spatial_resolution=RES,
                temporal_resolution="daily (AM overpass, ~2–3 day revisit)", source_url=source_url,
                data_type=DataType.SATELLITE_OBSERVATION,
                quality="recommended" if recommended else "not_recommended_or_unknown"))
        for lyr, key in ((l4s, "surface"), (l4r, "rootzone")):
            val = find_value(row, lyr)
            if _valid_sm(val):
                l4_daily[d][key].append(val)
    for d, vals in sorted(l4_daily.items()):
        for key, var in (("surface", "l4_surface_soil_moisture"), ("rootzone", "rootzone_soil_moisture")):
            if vals[key]:
                out.append(ObservationRecord(
                    dataset=DATASET, product_id=s.smap_l4_product, variable=var, value=round(mean(vals[key]), 4),
                    unit="m³/m³", observation_date=d, latitude=lat, longitude=lon, spatial_resolution=RES,
                    temporal_resolution="daily mean of 3-hourly", source_url=source_url,
                    data_type=DataType.MODEL_ESTIMATE, quality="model_assimilation"))
    return out
