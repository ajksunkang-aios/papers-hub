"""Fetch author affiliations from dblp person pages."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from core.author_profiles import normalize_author_key, normalize_author_name
from core.dblp_person_index import DblpPersonIndex
from core.published_abstracts import REQUEST_DELAY_SEC, USER_AGENT

# Re-export shared limits (override legacy module constant).
from core.fetch_limits import DBLP_MAX_TIME_SEC as _DBLP_MAX_TIME_SEC
from core.fetch_limits import DBLP_CONNECT_TIMEOUT_SEC, DBLP_AUTHOR_BUDGET_SEC, TimeBudget

DBLP_MAX_TIME_SEC = _DBLP_MAX_TIME_SEC

DBLP_MIRRORS = ("https://dblp.org",)
DBLP_BASE = DBLP_MIRRORS[0]
DBLP_AUTHOR_SEARCH_PATH = "/search/author/api"

AFFILIATION_RE = re.compile(
    r'itemprop="affiliation"[^>]*>.*?itemprop="name">([^<]+)',
    re.IGNORECASE | re.DOTALL,
)

_DBLP_HOST_PREFIXES = (
    "https://dblp.org",
    "http://dblp.org",
    "https://dblp.dagstuhl.de",
    "http://dblp.dagstuhl.de",
    "https://dblp.uni-trier.de",
    "http://dblp.uni-trier.de",
)


def _rewrite_dblp_host(url: str, base: str) -> str:
    """Rewrite any dblp host to ``base`` so person pages stay on a reachable mirror."""
    text = (url or "").strip()
    if not text:
        return text
    for host in _DBLP_HOST_PREFIXES:
        if text.startswith(host):
            return base + text[len(host) :]
    return text


def _normalize_dblp_url(url: str) -> str:
    return _rewrite_dblp_host(url, DBLP_BASE)


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
        max_lookups: int | None = None,
        person_index: DblpPersonIndex | None = None,
        online_fallback: bool = False,
    ) -> None:
        self.cache = cache
        self.offline = offline
        self.request_delay_sec = request_delay_sec
        self.person_index = person_index
        # Slow HTTP person-page lookup; off by default when xml person index is loaded.
        self.online_fallback = online_fallback
        # Cap new person-page resolutions so CI can finish and persist the cache.
        self.max_online_authors = max_lookups
        self._last_request = 0.0
        self._failures = 0
        self._online_lookups = 0
        self._budget_exhausted = False

    @property
    def online_lookups(self) -> int:
        return self._online_lookups

    @property
    def budget_exhausted(self) -> bool:
        return self._budget_exhausted

    def _network_ok(self) -> bool:
        return self.online_fallback and not self.offline and not self._budget_exhausted

    def _resolve_from_person_index(self, author_name: str, key: str) -> list[str] | None:
        """Lookup offline index; return affiliations, [] on indexed miss, None if not indexed."""
        if self.person_index is None or not self.person_index.loaded:
            return None
        hit = self.person_index.lookup(author_name)
        if hit is None:
            return None
        affs, pid = hit
        if affs:
            self.cache.set(key, affs, pid=pid)
            return affs
        self.cache.set_miss(key)
        return []

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.request_delay_sec:
            time.sleep(self.request_delay_sec - elapsed)
        self._last_request = time.monotonic()

    def _get_text(self, url: str, *, params: dict | None = None) -> str | None:
        if not self._network_ok():
            return None
        # Brief backoff when dblp is flaky so we do not burn the whole run.
        if self._failures >= 8:
            time.sleep(min(30.0, 2.0 * self._failures))
            self._failures = 0
        last_error = False
        for base in DBLP_MIRRORS:
            candidate = _rewrite_dblp_host(url, base)
            if params:
                sep = "&" if "?" in candidate else "?"
                candidate = f"{candidate}{sep}{urlencode(params)}"
            self._throttle()
            try:
                proc = subprocess.run(
                    [
                        "curl",
                        "-4",
                        "-sS",
                        "-L",
                        "--connect-timeout",
                        str(DBLP_CONNECT_TIMEOUT_SEC),
                        "--max-time",
                        str(DBLP_MAX_TIME_SEC),
                        "-A",
                        USER_AGENT,
                        "-H",
                        "Accept: */*",
                        candidate,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=DBLP_MAX_TIME_SEC + DBLP_CONNECT_TIMEOUT_SEC + 3,
                )
            except (subprocess.TimeoutExpired, OSError):
                last_error = True
                continue
            if proc.returncode != 0:
                last_error = True
                continue
            body = proc.stdout or ""
            if not body:
                last_error = True
                continue
            self._failures = 0
            return body
        if last_error:
            self._failures += 1
        return None

    def search_author_pid(self, author_name: str) -> str | None:
        text = self._get_text(
            f"{DBLP_BASE}{DBLP_AUTHOR_SEARCH_PATH}",
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
                url = _rewrite_dblp_host(info.get("url") or "", DBLP_BASE)
                if url:
                    return url
        if len(hits) == 1:
            info = hits[0].get("info") or {}
            url = _rewrite_dblp_host(info.get("url") or "", DBLP_BASE)
            return url or None
        return None

    def fetch_person_affiliations(self, pid_url: str) -> list[str]:
        pid_url = _rewrite_dblp_host(pid_url, DBLP_BASE)
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

        indexed = self._resolve_from_person_index(author_name, key)
        if indexed is not None:
            return indexed

        if not self._network_ok():
            if self.person_index is not None and self.person_index.loaded:
                self.cache.set_miss(key)
            return []
        if self.max_online_authors is not None and self._online_lookups >= self.max_online_authors:
            self._budget_exhausted = True
            return []

        self._online_lookups += 1
        budget = TimeBudget(DBLP_AUTHOR_BUDGET_SEC)
        failures_before = self._failures
        pid = self.search_author_pid(author_name)
        if budget.expired:
            self._failures += 1
            return []
        if not pid:
            if self._failures > failures_before:
                return []
            self.cache.set_miss(key)
            return []

        affs = self.fetch_person_affiliations(pid)
        if budget.expired and not affs:
            self._failures += 1
            return []
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
