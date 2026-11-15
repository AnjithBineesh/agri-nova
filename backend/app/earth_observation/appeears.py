"""Client for NASA AppEEARS (Application for Extracting and Exploring Analysis Ready Samples).

API docs: https://appeears.earthdatacloud.nasa.gov/api/
AppEEARS point requests are asynchronous: a task is submitted, processed on
NASA infrastructure (minutes to hours), and the results are downloaded as CSV.
Requires NASA Earthdata Login credentials.
"""
import csv
import io
from dataclasses import dataclass
from datetime import date

from ..config import get_settings
from .earthdata_auth import basic_auth_header
from .http import UpstreamError, request_with_retries


@dataclass(frozen=True)
class Layer:
    product: str
    layer: str

    @property
    def column(self) -> str:
        return f"{self.product.replace('.', '_')}_{self.layer}"

    def as_dict(self) -> dict:
        return {"product": self.product, "layer": self.layer}


class AppEEARSClient:
    def __init__(self):
        self.s = get_settings()
        self.base = self.s.appeears_base_url.rstrip("/")
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.s.earthdata_username and self.s.earthdata_password) or bool(self.s.earthdata_token)

    def token(self) -> str:
        if self._token:
            return self._token
        if self.s.earthdata_username and self.s.earthdata_password:
            resp = request_with_retries("POST", f"{self.base}/login", headers={
                "Authorization": basic_auth_header(self.s.earthdata_username, self.s.earthdata_password),
                "Content-Length": "0"})
            if resp.status_code != 200:
                raise UpstreamError(f"AppEEARS login failed (HTTP {resp.status_code})", resp.status_code)
            self._token = resp.json()["token"]
        elif self.s.earthdata_token:
            self._token = self.s.earthdata_token
        else:
            raise UpstreamError("Earthdata credentials are not configured")
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def submit_point_task(self, name: str, layers: list[Layer], coordinates: list[dict], start: date, end: date
                          ) -> str:
        task = {
            "task_type": "point",
            "task_name": name,
            "params": {
                "dates": [{"startDate": start.strftime("%m-%d-%Y"), "endDate": end.strftime("%m-%d-%Y")}],
                "layers": [lyr.as_dict() for lyr in layers],
                "coordinates": coordinates,
            },
        }
        resp = request_with_retries("POST", f"{self.base}/task", json=task, headers=self._headers(), max_retries=1)
        if resp.status_code not in (200, 202):
            raise UpstreamError(f"AppEEARS task submission failed (HTTP {resp.status_code}): {resp.text[:300]}",
                                resp.status_code)
        return resp.json()["task_id"]

    def task_status(self, task_id: str) -> str:
        resp = request_with_retries("GET", f"{self.base}/task/{task_id}", headers=self._headers(), timeout=20)
        if resp.status_code != 200:
            raise UpstreamError(f"AppEEARS status check failed (HTTP {resp.status_code})", resp.status_code)
        return resp.json().get("status", "unknown")

    def bundle_csvs(self, task_id: str) -> dict[str, str]:
        resp = request_with_retries("GET", f"{self.base}/bundle/{task_id}", headers=self._headers())
        if resp.status_code != 200:
            raise UpstreamError(f"AppEEARS bundle listing failed (HTTP {resp.status_code})", resp.status_code)
        out = {}
        for f in resp.json().get("files", []):
            if f.get("file_name", "").endswith(".csv") and "results" in f["file_name"]:
                dl = request_with_retries("GET", f"{self.base}/bundle/{task_id}/{f['file_id']}",
                                          headers=self._headers(), timeout=120)
                if dl.status_code == 200:
                    out[f["file_name"]] = dl.text
        return out

    def task_url(self, task_id: str) -> str:
        return f"{self.base}/task/{task_id}"


def parse_point_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def find_value(row: dict, layer: Layer) -> float | None:
    raw = row.get(layer.column)
    if raw is None:
        # Fall back to suffix matching in case of minor naming differences.
        prefix = layer.product.split(".")[0]
        for k, v in row.items():
            if k and k.endswith(layer.layer) and k.startswith(prefix):
                raw = v
                break
    if raw in (None, "", "NA", "nan"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def row_date(row: dict) -> date | None:
    raw = (row.get("Date") or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
