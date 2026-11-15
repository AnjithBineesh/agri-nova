"""Quick NASA POWER look-up for any coordinates (used while registering a farm)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..agriculture.weather_summary import summarise
from ..authentication.deps import get_current_user
from ..database import get_db
from ..earth_observation.http import UpstreamError
from ..earth_observation.nasa_power_service import fetch_nasa_power, parse_power_response
from ..models import User

router = APIRouter(prefix="/api/power", tags=["earth observation"])


@router.get("/preview")
def preview(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    try:
        data, url = fetch_nasa_power(db, latitude, longitude)
    except UpstreamError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The weather service is not reachable right now. Please try again later.")
    daily: dict = {}
    for r in parse_power_response(data, "daily", latitude, longitude, url):
        daily.setdefault(r.observation_date, {})[r.variable] = r.value
    out = summarise(daily, None, today)
    out.pop("days", None)
    out.update({"source_url": url, "year": today.year})
    return out
