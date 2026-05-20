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
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

from core.hub_config import Hub, add_hub_argument, load_hub
from core.keywords import score_keywords

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
USER_AGENT = "top-conference-arxiv/1.0 (research; +https://github.com/example/top-conference)"

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


def fetch_feed(session: requests.Session, category: str, max_results: int) -> str:
    params = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    last_err: Exception | None = None
    for attempt in range(5):
        resp = session.get(ARXIV_API, params=params, timeout=90)
        if resp.status_code == 429:
            wait = 12 * (attempt + 1)
            print(f"  arXiv rate limit; waiting {wait}s...")
            time.sleep(wait)
            last_err = requests.HTTPError(f"429 for {category}")
            continue
        try:
            resp.raise_for_status()
            return resp.text
        except requests.HTTPError as e:
            last_err = e
            time.sleep(6 * (attempt + 1))
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


def has_llm_systems_signal(title: str, abstract: str) -> bool:
    text = _text_blob(title, abstract)
    return any(k in text for k in active_hub().llm_systems_keywords)


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


def days_since_year_start(year: int) -> int:
    now = datetime.now(timezone.utc)
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    if year > now.year:
        return 0
    if year < now.year:
        return 400
    return max(1, (now - start).days + 1)


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
    args = parser.parse_args()

    hub = load_hub(args.hub)
    set_active_hub(hub)
    root = hub.root
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

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    filter_years: set[int] | None = None
    if args.years:
        filter_years = set(parse_years_arg(args.years))
    elif args.year is not None:
        filter_years = {args.year}

    days = args.days
    if filter_years is not None:
        min_year = min(filter_years)
        days = days_since_year_start(min_year)
        boost = policy.get("years_fetch_boost", {})
        args.os_max = max(args.os_max, int(boost.get("os_max", 200)))
        args.cl_max = max(args.cl_max, int(boost.get("cl_max", 500)))
        label = ",".join(str(y) for y in sorted(filter_years))
        print(f"Year filter {label} (scanning ~{days} days, os_max={args.os_max}, cl_max={args.cl_max})")

    def passes_date_filter(iso_ts: str) -> bool:
        if filter_years is not None:
            return within_years(iso_ts, filter_years)
        return within_days(iso_ts, days)

    all_papers: list[ArxivPaper] = []
    feed_defs = policy.get("feeds", [{"id": "cs.OS"}, {"id": "cs.CL", "filter": "cl_systems"}])
    max_by_feed = {
        "cs.OS": args.os_max,
        "cs.CL": args.cl_max,
    }

    for i, feed in enumerate(feed_defs):
        feed_id = feed["id"]
        feed_max = int(max_by_feed.get(feed_id, feed.get("default_max", 40)))
        if i > 0:
            time.sleep(3)
        print(f"Fetching {feed_id}...")
        xml = fetch_feed(session, feed_id, feed_max)
        entries = parse_entries(xml, source_feed=feed_id)
        kept = 0
        for p in entries:
            if not passes_date_filter(p.published):
                continue
            if feed.get("filter") == "cl_systems":
                filtered = filter_cl_paper(p, args.cl_min_score)
                if not filtered:
                    continue
                all_papers.append(filtered)
            else:
                score, tags = score_relevance(p.title, p.abstract)
                p.relevance_score = max(score, 1)
                p.relevance_tags = tags[:6] if tags else [feed_id.lower()]
                all_papers.append(p)
            kept += 1
        print(f"  kept {kept} {feed_id} papers")

    all_papers = dedupe(all_papers)
    all_papers.sort(key=lambda p: p.published, reverse=True)

    fetched_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "fetched_at": fetched_at,
        "hub_id": hub.id,
        "sources": [
            {"id": f["id"], "url": f"https://arxiv.org/list/{f['id']}/recent"} for f in feed_defs
        ],
        "filter_note": policy.get("filter_note", ""),
        "count": len(all_papers),
        "papers": [asdict(p) for p in all_papers],
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(all_papers)} papers to {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
