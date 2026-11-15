"""Database engine, session handling and a portable geometry column type.

* With PostgreSQL + PostGIS (``USE_POSTGIS=true``) geometry columns are native
  ``geometry(…, 4326)`` columns, written with ``ST_GeomFromGeoJSON`` and read
  with ``ST_AsGeoJSON`` so the application always works with GeoJSON.
* With SQLite (local development and tests) the same columns are stored as
  GeoJSON text so the application runs without a spatial database.
"""
import json
from collections.abc import Generator

from sqlalchemy import Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator, UserDefinedType

from .config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class _PostGISGeometry(UserDefinedType):
    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326):
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **kw):
        return f"geometry({self.geometry_type},{self.srid})"


class GeoJSONGeometry(TypeDecorator):
    """Stores a GeoJSON geometry dict. PostGIS-native when enabled."""

    impl = Text
    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326, **kw):
        self.geometry_type = geometry_type
        self.srid = srid
        super().__init__(**kw)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and settings.use_postgis:
            return dialect.type_descriptor(_PostGISGeometry(self.geometry_type, self.srid))
        return dialect.type_descriptor(Text())

    def bind_expression(self, bindvalue):
        if engine.dialect.name == "postgresql" and settings.use_postgis:
            return func.ST_SetSRID(func.ST_GeomFromGeoJSON(bindvalue), self.srid)
        return bindvalue

    def column_expression(self, col):
        if engine.dialect.name == "postgresql" and settings.use_postgis:
            return func.ST_AsGeoJSON(col)
        return col

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value) if isinstance(value, str) else value


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)

    if engine.dialect.name == "postgresql" and settings.use_postgis:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=engine)
