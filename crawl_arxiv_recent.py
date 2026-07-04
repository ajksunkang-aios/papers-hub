#!/usr/bin/env python3
"""
Fetch recent OS & systems-relevant LLM papers from arXiv.

Sources (aligned with arxiv.org/list/.../recent):
  - cs.OS  (Operating Systems)
  - cs.CL  (Computation and Language), filtered for systems/LLM relevance

Output: website/data/arxiv-recent.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

from core.author_country import enrich_authors_structured_local, load_author_country_policy
from core.author_profiles import ensure_all_authors_have_affiliations
from core.hub_config import Hub, add_hub_argument, load_hub
from core.incremental import (
    file_fingerprint,
    is_fresh,
    load_json,
    policy_fingerprint,
    save_json,
    utc_now_iso,
)
from core.keywords import score_keywords

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
USER_AGENT = "papers-hub/1.0 (research; incremental arXiv crawl)"
REQUEST_MIN_INTERVAL = 3.5
INTER_FEED_SLEEP_SEC = 5.0
_last_request_at = 0.0

# cs.OS feed: broad systems keyword scoring.
SYS_LLM_KEYWORDS: list[tuple[str, int]] = [
    ("linux kernel", 12),
    ("os kernel", 12),
    ("kernel module", 8),
    ("operating system", 4),
    ("file system", 4),
    ("system software", 4),
    ("runtime system", 3),
    ("storage system", 3),
    ("memory management", 3),
    ("inference serving", 3),
    ("model serving", 3),
    ("kv cache", 3),
    ("training system", 3),
    ("large language model", 2),
    ("llm", 1),
    ("distributed system", 2),
    ("scheduler", 2),
    ("virtualization", 2),
    ("ebpf", 3),
    ("rdma", 2),
    ("nvme", 2),
    ("kernel", 1),
    ("vllm", 2),
    ("deepspeed", 2),
]

STRONG_KEYWORDS = {
    "linux kernel",
    "os kernel",
    "operating system",
    "file system",
    "system software",
    "kernel module",
    "storage system",
    "runtime system",
}

# cs.CL: OS / system-software first; generic LLM terms are weak.
CL_SYS_KEYWORDS: list[tuple[str, int]] = [
    ("linux kernel", 20),
    ("os kernel", 20),
    ("kernel module", 12),
    ("operating system", 8),
    ("file system", 8),
    ("filesystem", 8),
    ("system software", 8),
    ("syscall", 7),
    ("device driver", 7),
    ("ebpf", 7),
    ("memory management", 6),
    ("virtual memory", 6),
    ("page cache", 6),
    ("runtime system", 6),
    ("storage system", 6),
    ("virtualization", 5),
    ("hypervisor", 5),
    ("container runtime", 5),
    ("distributed system", 4),
    ("rdma", 4),
    ("nvme", 4),
    ("scheduler", 4),
    ("inference serving", 4),
    ("model serving", 4),
    ("kv cache", 3),
    ("training system", 3),
    ("kernel", 1),
    ("large language model", 1),
    ("llm", 1),
]

CL_STRONG_KEYWORDS = {
    "linux kernel",
    "os kernel",
    "kernel module",
    "operating system",
    "file system",
    "system software",
}

# Required for cs.CL admission (strict system-software; not datacenter/ML hints alone).
OS_GATE_KEYWORDS = [
    "operating system",
    "linux kernel",
    "os kernel",
    "kernel module",
    "file system",
    "filesystem",
    "memory management",
    "virtual memory",
    "page cache",
    "system software",
    "runtime system",
    "storage system",
    "device driver",
    "syscall",
    "ebpf",
    "virtualization",
    "hypervisor",
    "container runtime",
]

LLM_SYSTEMS_KEYWORDS = [
    "inference serving",
    "model serving",
    "llm serving",
    "llm inference",
    "kv cache",
    "speculative decoding",
    "training system",
    "vllm",
    "deepspeed",
    "megatron",
    "disaggregated",
]

# Primary categories that are almost never OS; require cs.OS cross-list or OS terms.
NOISE_PRIMARY_CATEGORIES = frozenset(
    {"cs.AI", "cs.CV", "cs.HC", "cs.GR", "cs.CY", "cs.IR", "cs.CL"}
)

_ACTIVE_HUB: Hub | None = None


def set_active_hub(hub: Hub) -> None:
    global _ACTIVE_HUB
    _ACTIVE_HUB = hub


def active_hub() -> Hub:
    if _ACTIVE_HUB is None:
        return load_hub("os-kernel")
    return _ACTIVE_HUB


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    authors_structured: list[dict] = field(default_factory=list)
    first_author_affiliations: list[str] = field(default_factory=list)
    abstract: str = ""
    published: str = ""
    updated: str = ""
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""
    source_feed: str = ""
    abs_url: str = ""
    pdf_url: str = ""
    relevance_score: int = 0
    relevance_tags: list[str] = field(default_factory=list)


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return re.sub(r"\s+", " ", el.text).strip()


def arxiv_cache_dir(hub: Hub) -> Path:
    return hub.root / "data" / "arxiv-cache" / hub.id


def arxiv_manifest_path(hub: Hub) -> Path:
    return arxiv_cache_dir(hub) / "manifest.json"


def throttle_before_request() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < REQUEST_MIN_INTERVAL:
        time.sleep(REQUEST_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def submitted_date_clause(
    *,
    years: set[int] | None,
    since: datetime | None,
    until: datetime | None = None,
) -> str:
    """arXiv requires submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM] in GMT."""
    until_utc = _as_utc(until or datetime.now(timezone.utc))
    if since is not None:
        start_utc = _as_utc(since)
    elif years:
        start_utc = datetime(min(years), 1, 1, 0, 0, tzinfo=timezone.utc)
    else:
        start_utc = until_utc - timedelta(days=14)
    if start_utc > until_utc:
        start_utc = until_utc - timedelta(days=1)
    start = start_utc.strftime("%Y%m%d%H%M")
    end = until_utc.strftime("%Y%m%d%H%M")
    return f"submittedDate:[{start} TO {end}]"


def feed_search_query(category: str, date_clause: str) -> str:
    return f"cat:{category} AND {date_clause}"


def category_only_query(category: str) -> str:
    return f"cat:{category}"


def feed_query_candidates(category: str, date_clause: str) -> list[str]:
    """Prefer date-bounded query; fall back to category-only (filter dates locally).

    cs.CL + submittedDate often returns HTTP 409 from arXiv; use cat-only for cs.CL.
    """
    cat_only = category_only_query(category)
    bounded = feed_search_query(category, date_clause)
    if category == "cs.CL":
        return [cat_only]
    return [bounded, cat_only]


def crawl_run_fingerprint(
    hub: Hub,
    *,
    filter_years: set[int] | None,
    os_max: int,
    cl_max: int,
    cl_min_score: int,
    feed_defs: list[dict],
) -> str:
    return policy_fingerprint(
        {
            "hub": hub.id,
            "years": sorted(filter_years) if filter_years else None,
            "os_max": os_max,
            "cl_max": cl_max,
            "cl_min_score": cl_min_score,
            "feeds": feed_defs,
            "filter_note": hub.arxiv_policy.get("filter_note", ""),
        }
    )


def newest_published(papers: list[dict]) -> datetime | None:
    best: datetime | None = None
    for p in papers:
        raw = p.get("published", "")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if best is None or dt > best:
            best = dt
    return best


def dict_to_paper(d: dict) -> ArxivPaper:
    return ArxivPaper(
        arxiv_id=d.get("arxiv_id", ""),
        title=d.get("title", ""),
        authors=list(d.get("authors") or []),
        authors_structured=list(d.get("authors_structured") or []),
        first_author_affiliations=list(d.get("first_author_affiliations") or []),
        abstract=d.get("abstract", ""),
        published=d.get("published", ""),
        updated=d.get("updated", ""),
        categories=list(d.get("categories") or []),
        primary_category=d.get("primary_category", ""),
        source_feed=d.get("source_feed", ""),
        abs_url=d.get("abs_url", ""),
        pdf_url=d.get("pdf_url", ""),
        relevance_score=int(d.get("relevance_score") or 0),
        relevance_tags=list(d.get("relevance_tags") or []),
    )


def merge_paper_lists(
    existing: list[dict],
    fetched: list[ArxivPaper],
    *,
    years: set[int] | None,
) -> list[ArxivPaper]:
    by_id: dict[str, ArxivPaper] = {}
    for raw in existing:
        if years is not None and not within_years(raw.get("published", ""), years):
            continue
        base = re.sub(r"v\d+$", "", raw.get("arxiv_id", ""))
        if base:
            by_id[base] = dict_to_paper(raw)
    for paper in fetched:
        base = re.sub(r"v\d+$", "", paper.arxiv_id)
        if base:
            by_id[base] = paper
    merged = list(by_id.values())
    merged.sort(key=lambda p: p.published, reverse=True)
    return merged


def _arxiv_error_snippet(resp: requests.Response) -> str:
    text = (resp.text or "").strip().replace("\n", " ")
    return text[:240] if text else "(empty body)"


def fetch_feed(
    session: requests.Session,
    category: str,
    max_results: int,
    *,
    search_queries: list[str],
    cache_path: Path | None = None,
) -> tuple[str, str]:
    """Try queries in order; return (xml_text, query_used)."""
    last_err: Exception | None = None
    effective_max = max_results

    for qi, search_query in enumerate(search_queries):
        if qi > 0:
            print(f"  retry {category} with simpler query: {search_query}")
            time.sleep(INTER_FEED_SLEEP_SEC)

        for attempt in range(6):
            throttle_before_request()
            params = {
                "search_query": search_query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": effective_max,
            }
            try:
                resp = session.get(ARXIV_API, params=params, timeout=90)
            except requests.RequestException as e:
                last_err = e
                wait = min(120, 6 * (2**attempt)) + random.uniform(0, 3)
                print(f"  network error for {category}; waiting {wait:.0f}s...")
                time.sleep(wait)
                continue

            if resp.status_code in (400, 409):
                print(
                    f"  arXiv rejected query ({resp.status_code}) for {category}: "
                    f"{_arxiv_error_snippet(resp)}"
                )
                last_err = requests.HTTPError(f"{resp.status_code} for {category}")
                break

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after) + random.uniform(0, 2)
                else:
                    wait = min(180, 12 * (2**attempt)) + random.uniform(0, 5)
                print(f"  arXiv rate limit ({category}); waiting {wait:.0f}s...")
                time.sleep(wait)
                if effective_max > 40:
                    effective_max = max(40, effective_max // 2)
                    print(f"  reducing max_results to {effective_max}")
                last_err = requests.HTTPError(f"429 for {category}")
                continue

            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                last_err = e
                time.sleep(min(90, 6 * (attempt + 1)) + random.uniform(0, 2))
                continue

            text = resp.text
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
            return text, search_query

    if cache_path and cache_path.is_file():
        print(f"  using cached XML for {category} ({cache_path.name})")
        return cache_path.read_text(encoding="utf-8"), "cache"

    raise last_err or RuntimeError(f"failed to fetch {category}")


def parse_entries(xml_text: str, *, source_feed: str) -> list[ArxivPaper]:
    root = ET.fromstring(xml_text)
    papers: list[ArxivPaper] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = _text(entry.find("atom:id", ATOM_NS))
        arxiv_id = raw_id.rsplit("/", 1)[-1]
        title = _text(entry.find("atom:title", ATOM_NS))
        summary = _text(entry.find("atom:summary", ATOM_NS))
        published = _text(entry.find("atom:published", ATOM_NS))
        updated = _text(entry.find("atom:updated", ATOM_NS))
        authors = [_text(a.find("atom:name", ATOM_NS)) for a in entry.findall("atom:author", ATOM_NS)]
        authors = [a for a in authors if a]
        author_nodes = entry.findall("atom:author", ATOM_NS)
        authors_structured: list[dict] = []
        first_author_affiliations: list[str] = []
        for author_node in author_nodes:
            name = _text(author_node.find("atom:name", ATOM_NS))
            if not name:
                continue
            affs = [
                _text(a) for a in author_node.findall("arxiv:affiliation", ATOM_NS) if _text(a)
            ]
            authors_structured.append({"name": name, "affiliations": affs})
        if authors_structured:
            first_author_affiliations = authors_structured[0].get("affiliations") or []
        categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        primary_cat = primary.attrib.get("term", "") if primary is not None else ""

        abs_url = ""
        pdf_url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "")
            rel = link.attrib.get("rel", "")
            typ = link.attrib.get("type", "")
            if rel == "alternate" and typ == "text/html":
                abs_url = href
            if rel == "related" and "pdf" in typ:
                pdf_url = href
        if not abs_url and arxiv_id:
            abs_url = f"https://arxiv.org/abs/{arxiv_id}"

        papers.append(
            ArxivPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                authors_structured=authors_structured,
                first_author_affiliations=first_author_affiliations,
                abstract=summary,
                published=published,
                updated=updated,
                categories=categories,
                primary_category=primary_cat or (categories[0] if categories else ""),
                source_feed=source_feed,
                abs_url=abs_url,
                pdf_url=pdf_url,
            )
        )
    return papers


def score_relevance(title: str, abstract: str) -> tuple[int, list[str]]:
    hub = active_hub()
    text = f"{title} {abstract}"
    return score_keywords(text, hub.sys_keywords, hub.sys_strong)


def score_relevance_cl(title: str, abstract: str) -> tuple[int, list[str]]:
    hub = active_hub()
    text = f"{title} {abstract}"
    score, tags = score_keywords(text, hub.cl_keywords, hub.cl_strong)
    blob = text.lower()
    if "linux kernel" in blob:
        score += 10
    if "os kernel" in blob:
        score += 10
    return score, tags


def _text_blob(title: str, abstract: str) -> str:
    return f"{title} {abstract}".lower()


def has_os_signal(title: str, abstract: str) -> bool:
    text = _text_blob(title, abstract)
    return any(k in text for k in active_hub().os_gate_keywords)


def has_linux_or_os_kernel(title: str, abstract: str) -> bool:
    text = _text_blob(title, abstract)
    return "linux kernel" in text or "os kernel" in text


def has_cs_os_category(categories: list[str]) -> bool:
    return "cs.OS" in categories


def passes_systems_gate(
    *,
    title: str,
    abstract: str,
    categories: list[str],
    source_feed: str,
) -> bool:
    """True if paper is OS / system-software relevant (not generic NLP/ML)."""
    if source_feed != "cs.CL":
        return True
    # cs.CL: require OS cross-list or system-software terms (not LLM-serving keywords alone).
    if has_cs_os_category(categories):
        return True
    if has_linux_or_os_kernel(title, abstract):
        return True
    if has_os_signal(title, abstract):
        return True
    return False


def passes_top_arxiv_gate(paper: dict) -> bool:
    """Stricter gate for monthly top picks."""
    feed = paper.get("source_feed", "")
    if feed not in ("cs.OS", "cs.CL"):
        return True

    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    categories = paper.get("categories") or []
    primary = paper.get("primary_category", "")

    if not passes_systems_gate(
        title=title,
        abstract=abstract,
        categories=categories,
        source_feed=feed,
    ):
        return False

    if feed == "cs.OS":
        return True

    # cs.CL: always require OS / system-software (gate above); noisy primaries need cs.OS cross-list or OS terms.
    if primary in active_hub().noise_primary_categories:
        return has_cs_os_category(categories) or has_os_signal(title, abstract)
    return True


def within_days(iso_ts: str, days: int) -> bool:
    if not iso_ts:
        return True
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff


def within_year(iso_ts: str, year: int) -> bool:
    if not iso_ts:
        return False
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.year == year


def within_years(iso_ts: str, years: set[int]) -> bool:
    if not iso_ts:
        return False
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.year in years


def parse_years_arg(raw: str) -> list[int]:
    return sorted({int(part.strip()) for part in raw.split(",") if part.strip()})


def filter_cl_paper(paper: ArxivPaper, min_score: int) -> ArxivPaper | None:
    if not passes_systems_gate(
        title=paper.title,
        abstract=paper.abstract,
        categories=paper.categories,
        source_feed=paper.source_feed,
    ):
        return None
    score, tags = score_relevance_cl(paper.title, paper.abstract)
    if score < min_score:
        return None
    paper.relevance_score = score
    paper.relevance_tags = tags
    return paper


def dedupe(papers: Iterable[ArxivPaper]) -> list[ArxivPaper]:
    seen: set[str] = set()
    out: list[ArxivPaper] = []
    for p in papers:
        base_id = re.sub(r"v\d+$", "", p.arxiv_id)
        if base_id in seen:
            continue
        seen.add(base_id)
        out.append(p)
    return out


def apply_local_author_countries(papers: list[ArxivPaper], policy: dict) -> None:
    for paper in papers:
        rows = paper.authors_structured or [{"name": n, "affiliations": []} for n in paper.authors]
        enriched = enrich_authors_structured_local(rows, policy=policy)
        enriched = ensure_all_authors_have_affiliations(enriched)
        paper.authors_structured = enriched
        if enriched:
            paper.first_author_affiliations = enriched[0].get("affiliations") or []


def refilter_json(path: Path, min_cl_score: int) -> tuple[int, int]:
    """Re-apply cs.CL systems gate to an existing arxiv-recent.json (no network)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data.get("papers", []))
    kept: list[dict] = []
    for p in data.get("papers", []):
        feed = p.get("source_feed")
        if feed == "cs.OS":
            kept.append(p)
            continue
        if feed != "cs.CL":
            continue
        title = p.get("title", "")
        abstract = p.get("abstract", "")
        categories = p.get("categories") or []
        if not passes_systems_gate(
            title=title,
            abstract=abstract,
            categories=categories,
            source_feed="cs.CL",
        ):
            continue
        score, tags = score_relevance_cl(title, abstract)
        if score < min_cl_score:
            continue
        p["relevance_score"] = score
        p["relevance_tags"] = tags
        kept.append(p)
    unique = dedupe_dicts(kept)
    unique.sort(key=lambda x: x.get("published", ""), reverse=True)
    data["papers"] = unique
    data["count"] = len(unique)
    data["filter_note"] = (
        "cs.CL: OS cross-list or system-software terms required (linux/os kernel weighted "
        "highest); generic LLM/NLP or serving-only papers excluded."
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return before, len(unique)


def dedupe_dicts(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for p in papers:
        base = re.sub(r"v\d+$", "", p.get("arxiv_id", ""))
        if base in seen:
            continue
        seen.add(base)
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl recent arXiv OS/LLM papers.")
    add_hub_argument(parser)
    parser.add_argument(
        "--refilter-json",
        action="store_true",
        help="re-apply cs.CL gate to existing output JSON (no API fetch)",
    )
    parser.add_argument("--os-max", type=int, default=40, help="max cs.OS results")
    parser.add_argument("--cl-max", type=int, default=120, help="max cs.CL results to scan")
    parser.add_argument("--cl-min-score", type=int, default=6, help="min relevance score for cs.CL")
    parser.add_argument("--days", type=int, default=14, help="only keep papers from last N days")
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="keep papers published in this calendar year (overrides --days window)",
    )
    parser.add_argument(
        "--years",
        default=None,
        help="comma-separated years to keep (e.g. 2025,2026; overrides --days window)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="output JSON path (default: <hub site>/data/arxiv-recent.json)",
    )
    parser.add_argument(
        "--if-stale-hours",
        type=float,
        default=None,
        help="skip API fetch when manifest + output are newer than N hours",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="always fetch from arXiv (ignore staleness)",
    )
    parser.add_argument(
        "--no-incremental",
        action="store_true",
        help="replace output instead of merging with existing arxiv-recent.json",
    )
    args = parser.parse_args()

    hub = load_hub(args.hub)
    set_active_hub(hub)
    root = hub.root
    author_policy = load_author_country_policy(hub.hub_dir)
    out_json = Path(args.output_json) if args.output_json else hub.site_json_path("arxiv-recent.json")
    policy = hub.arxiv_policy
    if args.cl_min_score == 6:
        args.cl_min_score = int(policy.get("cl_min_score_default", args.cl_min_score))
    if args.days == 14:
        args.days = int(policy.get("days_default", args.days))

    if args.refilter_json:
        before, after = refilter_json(out_json, args.cl_min_score)
        print(f"Refiltered {out_json}: {before} -> {after} papers")
        return 0

    filter_years: set[int] | None = None
    if args.years:
        filter_years = set(parse_years_arg(args.years))
    elif args.year is not None:
        filter_years = {args.year}

    days = args.days
    feed_defs = policy.get("feeds", [{"id": "cs.OS"}, {"id": "cs.CL", "filter": "cl_systems"}])
    boost = policy.get("years_fetch_boost", {})
    if filter_years is not None:
        args.os_max = min(args.os_max, int(boost.get("os_max", 120)))
        args.cl_max = min(args.cl_max, int(boost.get("cl_max", 180)))
        label = ",".join(str(y) for y in sorted(filter_years))
        print(f"Year filter {label} (date-bounded API, os_max={args.os_max}, cl_max={args.cl_max})")
    else:
        print(f"Rolling window: last {days} days (os_max={args.os_max}, cl_max={args.cl_max})")

    run_fp = crawl_run_fingerprint(
        hub,
        filter_years=filter_years,
        os_max=args.os_max,
        cl_max=args.cl_max,
        cl_min_score=args.cl_min_score,
        feed_defs=feed_defs,
    )
    manifest_path = arxiv_manifest_path(hub)
    manifest = load_json(manifest_path)

    feeds = manifest.get("feeds") or {}
    last_run_had_feed_errors = any(
        isinstance(meta, dict) and meta.get("error") for meta in feeds.values()
    )
    if (
        not args.force
        and args.if_stale_hours is not None
        and out_json.is_file()
        and is_fresh(
            manifest,
            fingerprint=run_fp,
            max_age_hours=args.if_stale_hours,
            extra_keys={"years": sorted(filter_years) if filter_years else None},
        )
        and not last_run_had_feed_errors
    ):
        print(
            f"arXiv data fresh ({manifest.get('last_success_at', 'manifest')}); "
            f"skip fetch ({out_json})"
        )
        return 0
    if last_run_had_feed_errors and not args.force:
        print("Last crawl had feed errors; retrying fetch...")

    existing_rows: list[dict] = []
    incremental = not args.no_incremental and out_json.is_file()
    if incremental:
        try:
            existing_rows = json.loads(out_json.read_text(encoding="utf-8")).get("papers", [])
        except (json.JSONDecodeError, OSError):
            existing_rows = []

    since_dt: datetime | None = None
    if incremental and existing_rows:
        newest = newest_published(existing_rows)
        if newest is not None:
            since_dt = newest - timedelta(days=2)
            print(f"Incremental since {since_dt.date().isoformat()} (overlap 2d)")

    date_clause = submitted_date_clause(years=filter_years, since=since_dt)
    print(f"API date clause: {date_clause}")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    cache_dir = arxiv_cache_dir(hub)

    def passes_date_filter(iso_ts: str) -> bool:
        if filter_years is not None:
            return within_years(iso_ts, filter_years)
        return within_days(iso_ts, args.days)

    fetched_batch: list[ArxivPaper] = []
    max_by_feed = {"cs.OS": args.os_max, "cs.CL": args.cl_max}
    feed_manifest: dict[str, dict] = {}
    feed_errors: list[str] = []

    for fi, feed in enumerate(feed_defs):
        if fi > 0:
            time.sleep(INTER_FEED_SLEEP_SEC)
        feed_id = feed["id"]
        feed_max = int(max_by_feed.get(feed_id, feed.get("default_max", 40)))
        queries = feed_query_candidates(feed_id, date_clause)
        qhash = policy_fingerprint({"q": queries[0], "max": feed_max})[:12]
        cache_path = cache_dir / f"{feed_id}-{qhash}.xml"
        print(f"Fetching {feed_id} (max_results={feed_max})...")
        print(f"  query: {queries[0]}")
        try:
            xml, query_used = fetch_feed(
                session,
                feed_id,
                feed_max,
                search_queries=queries,
                cache_path=cache_path,
            )
        except Exception as err:
            print(f"  WARNING: skipped {feed_id} ({err})")
            feed_manifest[feed_id] = {
                "fetched_at": utc_now_iso(),
                "error": str(err),
                "search_query": queries[0],
                "kept": 0,
            }
            continue

        entries = parse_entries(xml, source_feed=feed_id)
        kept = 0
        for p in entries:
            if not passes_date_filter(p.published):
                continue
            if feed.get("filter") == "cl_systems":
                filtered = filter_cl_paper(p, args.cl_min_score)
                if not filtered:
                    continue
                fetched_batch.append(filtered)
            else:
                score, tags = score_relevance(p.title, p.abstract)
                p.relevance_score = max(score, 1)
                p.relevance_tags = tags[:6] if tags else [feed_id.lower()]
                fetched_batch.append(p)
            kept += 1
        print(f"  kept {kept} {feed_id} papers this run")
        feed_manifest[feed_id] = {
            "fetched_at": utc_now_iso(),
            "search_query": query_used,
            "max_results": feed_max,
            "cache_file": str(cache_path.relative_to(hub.root)),
            "kept": kept,
        }

    feed_errors = [fid for fid, m in feed_manifest.items() if m.get("error")]
    if feed_errors:
        print(f"Feeds with errors: {', '.join(feed_errors)} (other feeds still saved)")

    apply_local_author_countries(fetched_batch, author_policy)
    if incremental:
        all_papers = merge_paper_lists(existing_rows, fetched_batch, years=filter_years)
    else:
        all_papers = dedupe(fetched_batch)
        all_papers.sort(key=lambda p: p.published, reverse=True)
    apply_local_author_countries(all_papers, author_policy)

    fetched_at = utc_now_iso()
    payload = {
        "fetched_at": fetched_at,
        "hub_id": hub.id,
        "incremental": incremental,
        "years": sorted(filter_years) if filter_years else None,
        "sources": [
            {"id": f["id"], "url": f"https://arxiv.org/list/{f['id']}/recent"} for f in feed_defs
        ],
        "filter_note": policy.get("filter_note", ""),
        "count": len(all_papers),
        "papers": [asdict(p) for p in all_papers],
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_body: dict = {
        "hub_id": hub.id,
        "source": "arxiv",
        "fingerprint": run_fp,
        "years": sorted(filter_years) if filter_years else None,
        "last_attempt_at": fetched_at,
        "output": str(out_json.relative_to(hub.root)),
        "output_count": len(all_papers),
        "incremental": incremental,
        "feeds": feed_manifest,
    }
    if not feed_errors:
        manifest_body["last_success_at"] = fetched_at
    elif manifest.get("last_success_at"):
        manifest_body["last_success_at"] = manifest["last_success_at"]
    save_json(manifest_path, manifest_body)

    mode = "merged" if incremental else "full"
    print(f"Wrote {len(all_papers)} papers to {out_json} ({mode}, +{len(fetched_batch)} this run)")
    if feed_errors and not fetched_batch and not existing_rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
