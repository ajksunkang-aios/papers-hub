"""Build and finalize per-author affiliation records on papers."""

from __future__ import annotations

import re
from typing import Any

from core.author_country import enrich_authors_structured_local

UNKNOWN_AFFILIATION = "Unknown affiliation"
AUTHOR_NAME_YEAR_RE = re.compile(r"\s+\d{4}$")
AUTHOR_NAME_SUFFIX_RE = re.compile(r"\s+\d+$")


def normalize_author_name(name: str) -> str:
    text = (name or "").strip()
    text = AUTHOR_NAME_YEAR_RE.sub("", text)
    text = AUTHOR_NAME_SUFFIX_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_author_key(name: str) -> str:
    return normalize_author_name(name).lower()


def build_authors_structured_skeleton(authors: list[str] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in authors or []:
        text = (name or "").strip()
        if not text:
            continue
        rows.append({"name": text, "affiliations": []})
    return rows


def upgrade_authors_structured(paper: dict[str, Any]) -> list[dict[str, Any]]:
    rows = paper.get("authors_structured")
    if rows:
        return [dict(row) for row in rows if row.get("name")]
    authors = [a for a in (paper.get("authors") or []) if a]
    first_affs = [a for a in (paper.get("first_author_affiliations") or []) if a]
    out: list[dict[str, Any]] = []
    for idx, name in enumerate(authors):
        out.append(
            {
                "name": name,
                "affiliations": list(first_affs) if idx == 0 and first_affs else [],
            }
        )
    return out


def rows_need_real_affiliations(rows: list[dict[str, Any]] | None) -> bool:
    if not rows:
        return True
    for row in rows:
        affs = [
            a
            for a in (row.get("affiliations") or [])
            if a and a != UNKNOWN_AFFILIATION
        ]
        if not affs:
            return True
    return False


def author_rows_missing_affiliations(rows: list[dict[str, Any]] | None) -> bool:
    """True when any author lacks a real (non-placeholder) affiliation."""
    return rows_need_real_affiliations(rows)


def merge_author_affiliations(
    rows: list[dict[str, Any]],
    aff_by_name: dict[str, list[str]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in rows:
        name = (row.get("name") or "").strip()
        existing = [
            a
            for a in (row.get("affiliations") or [])
            if a and a != UNKNOWN_AFFILIATION
        ]
        if existing:
            merged.append({**row, "name": name, "affiliations": existing})
            continue
        key = normalize_author_key(name)
        fetched = [a for a in aff_by_name.get(key, []) if a]
        merged.append({**row, "name": name, "affiliations": fetched})
    return merged


def ensure_all_authors_have_affiliations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        affs = [a for a in (row.get("affiliations") or []) if a]
        if not affs:
            affs = [UNKNOWN_AFFILIATION]
        out.append({**row, "affiliations": affs})
    return out


def finalize_authors_structured(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    filled = ensure_all_authors_have_affiliations(rows)
    return enrich_authors_structured_local(filled, policy=policy)


def attach_author_fields(paper: dict[str, Any], *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = upgrade_authors_structured(paper)
    if not rows:
        authors = [a for a in (paper.get("authors") or []) if a]
        rows = build_authors_structured_skeleton(authors)
    if policy is not None:
        rows = finalize_authors_structured(rows, policy=policy)
    else:
        rows = ensure_all_authors_have_affiliations(rows)
    paper["authors_structured"] = rows
    paper["first_author_affiliations"] = rows[0].get("affiliations") or [] if rows else []
    return paper


def paper_authors_complete(paper: dict[str, Any], *, first_author_only: bool = False) -> bool:
    rows = paper.get("authors_structured")
    if not rows:
        return False
    expected = len([a for a in (paper.get("authors") or []) if a])
    if expected and len(rows) < expected:
        return False
    if first_author_only:
        first_affs = [
            a
            for a in (rows[0].get("affiliations") or [])
            if a and a != UNKNOWN_AFFILIATION
        ]
        return bool(first_affs)
    return not rows_need_real_affiliations(rows)
