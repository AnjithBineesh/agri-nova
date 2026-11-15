"""Landsat 8/9 NDVI via NASA HLSL30 v2.0 (Landsat OLI surface reflectance harmonised to a 30 m grid).

HLSL30 is NASA's analysis-ready Landsat Collection 2-based product. NDVI = (NIR - RED) / (NIR + RED)
with NIR = B05 and RED = B04; observations flagged as cloud, cloud shadow, adjacent cloud, snow/ice
or water in Fmask are excluded. Not every date has a clear observation.
"""
from ..config import get_settings
from .appeears import Layer
from .hls_common import compute_ndvi_records

DATASET = "landsat"


def layers() -> list[Layer]:
    p = get_settings().hls_landsat_product
    return [Layer(p, "B04"), Layer(p, "B05"), Layer(p, "Fmask")]


def parse(rows, lat, lon, source_url):
    red, nir, fmask = layers()
    return compute_ndvi_records(rows, red, nir, fmask, DATASET, f"{get_settings().hls_landsat_product} (Landsat OLI)",
                                lat, lon, source_url)
