"""Small stdlib HTTP client with per-host rate limiting, retries and a disk cache.

Public data providers publish usage rules we must respect:
  * GDELT DOC API: at most one request every 5 seconds.
  * SEC EDGAR: at most 10 requests/second and a descriptive User-Agent
    that includes contact details (set ``RISK_COLLECTOR_USER_AGENT``).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .models import utcnow

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "risk-collector/0.1 (+https://github.com/Frame-42/UBS-AI-Challenge; company risk research)"

# Minimum seconds between requests to the same host.
HOST_MIN_INTERVAL: Dict[str, float] = {
    "api.gdeltproject.org": 6.0,
    "data.sec.gov": 0.15,
    "efts.sec.gov": 0.15,
    "www.sec.gov": 0.15,
    "www.courtlistener.com": 1.0,
    "www.justice.gov": 0.5,
    "en.wikipedia.org": 1.0,
}


@dataclass
class Response:
    url: str
    status: int
    body: bytes
    retrieved_at: str
    from_cache: bool = False

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding, errors="replace")

    def json(self):
        # GDELT occasionally emits control characters inside strings.
        return json.loads(self.text(), strict=False)


class HttpError(RuntimeError):
    pass


class HttpClient:
    def __init__(
        self,
        cache_dir: Optional[str] = ".cache/risk_collector",
        user_agent: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        use_cache: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.user_agent = user_agent or os.environ.get("RISK_COLLECTOR_USER_AGENT") or DEFAULT_USER_AGENT
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_cache = use_cache and self.cache_dir is not None
        self._last_call: Dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ cache
    def _cache_paths(self, url: str):
        h = hashlib.sha256(url.encode()).hexdigest()[:32]
        assert self.cache_dir is not None
        return self.cache_dir / f"{h}.bin", self.cache_dir / f"{h}.json"

    def _cache_get(self, url: str, ttl: float) -> Optional[Response]:
        if not self.use_cache or ttl <= 0:
            return None
        body_p, meta_p = self._cache_paths(url)
        if not (body_p.exists() and meta_p.exists()):
            return None
        meta = json.loads(meta_p.read_text())
        if time.time() - meta["stored"] > ttl:
            return None
        return Response(url, meta["status"], gzip.decompress(body_p.read_bytes()), meta["retrieved_at"], True)

    def _cache_put(self, resp: Response) -> None:
        if not self.use_cache:
            return
        assert self.cache_dir is not None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        body_p, meta_p = self._cache_paths(resp.url)
        body_p.write_bytes(gzip.compress(resp.body))
        meta_p.write_text(json.dumps({"url": resp.url, "status": resp.status,
                                      "retrieved_at": resp.retrieved_at, "stored": time.time()}))

    # ------------------------------------------------------------- throttling
    def _throttle(self, host: str) -> None:
        interval = HOST_MIN_INTERVAL.get(host, 0.0)
        with self._lock:
            wait = self._last_call.get(host, 0.0) + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call[host] = time.monotonic()

    # -------------------------------------------------------------------- api
    def get(self, url: str, params: Optional[dict] = None, cache_ttl: float = 3600,
            headers: Optional[dict] = None) -> Response:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
        cached = self._cache_get(url, cache_ttl)
        if cached:
            log.debug("cache hit %s", url)
            return cached

        host = urllib.parse.urlparse(url).netloc
        hdrs = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"}
        hdrs.update(headers or {})
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                    resp = Response(url, r.status, body, utcnow())
                # GDELT signals rate limiting with a 200 + plain-text notice.
                if host == "api.gdeltproject.org" and body.startswith(b"Please limit requests"):
                    raise HttpError("GDELT rate limit notice")
                self._cache_put(resp)
                return resp
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code not in (429, 500, 502, 503, 504):
                    raise HttpError(f"HTTP {e.code} for {url}") from e
            except (urllib.error.URLError, TimeoutError, HttpError, ConnectionError) as e:
                last_err = e
            backoff = max(HOST_MIN_INTERVAL.get(host, 1.0), 1.0) * (2 ** attempt)
            log.warning("request failed (%s), retry %d in %.0fs: %s", last_err, attempt + 1, backoff, url)
            time.sleep(backoff)
        raise HttpError(f"giving up on {url}: {last_err}")
