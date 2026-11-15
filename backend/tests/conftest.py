import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="agrinova-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "STORAGE_DIR": f"{_tmp}/storage",
    "ENABLE_DEMO_DATA": "true",
    "JWT_SECRET_KEY": "test-secret-key-with-sufficient-length-0123456789",
    "HTTP_MAX_RETRIES": "0",
    "HTTP_TIMEOUT_SECONDS": "2",
    "NASA_POWER_BASE_URL": "http://127.0.0.1:9/api",  # unreachable on purpose: tests never call NASA
    "EARTHDATA_USERNAME": "",
    "EARTHDATA_PASSWORD": "",
    "EARTHDATA_TOKEN": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register(client, email, role="farmer", org=None):
    body = {"name": email.split("@")[0].title(), "email": email, "password": "password123", "role": role}
    if org:
        body["organisation_name"] = org
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


FARM = {
    "farm_name": "Test Farm", "country": "India", "state": "Maharashtra", "region": "Pune",
    "latitude": 18.52, "longitude": 73.85, "location_source": "manual", "irrigation_type": "supplemental",
    "irrigation_capacity_mm": 150, "current_crop": "maize",
    "growing_seasons": [{"name": "Kharif", "start_month": 6, "end_month": 10},
                        {"name": "Rabi", "start_month": 11, "end_month": 3}],
    "crop_history": [{"crop_slug": "maize", "season": "Kharif", "year": 2025},
                     {"crop_slug": "wheat", "season": "Rabi", "year": 2025}],
}
