"""Application configuration loaded from environment variables.

Secrets (JWT key, NASA Earthdata credentials, CDS key) are read only on the
server side and are never sent to the frontend.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Agri Nova API"
    environment: str = "development"

    # Database: SQLite for local development, PostgreSQL + PostGIS for production.
    database_url: str = f"sqlite:///{(BASE_DIR / 'agrinova.db').as_posix()}"
    use_postgis: bool = False

    # Security
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # File storage
    storage_backend: str = "local"  # local | s3
    storage_dir: Path = BASE_DIR / "storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    max_upload_mb: int = 15

    # NASA POWER (no credentials required)
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api"
    nasa_power_community: str = "AG"

    # NASA Earthdata Login (required for GPM via Giovanni, and AppEEARS products)
    earthdata_username: str | None = None
    earthdata_password: str | None = None
    earthdata_token: str | None = None  # EDL bearer token (alternative to username/password)

    giovanni_timeseries_url: str = "https://api.giovanni.earthdata.nasa.gov/timeseries"
    gpm_imerg_final_variable: str = "GPM_3IMERGDF_07_precipitation"
    gpm_imerg_late_variable: str = "GPM_3IMERGDL_07_precipitation"

    appeears_base_url: str = "https://appeears.earthdatacloud.nasa.gov/api"
    # AppEEARS product identifiers. Verify against GET {appeears_base_url}/product,
    # because DAACs periodically release new versions and retire old ones.
    smap_l3_product: str = "SPL3SMP_E.006"
    smap_l3_layer: str = "Soil_Moisture_Retrieval_Data_AM_soil_moisture"
    smap_l3_qa_layer: str = "Soil_Moisture_Retrieval_Data_AM_retrieval_qual_flag"
    smap_l4_product: str = "SPL4SMGP.008"
    smap_l4_surface_layer: str = "Geophysical_Data_sm_surface"
    smap_l4_rootzone_layer: str = "Geophysical_Data_sm_rootzone"
    modis_vi_product: str = "MOD13Q1.061"
    hls_landsat_product: str = "HLSL30.020"
    hls_sentinel_product: str = "HLSS30.020"
    ecostress_lst_product: str = "ECO_L2T_LSTE.002"
    ecostress_et_product: str = "ECO_L3T_JET.002"
    ecostress_et_layer: str = "ETdaily"
    srtm_product: str = "SRTMGL1_NC.003"

    # Copernicus Climate Data Store (ERA5) – adapter interface only in this release.
    cds_api_key: str | None = None

    # HTTP behaviour
    http_timeout_seconds: float = 45.0
    http_max_retries: int = 3
    cache_ttl_hours: int = 24 * 7

    # Demonstration data. NEVER enabled by default. When enabled, every value
    # generated is labelled "demonstration" end-to-end and is never stored as a
    # NASA observation.
    enable_demo_data: bool = False

    tesseract_cmd: str = "tesseract"

    upload_allowed_types: list[str] = Field(default_factory=lambda: ["application/pdf", "image/jpeg", "image/png"])

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def earthdata_configured(self) -> bool:
        return bool(self.earthdata_token or (self.earthdata_username and self.earthdata_password))


@lru_cache
def get_settings() -> Settings:
    return Settings()
