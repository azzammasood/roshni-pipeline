"""Polite HTTP client: fixed User-Agent, robots.txt, rate limit, host denylist."""

import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

# Hosts we must never touch (robots disallow or personal data). Checked by suffix.
DENIED_HOST_SUFFIXES = ("lesco.gov.pk", "pitc.com.pk")


class FetchRefused(Exception):
    """Raised when policy forbids a request (denylist or robots.txt)."""


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_denied_host(url: str) -> bool:
    host = _host(url)
    return any(host == s or host.endswith("." + s) for s in DENIED_HOST_SUFFIXES)


class PoliteClient:
    """Wraps httpx.Client. One request per `min_interval` seconds across all hosts."""

    def __init__(
        self,
        user_agent: str,
        min_interval: float = 1.0,
        timeout: float = 90,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        retries: int = 2,
    ) -> None:
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.retries = retries
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._last is not None:
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def _raw_get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        attempt = 0
        while True:
            self._throttle()
            try:
                resp = self._client.get(url, headers=headers)
            except httpx.TransportError:
                if attempt >= self.retries:
                    raise
            else:
                if resp.status_code < 500 or attempt >= self.retries:
                    return resp
            attempt += 1
            self._sleep(2**attempt)

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            resp = self._raw_get(origin + "/robots.txt")
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            elif resp.status_code in (401, 403):
                rp.disallow_all = True
            else:  # 404 and similar: no rules
                rp.allow_all = True
            self._robots[origin] = rp
        return self._robots[origin]

    def check_allowed(self, url: str) -> None:
        if is_denied_host(url):
            raise FetchRefused(f"host is on the denylist: {url}")
        if not self._robots_for(url).can_fetch(self.user_agent, url):
            raise FetchRefused(f"robots.txt disallows: {url}")

    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        self.check_allowed(url)
        return self._raw_get(url, headers=headers)
