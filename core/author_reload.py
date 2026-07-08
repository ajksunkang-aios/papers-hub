"""Reload author enrichments from disk caches; avoid re-fetching dblp.

Persistence layers (written during online enrich, restored by GitHub Actions cache):
  - data/dblp-affiliation-cache-{hub}.json  — author name → affiliations / miss
  - data/author-country-cache-{hub}.json    — paper key → authors_structured
  - data/author-paper-reload-{hub}.json    — paper key → authors_structured (reload index)

On each run: hydrate conference JSON from these files, then only HTTP-fetch
authors that are still missing from the dblp affiliation cache.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.author_country import AuthorCountryCache
from core.author_profiles import (
    UNKNOWN_AFFILIATION,
    merge_author_affiliations,
    normalize_author_key,
    paper_authors_complete,
    rows_need_real_affiliations,
    upgrade_authors_structured,
)
from core.dblp_affiliations import DblpAffiliationCache
from core.published_abstracts import lookup_cache_keys


def paper_lookup_keys(paper: dict[str, Any]) -> list[str]:
    keys = lookup_cache_keys(
        title=paper.get("title", ""),
        ee_links=paper.get("ee_links"),
        dblp_key=paper.get("dblp_key"),
    )
    arxiv_id = paper.get("arxiv_id")
    if arxiv_id:
        base_id = re.sub(r"v\d+$", "", str(arxiv_id).strip())
        if base_id:
            keys.insert(0, f"arxiv:{base_id}")
    return [k for k in keys if k]


def rows_have_real_affiliations(
    rows: list[dict[str, Any]] | None,
    *,
    first_author_only: bool = False,
) -> bool:
    if not rows:
        return False
    target = rows[:1] if first_author_only else rows
    return not rows_need_real_affiliations(target)


def load_cached_authors_structured(
    paper: dict[str, Any],
    country_cache: AuthorCountryCache,
    *,
    first_author_only: bool = False,
) -> list[dict[str, Any]] | None:
    """Return cached rows only when they contain real affiliations (not XX placeholders)."""
    for key in paper_lookup_keys(paper):
        hit = country_cache.get(key)
        rows = hit.get("authors_structured") if hit else None
        if rows and rows_have_real_affiliations(rows, first_author_only=first_author_only):
            return list(rows)
    return None


def target_author_names(
    paper: dict[str, Any],
    *,
    first_author_only: bool = False,
) -> list[str]:
    rows = upgrade_authors_structured(paper)
    if not rows:
        names = [n for n in (paper.get("authors") or []) if n]
        return names[:1] if first_author_only and names else names
    if first_author_only:
        name = rows[0].get("name") or ""
        return [name] if name else []
    return [row.get("name", "") for row in rows if row.get("name")]


def dblp_authors_resolved(
    names: list[str],
    dblp_cache: DblpAffiliationCache | None,
) -> bool:
    """True when every name has a cache hit or explicit miss (no HTTP needed)."""
    if dblp_cache is None or not names:
        return False
    for name in names:
        key = normalize_author_key(name)
        if not key:
            continue
        if dblp_cache.get(key) is None and not dblp_cache.is_miss(key):
            return False
    return True


def paper_needs_affiliation_enrich(
    paper: dict[str, Any],
    *,
    force: bool = False,
    first_author_only: bool = False,
) -> bool:
    """True when the paper still lacks real (non-placeholder) affiliations."""
    if force:
        return True
    return not paper_authors_complete(paper, first_author_only=first_author_only)


def paper_needs_online_fetch(
    paper: dict[str, Any],
    *,
    dblp_cache: DblpAffiliationCache | None,
    force: bool = False,
    first_author_only: bool = False,
) -> bool:
    """Whether this paper still needs a dblp person-page HTTP fetch."""
    if force:
        return True
    if paper_authors_complete(paper, first_author_only=first_author_only):
        return False
    names = target_author_names(paper, first_author_only=first_author_only)
    if not names:
        return False
    return not dblp_authors_resolved(names, dblp_cache)


def apply_dblp_cache_affiliations(
    paper: dict[str, Any],
    dblp_cache: DblpAffiliationCache,
    *,
    first_author_only: bool = False,
) -> list[dict[str, Any]]:
    rows = upgrade_authors_structured(paper)
    if not rows:
        rows = [{"name": n, "affiliations": []} for n in (paper.get("authors") or []) if n]
    names = target_author_names(paper, first_author_only=first_author_only)
    aff_by_name: dict[str, list[str]] = {}
    for name in names:
        key = normalize_author_key(name)
        if not key:
            continue
        cached = dblp_cache.get(key)
        if cached is not None:
            aff_by_name[key] = cached
        elif dblp_cache.is_miss(key):
            aff_by_name[key] = []
    if not aff_by_name:
        return rows
    if first_author_only and rows:
        return merge_author_affiliations(rows[:1], aff_by_name) + rows[1:]
    return merge_author_affiliations(rows, aff_by_name)


class AuthorPaperReloadIndex:
    """Compact paper-key → authors_structured index for fast CI reload."""

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

    def get(
        self,
        paper: dict[str, Any],
        *,
        first_author_only: bool = False,
    ) -> list[dict[str, Any]] | None:
        for key in paper_lookup_keys(paper):
            entry = self._data["entries"].get(key)
            rows = entry.get("authors_structured") if entry else None
            if rows and rows_have_real_affiliations(rows, first_author_only=first_author_only):
                return list(rows)
        return None

    def set_paper(self, paper: dict[str, Any], *, first_author_only: bool = False) -> None:
        rows = paper.get("authors_structured")
        if not rows_have_real_affiliations(rows, first_author_only=first_author_only):
            return
        payload = {
            "authors_structured": rows,
            "first_author_affiliations": paper.get("first_author_affiliations") or [],
        }
        for key in paper_lookup_keys(paper):
            self._data["entries"][key] = payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
