"""Resolve author affiliations and countries (OpenAlex as fallback)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.published_abstracts import (
    REQUEST_DELAY_SEC,
    REQUEST_TIMEOUT,
    USER_AGENT,
    extract_doi,
    lookup_cache_keys,
    normalize_title_key,
)


@dataclass
class FirstAuthorCountry:
    name: str
    country_code: str
    country_label: str
    affiliations: list[str]
    source: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "country_code": self.country_code,
            "country_label": self.country_label,
            "affiliations": self.affiliations,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class AuthorProfile:
    name: str
    affiliations: list[str] = field(default_factory=list)
    country_code: str = "XX"
    country_label: str = "Unknown"
    source: str = "unknown"
    confidence: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "affiliations": self.affiliations,
            "country_code": self.country_code,
            "country_label": self.country_label,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuthorProfile:
        code = (raw.get("country_code") or "XX").upper()
        return cls(
            name=(raw.get("name") or "").strip(),
            affiliations=[a for a in (raw.get("affiliations") or []) if a],
            country_code=code,
            country_label=raw.get("country_label") or country_label(code, {}),
            source=raw.get("source") or "unknown",
            confidence=raw.get("confidence") or "unknown",
        )


def load_author_country_policy(hub_dir: Path) -> dict[str, Any]:
    path = hub_dir / "author_country_policy.json"
    if not path.is_file():
        return {
            "country_labels": {"XX": "Unknown"},
            "institution_hints": [],
            "country_keywords": [],
            "region_groups": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def build_institution_matcher(hints: list[list[str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in hints:
        if len(row) != 2:
            continue
        needle, code = row[0].strip().lower(), row[1].strip().upper()
        if needle and code:
            out.append((needle, code))
    out.sort(key=lambda x: len(x[0]), reverse=True)
    return out


def country_label(code: str, labels: dict[str, str]) -> str:
    c = (code or "XX").upper()
    return labels.get(c, c if c != "XX" else "Unknown")


def infer_country_from_text(text: str, matcher: list[tuple[str, str]]) -> str | None:
    hay = (text or "").lower()
    if not hay:
        return None
    for needle, code in matcher:
        token = needle.strip().lower()
        if not token:
            continue
        if " " in token or len(token) > 5:
            if token in hay:
                return code
            continue
        if re.search(rf"\b{re.escape(token)}\b", hay):
            return code
    return None


def build_matchers(policy: dict[str, Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    institution = build_institution_matcher(policy.get("institution_hints", []))
    country = build_institution_matcher(policy.get("country_keywords", []))
    return institution, country


def resolve_author_local(
    name: str,
    affiliations: list[str],
    *,
    policy: dict[str, Any],
) -> AuthorProfile:
    labels = policy.get("country_labels", {})
    institution_matcher, country_matcher = build_matchers(policy)
    affs = [a for a in affiliations if a]
    blob = " ".join(affs)

    code = infer_country_from_text(blob, institution_matcher)
    source = "affiliation-institution"
    confidence = "medium"
    if not code:
        code = infer_country_from_text(blob, country_matcher)
        source = "affiliation-country-text"
        confidence = "low"

    if not code:
        return AuthorProfile(
            name=name,
            affiliations=affs,
            country_code="XX",
            country_label=country_label("XX", labels),
            source="unknown",
            confidence="unknown",
        )

    return AuthorProfile(
        name=name,
        affiliations=affs,
        country_code=code,
        country_label=country_label(code, labels),
        source=source,
        confidence=confidence,
    )


def normalize_authors_input(
    authors: list[str] | None,
    authors_structured: list[dict[str, Any]] | None,
) -> list[AuthorProfile]:
    if authors_structured:
        profiles = [AuthorProfile.from_dict(raw) for raw in authors_structured if raw.get("name")]
        if profiles:
            return profiles
    return [AuthorProfile(name=name) for name in (authors or []) if name]


def merge_openalex_profiles(
    profiles: list[AuthorProfile],
    openalex_rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> list[AuthorProfile]:
    if not openalex_rows:
        return profiles

    labels = policy.get("country_labels", {})
    institution_matcher, country_matcher = build_matchers(policy)
    used = set()

    def norm_name(name: str) -> str:
        return re.sub(r"\s+\d{4}$", "", (name or "").strip().lower())

    merged: list[AuthorProfile] = []
    for idx, profile in enumerate(profiles):
        row = openalex_rows[idx] if idx < len(openalex_rows) else None
        if row is None:
            for j, candidate in enumerate(openalex_rows):
                if j in used:
                    continue
                if norm_name(candidate.get("name", "")) == norm_name(profile.name):
                    row = candidate
                    used.add(j)
                    break

        if row is None:
            merged.append(profile if profile.country_code != "XX" else resolve_author_local(profile.name, profile.affiliations, policy=policy))
            continue

        affs = row.get("affiliations") or profile.affiliations
        code = (row.get("country_code") or profile.country_code or "XX").upper()
        source = row.get("source") or profile.source
        confidence = row.get("confidence") or profile.confidence

        if code == "XX" and affs:
            local = resolve_author_local(profile.name or row.get("name", ""), affs, policy=policy)
            if local.country_code != "XX":
                code = local.country_code
                source = local.source
                confidence = local.confidence

        if code == "XX" and affs:
            code = infer_country_from_text(" ".join(affs), institution_matcher) or infer_country_from_text(
                " ".join(affs), country_matcher
            )
            if code:
                source = "openalex-affiliation-rules"
                confidence = "medium"

        merged.append(
            AuthorProfile(
                name=(row.get("name") or profile.name).strip(),
                affiliations=affs,
                country_code=code if code else "XX",
                country_label=country_label(code if code else "XX", labels),
                source=source if code else "unknown",
                confidence=confidence if code else "unknown",
            )
        )

    return merged


def enrich_authors_structured_local(
    rows: list[dict[str, Any]] | None,
    *,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    profiles = normalize_authors_input(None, rows)
    if not profiles and rows:
        profiles = [AuthorProfile(name=(row.get("name") or ""), affiliations=row.get("affiliations") or []) for row in rows]
    out: list[dict[str, Any]] = []
    for profile in profiles:
        if profile.country_code != "XX" and profile.affiliations:
            out.append(profile.to_dict())
            continue
        resolved = resolve_author_local(profile.name, profile.affiliations or [], policy=policy)
        out.append(resolved.to_dict())
    return out


def parse_openalex_authorship_rows(data: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    labels = policy.get("country_labels", {})
    institution_matcher, country_matcher = build_matchers(policy)
    rows: list[dict[str, Any]] = []

    for authorship in data.get("authorships") or []:
        author = authorship.get("author") or {}
        name = (author.get("display_name") or "").strip()
        affiliations: list[str] = []
        countries: list[str] = []
        for inst in authorship.get("institutions") or []:
            display = (inst.get("display_name") or "").strip()
            if display:
                affiliations.append(display)
            cc = (inst.get("country_code") or "").strip().upper()
            if cc:
                countries.append(cc)
        for raw in authorship.get("raw_affiliation_strings") or []:
            text = (raw or "").strip()
            if text and text not in affiliations:
                affiliations.append(text)

        code = countries[0] if countries else None
        source = "openalex"
        confidence = "high"
        if not code and affiliations:
            code = infer_country_from_text(" ".join(affiliations), institution_matcher)
            if code:
                source = "openalex-affiliation-rules"
                confidence = "medium"
        if not code and affiliations:
            code = infer_country_from_text(" ".join(affiliations), country_matcher)
            if code:
                source = "openalex-country-text"
                confidence = "low"

        rows.append(
            AuthorProfile(
                name=name,
                affiliations=affiliations,
                country_code=code or "XX",
                country_label=country_label(code or "XX", labels),
                source=source if code else "openalex-unknown",
                confidence=confidence if code else "unknown",
            ).to_dict()
        )
    return rows


def first_author_from_structured(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


class AuthorCountryCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {"version": 2, "entries": {}}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("entries"), dict):
                    self._data = loaded
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._data["entries"].get(key)
        if not entry or entry.get("miss"):
            return None
        return entry

    def is_miss(self, key: str) -> bool:
        entry = self._data["entries"].get(key)
        return bool(entry and entry.get("miss"))

    def set_miss(self, keys: list[str]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        for key in keys:
            if key:
                self._data["entries"][key] = {"miss": True, "fetched_at": ts}

    def set(self, key: str, payload: dict[str, Any]) -> None:
        self._data["entries"][key] = {
            **payload,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class AuthorCountryResolver:
    def __init__(
        self,
        *,
        cache: AuthorCountryCache,
        policy: dict[str, Any],
        offline: bool = False,
    ) -> None:
        self.cache = cache
        self.policy = policy
        self.labels: dict[str, str] = policy.get("country_labels", {})
        self.offline = offline
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        retry = Retry(total=2, backoff_factor=0.4, status_forcelist=(429, 500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self._last_request = 0.0
        self._failures = 0

    def _network_ok(self) -> bool:
        return not self.offline and self._failures < 5

    def _throttle(self) -> None:
        import time

        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_DELAY_SEC:
            time.sleep(REQUEST_DELAY_SEC - elapsed)
        self._last_request = time.monotonic()

    def _get_json(self, url: str, *, params: dict | None = None) -> dict | None:
        if not self._network_ok():
            return None
        self._throttle()
        try:
            r = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            self._failures = 0
            return r.json()
        except (requests.Timeout, requests.ConnectionError, requests.RequestException, json.JSONDecodeError):
            self._failures += 1
            return None

    def fetch_openalex_work(self, doi: str) -> dict | None:
        url = f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='')}"
        return self._get_json(url)

    def fetch_openalex_by_arxiv(self, arxiv_id: str) -> dict | None:
        base_id = re.sub(r"v\d+$", "", arxiv_id.strip())
        if not base_id:
            return None
        url = f"https://api.openalex.org/works/https://arxiv.org/abs/{quote(base_id, safe='')}"
        return self._get_json(url)

    def fetch_openalex_by_title(self, title: str) -> dict | None:
        if not title:
            return None
        data = self._get_json(
            "https://api.openalex.org/works",
            params={"filter": f"title.search:{title}", "per-page": 5},
        )
        if not data:
            return None
        want = normalize_title_key(title)
        for work in data.get("results") or []:
            if normalize_title_key(work.get("title") or "") == want:
                return work
        return None

    def resolve_paper_authors(
        self,
        *,
        title: str,
        authors: list[str] | None = None,
        authors_structured: list[dict[str, Any]] | None = None,
        ee_links: list[str] | None = None,
        dblp_key: str | None = None,
        arxiv_id: str | None = None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        cache_keys = lookup_cache_keys(title=title, ee_links=ee_links, dblp_key=dblp_key)
        if arxiv_id:
            base_id = re.sub(r"v\d+$", "", arxiv_id)
            cache_keys.insert(0, f"arxiv:{base_id}")

        if not force:
            for key in cache_keys:
                hit = self.cache.get(key)
                if hit and hit.get("authors_structured"):
                    return hit["authors_structured"]

        profiles = normalize_authors_input(authors, authors_structured)
        resolved = [resolve_author_local(p.name, p.affiliations, policy=self.policy) for p in profiles]

        needs_fallback = any(p.country_code == "XX" for p in resolved) or any(
            not p.affiliations for p in resolved
        )

        if needs_fallback and self._network_ok():
            doi = extract_doi(ee_links)
            work = self.fetch_openalex_work(doi) if doi else None
            if work is None and arxiv_id:
                work = self.fetch_openalex_by_arxiv(arxiv_id)
            if work is None and title:
                work = self.fetch_openalex_by_title(title)
            if work:
                openalex_rows = parse_openalex_authorship_rows(work, policy=self.policy)
                resolved = merge_openalex_profiles(
                    resolved,
                    openalex_rows,
                    policy=self.policy,
                )

        rows = [p.to_dict() for p in resolved]
        if rows and cache_keys:
            payload = {
                "authors_structured": rows,
                "first_author": first_author_from_structured(rows),
            }
            for key in cache_keys:
                self.cache.set(key, payload)
        elif cache_keys and all(p.country_code == "XX" for p in resolved):
            self.cache.set_miss(cache_keys)

        return rows

    def resolve(
        self,
        *,
        title: str,
        authors: list[str] | None = None,
        authors_structured: list[dict[str, Any]] | None = None,
        ee_links: list[str] | None = None,
        dblp_key: str | None = None,
        arxiv_id: str | None = None,
        affiliations: list[str] | None = None,
        force: bool = False,
    ):
        """Backward-compatible first-author view."""
        if authors_structured is None and affiliations:
            names = [a for a in (authors or []) if a]
            authors_structured = [
                {"name": names[0] if names else "", "affiliations": affiliations}
            ] if affiliations else None

        rows = self.resolve_paper_authors(
            title=title,
            authors=authors,
            authors_structured=authors_structured,
            ee_links=ee_links,
            dblp_key=dblp_key,
            arxiv_id=arxiv_id,
            force=force,
        )
        first = rows[0] if rows else {
            "name": (authors or [""])[0],
            "affiliations": affiliations or [],
            "country_code": "XX",
            "country_label": country_label("XX", self.labels),
            "source": "unknown",
            "confidence": "unknown",
        }
        return FirstAuthorCountry(
            name=first.get("name") or "",
            country_code=(first.get("country_code") or "XX").upper(),
            country_label=first.get("country_label") or country_label(first.get("country_code", "XX"), self.labels),
            affiliations=first.get("affiliations") or [],
            source=first.get("source") or "unknown",
            confidence=first.get("confidence") or "unknown",
        )


def build_arxiv_authors_index(arxiv_json_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Map normalized title -> authors_structured from crawled arXiv feed."""
    if not arxiv_json_path.is_file():
        return {}
    try:
        data = json.loads(arxiv_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for paper in data.get("papers", []):
        rows = paper.get("authors_structured")
        if not rows:
            continue
        title = paper.get("title", "")
        key = normalize_title_key(title)
        if key:
            out[key] = rows
    return out


def upgrade_authors_structured(paper: dict[str, Any]) -> list[dict[str, Any]]:
    from core.author_profiles import upgrade_authors_structured as _upgrade

    return _upgrade(paper)


def authors_need_enrichment(rows: list[dict[str, Any]] | None) -> bool:
    if not rows:
        return True
    return any((row.get("country_code") or "XX").upper() == "XX" for row in rows)


def parse_openalex_authorship(work: dict[str, Any], *, policy: dict[str, Any] | None = None) -> tuple[str, str, list[str]]:
    """Backward-compatible first-author OpenAlex parse."""
    policy = policy or {"country_labels": {}}
    rows = parse_openalex_authorship_rows(work, policy=policy)
    first = rows[0] if rows else {}
    return (
        first.get("name") or "",
        (first.get("country_code") or "XX").upper(),
        first.get("affiliations") or [],
    )
