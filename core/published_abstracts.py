"""Fetch and cache abstracts for peer-reviewed (dblp) conference papers."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
JATS_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

USER_AGENT = "os-kernel-papers-hub/1.0 (research; abstract-enrichment)"
# (connect_sec, read_sec)  short connect avoids hangs on blocked routes / proxies
REQUEST_TIMEOUT = (4, 10)
MIN_ABSTRACT_LEN = 40
REQUEST_DELAY_SEC = 0.12
CIRCUIT_BREAKER_FAILURES = 5


def normalize_title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def extract_doi(ee_links: list[str] | None) -> str | None:
    for url in ee_links or []:
        m = DOI_RE.search(url)
        if m:
            return m.group(1).lower()
    return None


def strip_markup(text: str) -> str:
    if not text:
        return ""
    text = JATS_TAG_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def openalex_inverted_to_text(inv: dict[str, list[int]] | None) -> str:
    if not inv:
        return ""
    max_pos = max(max(positions) for positions in inv.values())
    words = [""] * (max_pos + 1)
    for word, positions in inv.items():
        for pos in positions:
            words[pos] = word
    return " ".join(w for w in words if w).strip()


class AbstractCache:
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

    def get(self, key: str) -> str | None:
        entry = self._data["entries"].get(key)
        if not entry or entry.get("miss"):
            return None
        abstract = (entry.get("abstract") or "").strip()
        return abstract if len(abstract) >= MIN_ABSTRACT_LEN else None

    def is_miss(self, key: str) -> bool:
        entry = self._data["entries"].get(key)
        return bool(entry and entry.get("miss"))

    def set_miss(self, keys: list[str]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        for key in keys:
            if not key:
                continue
            self._data["entries"][key] = {
                "abstract": "",
                "miss": True,
                "fetched_at": ts,
            }

    def set(self, key: str, abstract: str, source: str, *, doi: str | None = None) -> None:
        abstract = abstract.strip()
        if len(abstract) < MIN_ABSTRACT_LEN:
            return
        self._data["entries"][key] = {
            "abstract": abstract,
            "source": source,
            "doi": doi,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def lookup_cache_keys(
    *,
    title: str,
    ee_links: list[str] | None,
    dblp_key: str | None,
) -> list[str]:
    keys: list[str] = []
    doi = extract_doi(ee_links)
    if doi:
        keys.append(f"doi:{doi}")
    if dblp_key:
        keys.append(f"dblp:{dblp_key}")
    title_key = normalize_title_key(title)
    if title_key:
        keys.append(f"title:{title_key}")
    return keys


def build_arxiv_title_index(arxiv_json_path: Path) -> dict[str, str]:
    """Map normalized title -> abstract from crawled arXiv recent feed."""
    if not arxiv_json_path.is_file():
        return {}
    try:
        data = json.loads(arxiv_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, str] = {}
    for paper in data.get("papers", []):
        title = paper.get("title", "")
        abstract = (paper.get("abstract") or "").strip()
        if not title or len(abstract) < MIN_ABSTRACT_LEN:
            continue
        key = normalize_title_key(title)
        if key:
            out[key] = abstract
    return out


class AbstractFetcher:
    def __init__(
        self,
        *,
        cache: AbstractCache,
        arxiv_by_title: dict[str, str] | None = None,
        allow_arxiv_api: bool = False,
        offline: bool = False,
    ) -> None:
        self.cache = cache
        self.arxiv_by_title = arxiv_by_title or {}
        self.allow_arxiv_api = allow_arxiv_api and not offline
        self.offline = offline
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        no_retry = Retry(total=0, connect=0, read=0, redirect=0)
        adapter = HTTPAdapter(max_retries=no_retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._last_request = 0.0
        self._consecutive_failures = 0
        self._network_disabled = offline

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_DELAY_SEC:
            time.sleep(REQUEST_DELAY_SEC - elapsed)
        self._last_request = time.monotonic()

    def _note_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= CIRCUIT_BREAKER_FAILURES:
            self._network_disabled = True

    def _note_success(self) -> None:
        self._consecutive_failures = 0

    def _network_ok(self) -> bool:
        return not self.offline and not self._network_disabled

    def _get_json(self, url: str, *, params: dict | None = None) -> dict | None:
        if not self._network_ok():
            return None
        self._throttle()
        try:
            r = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                self._note_success()
                return None
            r.raise_for_status()
            self._note_success()
            return r.json()
        except (requests.Timeout, requests.ConnectionError):
            self._note_failure()
            return None
        except (requests.RequestException, json.JSONDecodeError):
            self._note_failure()
            return None

    def fetch_openalex(self, doi: str) -> str:
        url = f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='')}"
        data = self._get_json(url)
        if not data:
            return ""
        inv = data.get("abstract_inverted_index")
        if inv:
            text = openalex_inverted_to_text(inv)
            if len(text) >= MIN_ABSTRACT_LEN:
                return text
        return strip_markup(data.get("abstract") or "")

    def fetch_crossref(self, doi: str) -> str:
        url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
        data = self._get_json(url)
        if not data:
            return ""
        msg = data.get("message") or {}
        abstract = strip_markup(msg.get("abstract") or "")
        return abstract if len(abstract) >= MIN_ABSTRACT_LEN else ""

    def fetch_semantic_scholar(self, doi: str) -> str:
        paper_id = f"DOI:{doi}"
        url = f"https://api.semanticscholar.org/graph/v1/paper/{quote(paper_id, safe='')}"
        data = self._get_json(url, params={"fields": "abstract"})
        if not data:
            return ""
        abstract = (data.get("abstract") or "").strip()
        return abstract if len(abstract) >= MIN_ABSTRACT_LEN else ""

    def fetch_arxiv_api(self, title: str) -> str:
        if not self._network_ok():
            return ""
        self._throttle()
        query = f'ti:"{title}"'
        try:
            r = self.session.get(
                "https://export.arxiv.org/api/query",
                params={"search_query": query, "max_results": 5},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            r.raise_for_status()
            self._note_success()
        except (requests.Timeout, requests.ConnectionError):
            self._note_failure()
            return ""
        except requests.RequestException:
            self._note_failure()
            return ""
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return ""
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        want = normalize_title_key(title)
        for entry in root.findall("atom:entry", ns):
            t_el = entry.find("atom:title", ns)
            if t_el is None or normalize_title_key(t_el.text or "") != want:
                continue
            summary = entry.find("atom:summary", ns)
            if summary is not None:
                abstract = WS_RE.sub(" ", (summary.text or "")).strip()
                if len(abstract) >= MIN_ABSTRACT_LEN:
                    return abstract
        return ""

    def resolve(
        self,
        *,
        title: str,
        ee_links: list[str] | None,
        dblp_key: str | None,
        force: bool = False,
    ) -> tuple[str, str]:
        """
        Return (abstract, source). source is empty if not found.
        Lookup order: disk cache -> local arXiv index -> OpenAlex -> Semantic Scholar
        -> Crossref -> arXiv API title search.
        """
        cache_keys = lookup_cache_keys(
            title=title, ee_links=ee_links, dblp_key=dblp_key
        )
        title_key = normalize_title_key(title)
        doi = extract_doi(ee_links)

        if not force:
            for key in cache_keys:
                hit = self.cache.get(key)
                if hit:
                    return hit, "cache"
            if cache_keys and all(self.cache.is_miss(key) for key in cache_keys):
                return "", "cache-miss"

        if title_key and title_key in self.arxiv_by_title:
            abstract = self.arxiv_by_title[title_key]
            self._store(cache_keys, abstract, "arxiv-local", doi=doi)
            return abstract, "arxiv-local"

        if doi and self._network_ok():
            for source, fn in (
                ("openalex", self.fetch_openalex),
                ("crossref", self.fetch_crossref),
                ("semantic-scholar", self.fetch_semantic_scholar),
            ):
                abstract = fn(doi)
                if abstract:
                    self._store(cache_keys, abstract, source, doi=doi)
                    return abstract, source

        if title and self.allow_arxiv_api:
            abstract = self.fetch_arxiv_api(title)
            if abstract:
                self._store(cache_keys, abstract, "arxiv-api", doi=doi)
                return abstract, "arxiv-api"

        if cache_keys:
            self.cache.set_miss(cache_keys)
        return "", ""

    def _store(self, keys: list[str], abstract: str, source: str, *, doi: str | None) -> None:
        for key in keys:
            self.cache.set(key, abstract, source, doi=doi)
