"""Shared HTTP client with timeouts, bounded retries and exponential backoff."""
import logging
import time

import httpx

from ..config import get_settings

log = logging.getLogger("agrinova.http")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class UpstreamError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def request_with_retries(method: str, url: str, *, max_retries: int | None = None, timeout: float | None = None,
                         client: httpx.Client | None = None, **kwargs) -> httpx.Response:
    settings = get_settings()
    retries = settings.http_max_retries if max_retries is None else max_retries
    timeout = timeout or settings.http_timeout_seconds
    own_client = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True,
                                    headers={"User-Agent": "AgriNova/1.0 (NASA Space Apps decision support)"})
    last_exc: Exception | None = None
    try:
        for attempt in range(retries + 1):
            try:
                resp = client.request(method, url, **kwargs)
                if resp.status_code in RETRYABLE_STATUS and attempt < retries:
                    wait = _retry_after(resp) or 2 ** attempt
                    log.warning("Upstream %s returned %s; retrying in %ss", url, resp.status_code, wait)
                    time.sleep(min(wait, 30))
                    continue
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 30))
                    continue
        raise UpstreamError(f"Could not reach {httpx.URL(url).host}: {last_exc}")
    finally:
        if own_client:
            client.close()


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    try:
        return float(value) if value else None
    except ValueError:
        return None
