"""FAO GAEZ v5 (Global Agro-Ecological Zones) – adapter interface.

GAEZ is an FAO/IIASA agricultural knowledge and spatial dataset, not a NASA mission dataset.
Status: interface only. GAEZ v5 rasters (agro-climatic suitability, attainable yield, soil and terrain
constraints, historical and future climate) are published through the FAO data portal
(https://data.apps.fao.org/). Planned integration samples the 5-arc-minute suitability index rasters at
the farm location using Rasterio. Until then the crop suitability engine uses its transparent rule-based
assessment with crop requirements drawn from FAO references.
"""
from .base import AdapterResult, FetchState

DATASET = "gaez"


def fetch(*_args, **_kwargs) -> AdapterResult:
    return AdapterResult(DATASET, FetchState.NOT_INTEGRATED,
                         message="FAO GAEZ v5 raster sampling is planned; rule-based suitability is used meanwhile.")
