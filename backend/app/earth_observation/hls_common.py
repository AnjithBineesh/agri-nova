"""Shared NDVI computation for NASA Harmonized Landsat Sentinel-2 (HLS v2.0) surface reflectance."""
from .appeears import Layer, find_value, row_date
from .base import DataType, ObservationRecord

# HLS v2.0 Fmask bits: 1 cloud, 2 adjacent to cloud/shadow, 3 cloud shadow, 4 snow/ice, 5 water.
FMASK_REJECT_BITS = (1, 2, 3, 4, 5)


def fmask_clear(fmask: float | None) -> bool:
    if fmask is None or fmask >= 255:
        return False
    f = int(fmask)
    return not any(f & (1 << b) for b in FMASK_REJECT_BITS)


def _refl(v: float | None) -> float | None:
    if v is None or v <= -9999:
        return None
    if abs(v) > 2:  # integer reflectance, scale factor 0.0001
        v *= 0.0001
    return v if 0 <= v <= 1.2 else None


def compute_ndvi_records(rows: list[dict], red: Layer, nir: Layer, fmask: Layer, dataset: str, product_label: str,
                         lat: float, lon: float, source_url: str) -> list[ObservationRecord]:
    out = []
    for row in rows:
        d = row_date(row)
        if d is None:
            continue
        if not fmask_clear(find_value(row, fmask)):
            continue
        r, n = _refl(find_value(row, red)), _refl(find_value(row, nir))
        if r is None or n is None or (n + r) <= 0:
            continue
        ndvi = (n - r) / (n + r)
        out.append(ObservationRecord(
            dataset=dataset, product_id=product_label, variable="ndvi", value=round(ndvi, 4), unit="index",
            observation_date=d, latitude=lat, longitude=lon, spatial_resolution="30 m",
            temporal_resolution="per clear overpass", source_url=source_url,
            data_type=DataType.DERIVED_SATELLITE_INDICATOR, quality="clear (Fmask)"))
    return out
