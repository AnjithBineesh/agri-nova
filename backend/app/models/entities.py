from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, GeoJSONGeometry


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    country: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["User"]] = relationship(back_populates="organisation")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default="farmer")  # farmer | researcher | organisation | admin
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id", ondelete="SET NULL"))
    preferences: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organisation: Mapped[Organisation | None] = relationship(back_populates="members")
    farms: Mapped[list["Farm"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    farm_name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(150))  # district or region
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location: Mapped[dict | None] = mapped_column(GeoJSONGeometry("POINT"))
    location_source: Mapped[str] = mapped_column(String(20), default="map")  # gps | map | manual
    boundary: Mapped[dict | None] = mapped_column(GeoJSONGeometry("POLYGON"))
    # none: only a point is known; user_drawn: polygon drawn by the user; verified: surveyed/verified field
    boundary_status: Mapped[str] = mapped_column(String(20), default="none")
    area_ha: Mapped[float | None] = mapped_column(Float)
    area_source: Mapped[str | None] = mapped_column(String(30))  # user_entered | computed_from_boundary
    soil_type: Mapped[str | None] = mapped_column(String(100))
    current_crop: Mapped[str | None] = mapped_column(String(60))
    previous_crops: Mapped[list | None] = mapped_column(JSON, default=list)
    irrigation_type: Mapped[str] = mapped_column(String(30), default="none")  # none | supplemental | full
    irrigation_capacity_mm: Mapped[float | None] = mapped_column(Float)  # water available per season
    growing_seasons: Mapped[list | None] = mapped_column(JSON, default=list)
    farming_method: Mapped[str | None] = mapped_column(String(60))
    residue_management: Mapped[str] = mapped_column(String(30), default="partial")  # removed | partial | retained
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="farms")
    soil_profiles: Mapped[list["SoilProfile"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    soil_reports: Mapped[list["SoilReport"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    crop_history: Mapped[list["CropHistory"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    observations: Mapped[list["EarthObservation"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    fetch_status: Mapped[list["DatasetFetchStatus"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class SoilProfile(Base):
    __tablename__ = "soil_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    ph: Mapped[float | None] = mapped_column(Float)
    nitrogen: Mapped[float | None] = mapped_column(Float)
    nitrogen_unit: Mapped[str | None] = mapped_column(String(20))
    phosphorus: Mapped[float | None] = mapped_column(Float)
    phosphorus_unit: Mapped[str | None] = mapped_column(String(20))
    phosphorus_method: Mapped[str | None] = mapped_column(String(30))  # olsen | bray1 | mehlich3 | unknown
    potassium: Mapped[float | None] = mapped_column(Float)
    potassium_unit: Mapped[str | None] = mapped_column(String(20))
    organic_carbon: Mapped[float | None] = mapped_column(Float)  # percent
    organic_matter: Mapped[float | None] = mapped_column(Float)  # percent
    soil_texture: Mapped[str | None] = mapped_column(String(40))
    soil_depth_cm: Mapped[float | None] = mapped_column(Float)
    water_holding_capacity: Mapped[float | None] = mapped_column(Float)  # mm per m of soil
    drainage: Mapped[str | None] = mapped_column(String(40))
    electrical_conductivity: Mapped[float | None] = mapped_column(Float)  # dS/m
    measurement_date: Mapped[date | None] = mapped_column(Date)
    data_source: Mapped[str] = mapped_column(String(40), default="manual")  # manual | lab_report_confirmed
    value_status: Mapped[dict | None] = mapped_column(JSON, default=dict)  # field -> measured|estimated
    report_id: Mapped[int | None] = mapped_column(ForeignKey("soil_reports.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="soil_profiles")


class SoilReport(Base):
    __tablename__ = "soil_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    report_date: Mapped[date | None] = mapped_column(Date)
    laboratory: Mapped[str | None] = mapped_column(String(255))
    extraction_method: Mapped[str | None] = mapped_column(String(30))  # pdf_text | ocr
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extracted_values: Mapped[dict | None] = mapped_column(JSON, default=dict)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | confirmed | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    farm: Mapped[Farm] = relationship(back_populates="soil_reports")


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    crop_name: Mapped[str] = mapped_column(String(100))
    crop_family: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(30))
    duration: Mapped[dict] = mapped_column(JSON)
    water_requirement: Mapped[dict] = mapped_column(JSON)
    nutrient_requirements: Mapped[dict] = mapped_column(JSON)
    climate_requirements: Mapped[dict] = mapped_column(JSON)
    soil_preferences: Mapped[dict] = mapped_column(JSON)
    nitrogen_fixation: Mapped[bool] = mapped_column(Boolean, default=False)
    root_characteristics: Mapped[dict] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)  # complete record incl. rotation notes, pests, sources
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CropHistory(Base):
    __tablename__ = "crop_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crops.id", ondelete="SET NULL"))
    crop_slug: Mapped[str] = mapped_column(String(60))
    season: Mapped[str] = mapped_column(String(60))
    year: Mapped[int] = mapped_column(Integer)

    farm: Mapped[Farm] = relationship(back_populates="crop_history")


class EarthObservation(Base):
    __tablename__ = "earth_observations"
    __table_args__ = (
        Index("ix_obs_farm_dataset_var_date", "farm_id", "dataset", "variable", "observation_date"),
        UniqueConstraint("farm_id", "dataset", "product_id", "variable", "observation_date", "temporal_resolution",
                         name="uq_observation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(40))
    product_id: Mapped[str] = mapped_column(String(80))
    variable: Mapped[str] = mapped_column(String(80))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    observation_date: Mapped[date] = mapped_column(Date)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    resolution: Mapped[str | None] = mapped_column(String(60))
    temporal_resolution: Mapped[str] = mapped_column(String(30), default="daily")
    quality_flag: Mapped[str | None] = mapped_column(String(60))
    data_type: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(String(600))
    processing_status: Mapped[str] = mapped_column(String(30), default="processed")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="observations")


class DatasetFetchStatus(Base):
    __tablename__ = "dataset_fetch_status"
    __table_args__ = (UniqueConstraint("farm_id", "dataset", name="uq_fetch_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text)
    external_task_id: Mapped[str | None] = mapped_column(String(120))
    last_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_start: Mapped[date | None] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    farm: Mapped[Farm] = relationship(back_populates="fetch_status")


class ApiCache(Base):
    __tablename__ = "api_cache"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(String(40), index=True)
    strategy_key: Mapped[str] = mapped_column(String(40))
    strategy_name: Mapped[str] = mapped_column(String(120))
    crop_sequence: Mapped[list] = mapped_column(JSON)
    suitability_score: Mapped[float | None] = mapped_column(Float)
    priority_weights: Mapped[dict] = mapped_column(JSON)
    scores: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[dict] = mapped_column(JSON)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="recommendations")


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"))
    planning_horizon: Mapped[str] = mapped_column(String(20))
    scenario_inputs: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    assumptions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="simulations")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(20))  # farmer | scientific
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="reports")
