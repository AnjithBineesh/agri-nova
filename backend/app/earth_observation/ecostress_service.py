"""ECOSTRESS (ISS) land surface temperature and evapotranspiration via AppEEARS.

ECO_L2T_LSTE v002 (70 m tiled LST) and ECO_L3T_JET v002 (70 m JPL ensemble ET). The ISS orbit gives an
irregular revisit at varying times of day, so observations are sporadic – this is not continuous or
daily monitoring of a field.
"""
from ..config import get_settings
from .appeears import Layer, find_value, row_date
from .base import DataType, ObservationRecord

DATASET = "ecostress"
RES = "70 m"


def layers() -> list[Layer]:
    s = get_settings()
    return [Layer(s.ecostress_lst_product, "LST"), Layer(s.ecostress_lst_product, "cloud"),
            Layer(s.ecostress_et_product, s.ecostress_et_layer)]


def parse(rows, lat, lon, source_url):
    s = get_settings()
    lst_l, cloud_l, et_l = layers()
    out = []
    for row in rows:
        d = row_date(row)
        if d is None:
            continue
        lst = find_value(row, lst_l)
        cloud = find_value(row, cloud_l)
        if lst is not None and 200 < lst < 350 and (cloud is None or int(cloud) == 0):
            out.append(ObservationRecord(
                dataset=DATASET, product_id=s.ecostress_lst_product, variable="land_surface_temperature",
                value=round(lst - 273.15, 2), unit="°C", observation_date=d, latitude=lat, longitude=lon,
                spatial_resolution=RES, temporal_resolution="irregular (ISS overpass)", source_url=source_url,
                data_type=DataType.SATELLITE_OBSERVATION,
                quality="cloud-free" if cloud is not None else "cloud mask unavailable"))
        et = find_value(row, et_l)
        if et is not None and 0 <= et < 25:
            out.append(ObservationRecord(
                dataset=DATASET, product_id=s.ecostress_et_product, variable="evapotranspiration", value=round(et, 3),
                unit="mm/day", observation_date=d, latitude=lat, longitude=lon, spatial_resolution=RES,
                temporal_resolution="irregular (ISS overpass)", source_url=source_url,
                data_type=DataType.DERIVED_SATELLITE_INDICATOR, quality="model-derived from LST"))
    return out
