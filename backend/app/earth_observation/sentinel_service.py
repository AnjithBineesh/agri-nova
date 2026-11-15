"""ESA Sentinel-2 NDVI via NASA HLSS30 v2.0 (Sentinel-2 MSI harmonised surface reflectance, 30 m).

Native Sentinel-2 L2A (10–20 m) from the Copernicus Data Space Ecosystem can be added through the
same adapter interface; HLSS30 is used here because it is distributed through NASA Earthdata and
is radiometrically harmonised with Landsat. NIR = B8A, RED = B04.
"""
from ..config import get_settings
from .appeears import Layer
from .hls_common import compute_ndvi_records

DATASET = "sentinel2"


def layers() -> list[Layer]:
    p = get_settings().hls_sentinel_product
    return [Layer(p, "B04"), Layer(p, "B8A"), Layer(p, "Fmask")]


def parse(rows, lat, lon, source_url):
    red, nir, fmask = layers()
    return compute_ndvi_records(rows, red, nir, fmask, DATASET,
                                f"{get_settings().hls_sentinel_product} (Sentinel-2 MSI)", lat, lon, source_url)
