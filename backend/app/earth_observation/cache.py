"""Database-backed response cache so identical upstream requests are not repeated."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ApiCache


def cache_key(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(db: Session, key: str):
    row = db.get(ApiCache, key)
    if row is None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return None
    return json.loads(row.payload)


def cache_set(db: Session, key: str, payload, ttl_hours: float | None = None) -> None:
    ttl = ttl_hours if ttl_hours is not None else get_settings().cache_ttl_hours
    now = datetime.now(timezone.utc)
    row = db.get(ApiCache, key)
    if row is None:
        row = ApiCache(key=key)
        db.add(row)
    row.payload = json.dumps(payload, default=str)
    row.created_at = now
    row.expires_at = now + timedelta(hours=ttl)
    db.commit()
