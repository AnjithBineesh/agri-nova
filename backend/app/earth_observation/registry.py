"""Catalogue of every dataset Agri Nova knows about, with provenance and integration status."""
from .base import DatasetInfo, DataType

DATASETS: dict[str, DatasetInfo] = {d.key: d for d in [
    DatasetInfo(
        key="nasa_power", name="NASA POWER", provider="NASA Langley Research Center",
        products="POWER Agroclimatology (AG) daily & monthly point API",
        spatial_resolution="0.5° x 0.625° meteorology; 1° x 1° solar", temporal_resolution="daily, monthly",
        coverage="Global, 1981–present (meteorology), 1984–present (solar)",
        data_type=DataType.WEATHER_CLIMATE_ESTIMATE, access="Public REST API, no credentials",
        requires_credentials=False, integration="integrated",
        documentation_url="https://power.larc.nasa.gov/docs/services/api/",
        notes="Model/reanalysis-based estimates for a coarse grid cell; not field-scale measurements.",
        variables=("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M")),
    DatasetInfo(
        key="gpm_imerg", name="GPM IMERG", provider="NASA GSFC / GES DISC",
        products="GPM_3IMERGDF V07 (Final Run); GPM_3IMERGDL V07 (Late Run)",
        spatial_resolution="0.1° x 0.1° (~11 km)", temporal_resolution="daily",
        coverage="Global 60°N–60°S (fractional coverage beyond), June 2000–present",
        data_type=DataType.SATELLITE_OBSERVATION, access="Giovanni time-series API, Earthdata Login token",
        requires_credentials=True, integration="integrated",
        documentation_url="https://gpm.nasa.gov/data/imerg",
        notes="Final Run is gauge-adjusted research quality (~3.5 month latency). Late Run is provisional "
              "near-real-time (~14 h latency) and is used only after the Final Run record ends.",
        variables=("precipitation",)),
    DatasetInfo(
        key="smap", name="SMAP Soil Moisture", provider="NASA JPL / NSIDC DAAC",
        products="SPL3SMP_E (Enhanced L3, surface); SPL4SMGP (L4, surface & root zone)",
        spatial_resolution="9 km EASE-Grid 2.0", temporal_resolution="daily (L3), 3-hourly (L4)",
        coverage="Global, March 2015–present", data_type=DataType.SATELLITE_OBSERVATION,
        access="AppEEARS point API, Earthdata Login", requires_credentials=True, integration="integrated",
        documentation_url="https://nsidc.org/data/smap/data",
        notes="L3 surface (~0–5 cm) moisture is a satellite retrieval; L4 root zone (0–100 cm) is a "
              "model estimate with SMAP assimilation. Neither is a lab water-holding-capacity measurement.",
        variables=("surface_soil_moisture", "rootzone_soil_moisture")),
    DatasetInfo(
        key="modis", name="MODIS Vegetation Indices", provider="NASA LP DAAC",
        products="MOD13Q1 v061 NDVI/EVI", spatial_resolution="250 m", temporal_resolution="16-day composite",
        coverage="Global, 2000–present", data_type=DataType.DERIVED_SATELLITE_INDICATOR,
        access="AppEEARS point API, Earthdata Login", requires_credentials=True, integration="integrated",
        documentation_url="https://modis.gsfc.nasa.gov/data/dataprod/mod13.php",
        notes="Composites with pixel reliability 'good' or 'marginal' are retained; cloudy pixels are excluded.",
        variables=("ndvi", "evi")),
    DatasetInfo(
        key="landsat", name="Landsat 8/9 (HLS L30)", provider="NASA LP DAAC / USGS",
        products="HLSL30 v2.0 surface reflectance → NDVI", spatial_resolution="30 m",
        temporal_resolution="~8 days combined L8+L9 (clear-sky dependent)", coverage="Global land, 2013–present",
        data_type=DataType.DERIVED_SATELLITE_INDICATOR, access="AppEEARS point API, Earthdata Login",
        requires_credentials=True, integration="integrated",
        documentation_url="https://www.usgs.gov/landsat-missions/landsat-data-access",
        notes="NDVI = (B05 − B04)/(B05 + B04); Fmask cloud/shadow/snow/water observations removed.",
        variables=("ndvi",)),
    DatasetInfo(
        key="sentinel2", name="Sentinel-2 (HLS S30)", provider="ESA Copernicus via NASA LP DAAC",
        products="HLSS30 v2.0 surface reflectance → NDVI", spatial_resolution="30 m (harmonised)",
        temporal_resolution="~5 days (clear-sky dependent)", coverage="Global land, 2015–present",
        data_type=DataType.DERIVED_SATELLITE_INDICATOR, access="AppEEARS point API, Earthdata Login",
        requires_credentials=True, integration="integrated", documentation_url="https://dataspace.copernicus.eu/",
        notes="Native 10–20 m Sentinel-2 L2A from Copernicus Data Space can be added via the same interface.",
        variables=("ndvi",)),
    DatasetInfo(
        key="ecostress", name="ECOSTRESS", provider="NASA JPL / LP DAAC",
        products="ECO_L2T_LSTE v002 (LST); ECO_L3T_JET v002 (ET)", spatial_resolution="70 m",
        temporal_resolution="irregular ISS overpasses", coverage="~52°N–52°S, July 2018–present",
        data_type=DataType.SATELLITE_OBSERVATION, access="AppEEARS point API, Earthdata Login",
        requires_credentials=True, integration="integrated", documentation_url="https://ecostress.jpl.nasa.gov/data",
        notes="Sporadic observations at varying times of day – not continuous monitoring.",
        variables=("land_surface_temperature", "evapotranspiration")),
    DatasetInfo(
        key="srtm", name="SRTM Elevation", provider="NASA / NGA via LP DAAC",
        products="SRTMGL1_NC v003", spatial_resolution="1 arc-second (~30 m)", temporal_resolution="static (2000)",
        coverage="60°N–56°S", data_type=DataType.SATELLITE_OBSERVATION,
        access="AppEEARS point API, Earthdata Login", requires_credentials=True, integration="integrated",
        documentation_url="https://search.earthdata.nasa.gov/search?q=SRTM",
        notes="Slope from a 3x3 elevation window (Horn 1981); slope alone is not an erosion model.",
        variables=("elevation", "slope")),
    DatasetInfo(
        key="era5", name="ERA5 Reanalysis", provider="ECMWF / Copernicus C3S",
        products="reanalysis-era5-single-levels-timeseries", spatial_resolution="0.25° (~31 km)",
        temporal_resolution="hourly", coverage="Global, 1940–present", data_type=DataType.WEATHER_CLIMATE_ESTIMATE,
        access="CDS API key", requires_credentials=True, integration="interface_only",
        documentation_url="https://cds.climate.copernicus.eu/", notes="Adapter interface defined; not yet retrieved."),
    DatasetInfo(
        key="gaez", name="FAO GAEZ v5", provider="FAO / IIASA", products="Crop suitability & attainable yield rasters",
        spatial_resolution="5 arc-minutes (~9 km) and 30 arc-seconds", temporal_resolution="climatological periods",
        coverage="Global", data_type=DataType.MODEL_ESTIMATE, access="FAO data portal downloads",
        requires_credentials=False, integration="interface_only", documentation_url="https://www.fao.org/gaez/en",
        notes="Agricultural knowledge source (not a NASA dataset). Raster sampling planned."),
]}

