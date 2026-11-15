"""NASA Earthdata Login (EDL) bearer token handling. Server-side only."""
import base64
from datetime import datetime, timedelta, timezone

from ..config import get_settings
from .http import UpstreamError, request_with_retries

EDL_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"

_cached: dict = {}


def basic_auth_header(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


def get_edl_token() -> str | None:
    s = get_settings()
    if s.earthdata_token:
        return s.earthdata_token
    if not (s.earthdata_username and s.earthdata_password):
        return None
    if _cached.get("token") and _cached["expires"] > datetime.now(timezone.utc):
        return _cached["token"]
    resp = request_with_retries("POST", EDL_TOKEN_URL,
                                headers={"Authorization": basic_auth_header(s.earthdata_username,
                                                                            s.earthdata_password)})
    if resp.status_code != 200:
        raise UpstreamError(f"Earthdata Login token request failed (HTTP {resp.status_code})", resp.status_code)
    data = resp.json()
    _cached["token"] = data["access_token"]
    _cached["expires"] = datetime.now(timezone.utc) + timedelta(days=30)
    return _cached["token"]
