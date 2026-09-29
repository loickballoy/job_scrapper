"""Client HTTP minimal : retries avec backoff, respect de Retry-After, une session par thread."""
from __future__ import annotations

import threading
import time
from typing import Any, Optional, Tuple

import requests


class HttpClient:
    def __init__(self, user_agent: str, timeout: float = 20.0, retries: int = 3, backoff: float = 1.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._local = threading.local()

    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": self.user_agent, "Accept": "application/json"})
            self._local.session = s
        return s

    def get_json(self, url: str, params: Optional[dict] = None) -> Tuple[int, Any]:
        """Retourne (status, json). status == 0 : échec réseau après tous les essais.

        404 est renvoyé tel quel (slug inexistant : ce n'est pas une erreur transitoire).
        """
        last_status = 0
        for attempt in range(self.retries + 1):
            try:
                r = self._session().get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                last_status = 0
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
                continue

            if r.status_code == 200:
                try:
                    return 200, r.json()
                except ValueError:
                    return 200, None
            if r.status_code in (429, 500, 502, 503, 504):
                last_status = r.status_code
                retry_after = r.headers.get("Retry-After", "")
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = self.backoff * (2 ** attempt)
                if attempt < self.retries:
                    time.sleep(min(wait, 30.0))
                continue
            return r.status_code, None
        return last_status, None