# Provider-neutral names and status messages used in the website and reports.
DISPLAY_NAMES = {
    "nasa_power": "Weather and climate record", "gpm_imerg": "Observed rainfall", "smap": "Soil moisture",
    "modis": "Vegetation index (250 m)", "landsat": "Vegetation index (30 m, source A)",
    "sentinel2": "Vegetation index (30 m, source B)", "ecostress": "Surface temperature and evapotranspiration",
    "srtm": "Elevation and slope", "era5": "Reanalysis climate", "gaez": "Agro-ecological zones",
}
DISPLAY_RESOLUTION = {
    "nasa_power": "about 50 km", "gpm_imerg": "about 11 km", "smap": "9 km", "modis": "250 m", "landsat": "30 m",
    "sentinel2": "30 m", "ecostress": "70 m", "srtm": "30 m", "era5": "about 31 km", "gaez": "about 9 km",
}
STATUS_MESSAGES = {
    "complete": "Retrieved for this farm.",
    "pending": "Requested. Processing usually takes minutes to a few hours; this page checks automatically.",
    "processing": "Being processed. This page checks automatically.",
    "failed": "Couldn't be retrieved right now. Try again later.",
    "not_configured": "Not set up on this server yet (data access account needed).",
    "not_integrated": "Planned for a future update.",
    "not_requested": "Not requested yet.",
    "no_data": "No usable observations for this location and period (for example, persistent cloud).",
    "demonstration": "Demonstration values, not real observations.",
}

APPEEARS_TIMESERIES = ("smap", "modis", "landsat", "sentinel2", "ecostress")
APPEEARS_DATASETS = APPEEARS_TIMESERIES + ("srtm",)
