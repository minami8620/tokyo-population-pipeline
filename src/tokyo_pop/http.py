"""A polite HTTP session: identifies itself, retries transient errors, rate-limits."""

from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "tokyo-population-pipeline/0.1 "
    "(+https://github.com/minami8620/tokyo-population-pipeline)"
)
TIMEOUT_SECONDS = 30
MIN_INTERVAL_SECONDS = 1.0


class PoliteSession(requests.Session):
    """``requests.Session`` with retries and a minimum interval between requests."""

    def __init__(self, min_interval: float = MIN_INTERVAL_SECONDS) -> None:
        super().__init__()
        self.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.mount("https://", HTTPAdapter(max_retries=retry))
        self._min_interval = min_interval
        self._last_request = 0.0

    def request(self, method, url, **kwargs):  # type: ignore[override]
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        kwargs.setdefault("timeout", TIMEOUT_SECONDS)
        try:
            return super().request(method, url, **kwargs)
        finally:
            self._last_request = time.monotonic()
