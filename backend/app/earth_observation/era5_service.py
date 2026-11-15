"""ERA5 reanalysis (Copernicus Climate Data Store) – adapter interface.

Status: interface only. Planned implementation uses the CDS API dataset
"reanalysis-era5-single-levels-timeseries" (point time series, CSV) with a personal CDS API key
(CDS_API_KEY). ERA5 is a reanalysis (model + observations) at ~0.25° (~31 km), hourly from 1940.
NASA POWER already supplies the climate variables required by the MVP engines.
"""
from .base import AdapterResult, FetchState

DATASET = "era5"


def fetch(*_args, **_kwargs) -> AdapterResult:
    return AdapterResult(DATASET, FetchState.NOT_INTEGRATED,
                         message="ERA5 adapter interface defined; CDS retrieval scheduled for a later phase. "
                                 "NASA POWER provides the climate variables used by the current engines.")
