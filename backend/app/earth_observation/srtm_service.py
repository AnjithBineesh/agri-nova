"""SRTM terrain via AppEEARS (SRTMGL1_NC v003, 1 arc-second ≈ 30 m).

Elevation is sampled on a 3 x 3 grid centred on the farm point and slope is derived with Horn's (1981)
finite-difference method. Slope is one input to runoff / erosion considerations – it is not an erosion
model on its own.
"""
import math
from datetime import date

from ..config import get_settings
from .appeears import Layer, find_value
from .base import DataType, ObservationRecord

DATASET = "srtm"
STEP_DEG = 1 / 3600  # one arc-second
SRTM_DATE = date(2000, 2, 11)


def layers() -> list[Layer]:
    return [Layer(get_settings().srtm_product, "SRTMGL1_DEM")]


def grid_coordinates(lat: float, lon: float) -> list[dict]:
    coords = []
    for i, dy in enumerate((1, 0, -1)):  # north to south
        for j, dx in enumerate((-1, 0, 1)):  # west to east
            coords.append({"id": f"g{i}{j}", "latitude": round(lat + dy * STEP_DEG, 6),
                           "longitude": round(lon + dx * STEP_DEG, 6), "category": "terrain"})
    return coords


def horn_slope_deg(z: list[list[float]], dx_m: float, dy_m: float) -> float:
    a, b, c = z[0]
    d, _, f = z[1]
    g, h, i = z[2]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy_m)
    return math.degrees(math.atan(math.hypot(dzdx, dzdy)))


def parse(rows, lat, lon, source_url):
    lyr = layers()[0]
    grid: dict[str, float] = {}
    for row in rows:
        v = find_value(row, lyr)
        pid = row.get("ID", "")
        if v is not None and v > -1000 and pid.startswith("g"):
            grid[pid] = v
    out = []
    if "g11" in grid:
        out.append(ObservationRecord(
            dataset=DATASET, product_id=get_settings().srtm_product, variable="elevation", value=grid["g11"],
            unit="m", observation_date=SRTM_DATE, latitude=lat, longitude=lon, spatial_resolution="30 m",
            temporal_resolution="static (Feb 2000)", source_url=source_url,
            data_type=DataType.SATELLITE_OBSERVATION, quality="ok"))
    if len(grid) == 9:
        z = [[grid[f"g{i}{j}"] for j in range(3)] for i in range(3)]
        dy = STEP_DEG * 111_320
        dx = STEP_DEG * 111_320 * math.cos(math.radians(lat))
        out.append(ObservationRecord(
            dataset=DATASET, product_id=get_settings().srtm_product, variable="slope",
            value=round(horn_slope_deg(z, dx, dy), 2), unit="degrees", observation_date=SRTM_DATE, latitude=lat,
            longitude=lon, spatial_resolution="30 m (3x3 window)", temporal_resolution="static (Feb 2000)",
            source_url=source_url, data_type=DataType.DERIVED_SATELLITE_INDICATOR, quality="Horn 1981"))
    return out
