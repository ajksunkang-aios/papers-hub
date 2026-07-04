"""Fetch author affiliations from dblp person pages."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.author_profiles import normalize_author_key, normalize_author_name
from core.published_abstracts import REQUEST_DELAY_SEC, REQUEST_TIMEOUT, USER_AGENT

DBLP_AUTHOR_SEARCH = "https://dblp.org/search/author/api"
AFFILIATION_RE = re.compile(
    r'itemprop="affiliation"[^>]*>.*?itemprop="name">([^<]+)',
    re.IGNORECASE | re.DOTALL,
)


class DblpAffiliationCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {"version": 1, "entries": {}}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("entries"), dict):
                    self._data = loaded
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, author_key: str) -> list[str] | None:
        entry = self._data["entries"].get(author_key)
        if not entry:
            return None
        if entry.get("miss"):
            return []
        affs = entry.get("affiliations")
        if isinstance(affs, list):
            return [a for a in affs if a]
        return None

    def is_miss(self, author_key: str) -> bool:
        entry = self._data["entries"].get(author_key)
        return bool(entry and entry.get("miss"))

    def set(self, author_key: str, affiliations: list[str], *, pid: str | None = None) -> None:
        self._data["entries"][author_key] = {
            "affiliations": affiliations,
            "pid": pid,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def set_miss(self, author_key: str) -> None:
        self._data["entries"][author_key] = {
            "miss": True,
            "affiliations": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def parse_person_affiliations(html: str) -> list[str]:
    start = html.find("Person information")
    chunk = html[start : start + 12000] if start >= 0 else html[:12000]
    affs: list[str] = []
    seen: set[str] = set()
    for match in AFFILIATION_RE.findall(chunk):
        text = unescape(match.strip())
        if text and text not in seen:
            seen.add(text)
            affs.append(text)
    return affs


class DblpAffiliationFetcher:
    def __init__(
        self,
        *,
        cache: DblpAffiliationCache,
        offline: bool = False,
        request_delay_sec: float = REQUEST_DELAY_SEC,
    ) -> None:
        self.cache = cache
        self.offline = offline
        self.request_delay_sec = request_delay_sec
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        retry = Retry(total=2, backoff_factor=0.4, status_forcelist=(429, 500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self._last_request = 0.0
        self._failures = 0

    def _network_ok(self) -> bool:
        return not self.offline and self._failures < 8

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.request_delay_sec:
            time.sleep(self.request_delay_sec - elapsed)
        self._last_request = time.monotonic()

    def _get_text(self, url: str, *, params: dict | None = None) -> str | None:
        if not self._network_ok():
            return None
        self._throttle()
        try:
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                self._failures = max(0, self._failures - 1)
                return None
            resp.raise_for_status()
            self._failures = 0
            return resp.text
        except (requests.Timeout, requests.ConnectionError, requests.RequestException):
            self._failures += 1
            return None

    def search_author_pid(self, author_name: str) -> str | None:
        text = self._get_text(
            DBLP_AUTHOR_SEARCH,
            params={"q": author_name, "format": "json", "h": 8},
        )
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        hits = payload.get("result", {}).get("hits", {}).get("hit") or []
        if isinstance(hits, dict):
            hits = [hits]
        want = normalize_author_name(author_name).lower()
        for hit in hits:
            info = hit.get("info") or {}
            candidate = (info.get("author") or "").strip()
            if normalize_author_name(candidate).lower() == want:
                url = (info.get("url") or "").strip()
                if url:
                    return url
        if len(hits) == 1:
            info = hits[0].get("info") or {}
            url = (info.get("url") or "").strip()
            return url or None
        return None

    def fetch_person_affiliations(self, pid_url: str) -> list[str]:
        url = pid_url if pid_url.endswith(".html") else f"{pid_url.rstrip('/')}.html"
        html = self._get_text(url)
        if not html:
            return []
        return parse_person_affiliations(html)

    def resolve_author(self, author_name: str, *, force: bool = False) -> list[str]:
        key = normalize_author_key(author_name)
        if not force:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
            if self.cache.is_miss(key):
                return []

        if not self._network_ok():
            return []

        pid = self.search_author_pid(author_name)
        if not pid:
            self.cache.set_miss(key)
            return []

        affs = self.fetch_person_affiliations(pid)
        pid_slug = pid.rstrip("/").split("/")[-1]
        self.cache.set(key, affs, pid=pid_slug)
        if not affs:
            self.cache.set_miss(key)
        return affs

    def resolve_authors(self, author_names: list[str], *, force: bool = False) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for name in author_names:
            key = normalize_author_key(name)
            if not key:
                continue
            out[key] = self.resolve_author(name, force=force)
        return out
