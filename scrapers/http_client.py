"""Client HTTP partagé : délais, User-Agent, récupération robots.txt."""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, delay: float = REQUEST_DELAY_SECONDS):
        self.delay = delay
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            }
        )
        retries = Retry(
            total=2,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._robots: dict[str, Optional[RobotFileParser]] = {}

    def _wait(self, extra_delay: float = 0.0) -> None:
        wait_for = max(self.delay, extra_delay)
        elapsed = time.time() - self._last_request_at
        if elapsed < wait_for:
            time.sleep(wait_for - elapsed)

    def _robots_for(self, url: str) -> Optional[RobotFileParser]:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        robots_url = urljoin(origin, "/robots.txt")
        rp = RobotFileParser()
        try:
            self._wait()
            resp = self.session.get(robots_url, timeout=REQUEST_TIMEOUT)
            self._last_request_at = time.time()
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                self._robots[origin] = rp
            else:
                self._robots[origin] = None
        except Exception as exc:  # noqa: BLE001
            logger.warning("robots.txt indisponible pour %s: %s", origin, exc)
            self._robots[origin] = None
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:  # noqa: BLE001
            return True

    def get(self, url: str, extra_delay: float = 0.0) -> requests.Response:
        if not self.allowed(url):
            raise PermissionError(f"URL interdite par robots.txt: {url}")
        self._wait(extra_delay)
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        self._last_request_at = time.time()
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
        return resp
