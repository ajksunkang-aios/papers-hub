#!/usr/bin/env python3
"""
Build categorized top picks for two homepage sections:

  top-monthly.json    — arXiv preprints only
  top-published.json  — peer-reviewed conference proceedings only
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.hub_config import Hub, add_hub_argument, load_hub
from core.picks_scoring import AreaPickScoring
from crawl_arxiv_recent import passes_top_arxiv_gate

ROOT = Path(__file__).resolve().parent
WEB_DATA = ROOT / "website" / "data"

# Default hub config (overridden by --hub via configure_hub()).
CATEGORIES: list[dict] = [
    {
        "id": "llm-serving",
        "label": "LLM serving",
        "keywords": [
            ("inference serving", 12),
            ("model serving", 12),
            ("llm serving", 12),
            ("speculative decoding", 10),
            ("kv cache", 10),
            ("disaggregated", 8),
            ("vllm", 8),
            ("deepspeed", 6),
            ("megatron", 5),
            ("llm inference", 8),
            ("serving system", 6),
            ("throughput", 3),
            ("latency", 3),
        ],
    },
    {
        "id": "on-device-ai",
        "label": "On-device AI",
        "keywords": [
            ("on-device", 14),
            ("on device", 12),
            ("edge deployment", 10),
            ("mobile llm", 12),
            ("embedded llm", 12),
            ("edge ai", 10),
            ("on-device llm", 14),
            ("resource-constrained", 8),
            ("tinyml", 8),
            ("npu", 6),
            ("neural processing unit", 8),
            ("federated learning", 4),
        ],
    },
    {
        "id": "kernel-agentic",
        "label": "Kernel Agentic Engineering",
        "keywords": [
            ("kernel agent", 14),
            ("os agent", 12),
            ("agentic", 8),
            ("computer-use agent", 12),
            ("agent system", 6),
            ("llm agent", 8),
            ("operating system agent", 12),
            ("system agent", 6),
            ("autonomous agent", 6),
            ("tool use", 4),
            ("code agent", 6),
        ],
    },
    {
        "id": "system-security",
        "label": "System Security",
        "keywords": [
            ("secure container", 12),
            ("compartmentalization", 12),
            ("sandbox", 10),
            ("isolation", 8),
            ("trusted execution", 10),
            ("tee", 8),
            ("confidential computing", 10),
            ("side-channel", 8),
            ("vulnerability", 6),
            ("exploit", 6),
            ("memory safety", 8),
            ("control-flow integrity", 10),
            ("security", 4),
            ("malware", 6),
            ("intrusion", 5),
        ],
    },
    {
        "id": "os-kernel-arch",
        "label": "OS Kernel Architecture",
        "keywords": [
            ("linux kernel", 16),
            ("os kernel", 16),
            ("split-kernel", 16),
            ("split kernel", 16),
            ("kernel module", 12),
            ("microkernel", 12),
            ("monolithic kernel", 12),
            ("kernel architecture", 14),
            ("operating system", 8),
            ("syscall", 8),
            ("device driver", 8),
            ("hypervisor", 6),
        ],
    },
    {
        "id": "memory-resource",
        "label": "Memory and Resource Management",
        "keywords": [
            ("memory management", 14),
            ("virtual memory", 12),
            ("page cache", 12),
            ("memory allocator", 12),
            ("resource management", 12),
            ("cgroup", 10),
            ("memory tiering", 10),
            ("numa", 8),
            ("huge pages", 8),
            ("garbage collection", 6),
            ("malloc", 6),
            ("scheduling", 5),
            ("cpu scheduling", 8),
        ],
    },
    {
        "id": "fs-storage",
        "label": "File System and Storage",
        "keywords": [
            ("file system", 16),
            ("filesystem", 16),
            ("distributed file", 14),
            ("storage system", 12),
            ("nvme", 10),
            ("ssd", 8),
            ("object storage", 10),
            ("block storage", 10),
            ("journaling", 8),
            ("nfs", 8),
            ("cifs", 6),
            ("data path", 5),
        ],
    },
    {
        "id": "ebpf",
        "label": "eBPF and Programmable Kernel",
        "keywords": [
            ("ebpf", 16),
            ("bpf", 10),
            ("xdp", 12),
            ("programmable", 8),
            ("kernel extension", 10),
            ("verified program", 8),
            ("tracing", 6),
            ("kprobe", 10),
            ("uprobe", 10),
            ("cilium", 8),
        ],
    },
    {
        "id": "fault-tolerance",
        "label": "Fault Tolerance",
        "keywords": [
            ("fault tolerance", 14),
            ("fault-tolerant", 14),
            ("high availability", 10),
            ("replication", 8),
            ("consensus", 8),
            ("crash recovery", 10),
            ("atomic execution protection", 14),
            ("atomic execution", 12),
            ("distributed shared memory", 10),
            ("checkpoint", 8),
            ("failover", 10),
            ("byzantine", 6),
        ],
    },
]

MIN_CATEGORY_SCORE = 4
PER_CATEGORY_LIMIT = 5
DEFAULT_YEARS = [2023, 2024, 2025, 2026]
DEFAULT_ARXIV_YEARS = [2025, 2026]
CONFERENCE_SCORE_BOOST = 12
MIN_CONFERENCE_PREVIEW = 2
RECENCY_BOOST_PER_YEAR = 2
RECENCY_BASE_YEAR = 2023
_ACTIVE_WEB_DATA = WEB_DATA

# Fallback scoring context when no abstract was enriched for a proceedings paper.
VENUE_SCORE_HINTS: dict[str, str] = {
    "SOSP": "operating systems os kernel distributed systems storage",
    "OSDI": "operating systems os kernel systems software",
    "NSDI": "networked systems distributed systems operating systems",
    "ASPLOS": "computer architecture operating systems compiler systems",
    "EuroSys": "computer systems operating systems distributed systems",
    "ISCA": "computer architecture systems memory",
    "FAST": "file system storage systems operating systems",
    "USENIX Security": "system security operating systems isolation",
    "USENIX ATC": "operating systems systems software virtualization",
    "ICSE": "software engineering systems tools",
}


def configure_hub(hub: Hub) -> None:
    global CATEGORIES, MIN_CATEGORY_SCORE, PER_CATEGORY_LIMIT, DEFAULT_YEARS, DEFAULT_ARXIV_YEARS
    global CONFERENCE_SCORE_BOOST, MIN_CONFERENCE_PREVIEW, RECENCY_BOOST_PER_YEAR, RECENCY_BASE_YEAR
    global _ACTIVE_WEB_DATA
    CATEGORIES = hub.category_rows
    MIN_CATEGORY_SCORE = int(hub.categories.get("min_category_score", MIN_CATEGORY_SCORE))
    PER_CATEGORY_LIMIT = int(hub.categories.get("per_category_limit", PER_CATEGORY_LIMIT))
    DEFAULT_YEARS = [int(y) for y in hub.categories.get("default_years", DEFAULT_YEARS)]
    arxiv_years = hub.arxiv_pick_years or hub.categories.get("arxiv_pick_years")
    DEFAULT_ARXIV_YEARS = [int(y) for y in (arxiv_years or DEFAULT_ARXIV_YEARS)]
    ranking = hub.categories.get("ranking", {})
    CONFERENCE_SCORE_BOOST = int(ranking.get("conference_score_boost", CONFERENCE_SCORE_BOOST))
    MIN_CONFERENCE_PREVIEW = int(ranking.get("min_conference_preview", MIN_CONFERENCE_PREVIEW))
    RECENCY_BOOST_PER_YEAR = int(ranking.get("recency_boost_per_year", RECENCY_BOOST_PER_YEAR))
    RECENCY_BASE_YEAR = int(ranking.get("recency_base_year", RECENCY_BASE_YEAR))
    _ACTIVE_WEB_DATA = hub.web_data


@dataclass
class PaperCandidate:
    title: str
    authors: list[str]
    text: str
    source: str
    published: str | None = None
    primary_category: str | None = None
    source_feed: str | None = None
    venue: str | None = None
    year: int | None = None
    conference_id: str | None = None
    abs_url: str | None = None
    pdf_url: str | None = None
    dblp_url: str | None = None
    paper_url: str | None = None
    abstract: str | None = None


@dataclass
class CategoryPick:
    rank: int
    title: str
    authors: list[str]
    category_score: int
    category_id: str
    display_score: int | None = None
    score_boost: int = 0
    matched_tags: list[str] = field(default_factory=list)
    source: str = ""
    published: str | None = None
    primary_category: str | None = None
    source_feed: str | None = None
    venue: str | None = None
    year: int | None = None
    conference_id: str | None = None
    abs_url: str | None = None
    pdf_url: str | None = None
    dblp_url: str | None = None
    paper_url: str | None = None
    abstract: str | None = None


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def parse_year(iso_ts: str) -> int | None:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.year
    except ValueError:
        return None


def _area_scoring() -> AreaPickScoring:
    return AreaPickScoring(categories=CATEGORIES, min_score=MIN_CATEGORY_SCORE)


def best_category(text: str) -> tuple[str, str, int, list[str]] | None:
    return _area_scoring().best_match(text)


def parse_years_list(raw: str | None) -> list[int]:
    if not raw:
        return list(DEFAULT_YEARS)
    years = sorted({int(part.strip()) for part in raw.split(",") if part.strip()})
    return years or list(DEFAULT_YEARS)


def format_period_label(years: list[int]) -> str:
    years = sorted(set(years))
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}\u2013{years[-1]}"


def load_arxiv_candidates(years: list[int]) -> list[PaperCandidate]:
    year_set = set(years)
    path = _ACTIVE_WEB_DATA / "arxiv-recent.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[PaperCandidate] = []
    for p in data.get("papers", []):
        pub_year = parse_year(p.get("published", ""))
        if pub_year not in year_set:
            continue
        if not passes_top_arxiv_gate(p):
            continue
        text = AreaPickScoring.paper_text(p)
        out.append(
            PaperCandidate(
                title=p["title"],
                authors=p.get("authors", []),
                text=text,
                source="arxiv",
                published=p.get("published"),
                primary_category=p.get("primary_category"),
                source_feed=p.get("source_feed"),
                abs_url=p.get("abs_url"),
                pdf_url=p.get("pdf_url"),
                paper_url=p.get("abs_url"),
            )
        )
    return out


def conference_scoring_text(paper: dict, meta: dict, conf: dict) -> str:
    """Keyword scoring text: title + abstract (when enriched) + bibliographic context."""
    short = meta.get("short_name") or conf.get("short_name") or ""
    abstract = (paper.get("abstract") or "").strip()
    parts = [
        paper.get("title", ""),
        abstract,
        " ".join(paper.get("authors", [])),
        short,
        meta.get("full_name") or conf.get("full_name") or "",
        paper.get("venue") or "",
    ]
    if not abstract:
        parts.append(VENUE_SCORE_HINTS.get(short, ""))
    parts.append("peer-reviewed conference proceedings")
    return " ".join(p for p in parts if p)


def effective_category_score(paper: PaperCandidate, score: int) -> int:
    if paper.source != "conference":
        return score
    boost = CONFERENCE_SCORE_BOOST
    if paper.year:
        boost += max(0, paper.year - RECENCY_BASE_YEAR) * RECENCY_BOOST_PER_YEAR
    return score + boost


def select_balanced_top_picks(
    pool: list[tuple[PaperCandidate, int, list[str]]],
    limit: int,
) -> list[tuple[PaperCandidate, int, list[str]]]:
    """Ensure top-N preview includes peer-reviewed conference papers, not only arXiv."""
    if not pool:
        return []

    def sort_key(item: tuple[PaperCandidate, int, list[str]]) -> int:
        return effective_category_score(item[0], item[1])

    conf = sorted([x for x in pool if x[0].source == "conference"], key=sort_key, reverse=True)
    arxiv = sorted([x for x in pool if x[0].source == "arxiv"], key=lambda x: x[1], reverse=True)

    n_conf = min(MIN_CONFERENCE_PREVIEW, limit, len(conf))
    chosen: list[tuple[PaperCandidate, int, list[str]]] = list(conf[:n_conf])
    seen = {normalize_title(x[0].title) for x in chosen}

    rest: list[tuple[PaperCandidate, int, list[str]]] = []
    for item in arxiv:
        key = normalize_title(item[0].title)
        if key and key in seen:
            continue
        rest.append(item)
    for item in conf[n_conf:]:
        key = normalize_title(item[0].title)
        if key and key in seen:
            continue
        rest.append(item)
    rest.sort(key=sort_key, reverse=True)

    while len(chosen) < limit and rest:
        item = rest.pop(0)
        chosen.append(item)
        key = normalize_title(item[0].title)
        if key:
            seen.add(key)

    chosen.sort(key=sort_key, reverse=True)
    return chosen[:limit]


def conference_paper_url(paper: dict, meta: dict) -> str | None:
    for url in paper.get("ee_links") or []:
        if "doi.org" in url or "acm.org" in url or "usenix.org" in url:
            return url
    return paper.get("dblp_url")


def load_conference_candidates(years: list[int]) -> list[PaperCandidate]:
    year_set = set(years)
    manifest_path = _ACTIVE_WEB_DATA / "conferences.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[PaperCandidate] = []
    for conf in manifest.get("conferences", []):
        if conf.get("year") not in year_set:
            continue
        data_path = _ACTIVE_WEB_DATA / f"{conf['id']}.json"
        if not data_path.is_file():
            continue
        data = json.loads(data_path.read_text(encoding="utf-8"))
        for paper in data.get("papers", []):
            text = conference_scoring_text(paper, data, conf)
            url = conference_paper_url(paper, data)
            abstract = (paper.get("abstract") or "").strip() or None
            out.append(
                PaperCandidate(
                    title=paper["title"],
                    authors=paper.get("authors", []),
                    text=text,
                    source="conference",
                    venue=data.get("short_name") or conf.get("short_name"),
                    year=data.get("year") or conf.get("year"),
                    conference_id=data.get("id") or conf.get("id"),
                    dblp_url=paper.get("dblp_url"),
                    paper_url=url or paper.get("dblp_url"),
                    abstract=abstract,
                )
            )
    return out


def pool_to_picks(
    cat_id: str,
    pool: list[tuple[PaperCandidate, int, list[str]]],
    *,
    highlight_conference_scores: bool = False,
) -> list[CategoryPick]:
    picks: list[CategoryPick] = []
    for rank, (paper, raw_score, tags) in enumerate(pool, start=1):
        boost = 0
        if highlight_conference_scores and paper.source == "conference":
            display = effective_category_score(paper, raw_score)
            boost = display - raw_score
        else:
            display = raw_score
        picks.append(
            CategoryPick(
                rank=rank,
                title=paper.title,
                authors=paper.authors,
                category_score=raw_score,
                display_score=display,
                score_boost=boost,
                category_id=cat_id,
                matched_tags=tags,
                source=paper.source,
                published=paper.published,
                primary_category=paper.primary_category,
                source_feed=paper.source_feed,
                venue=paper.venue,
                year=paper.year,
                conference_id=paper.conference_id,
                abs_url=paper.abs_url,
                pdf_url=paper.pdf_url,
                dblp_url=paper.dblp_url,
                paper_url=paper.paper_url,
                abstract=paper.abstract,
            )
        )
    return picks


def build_category_picks(
    candidates: list[PaperCandidate],
    *,
    mixed_sources: bool,
    highlight_conference_scores: bool = False,
) -> list[dict]:
    """Assign each paper to its best-scoring category; rank all matches per category."""
    by_cat: dict[str, list[tuple[PaperCandidate, int, list[str]]]] = {
        c["id"]: [] for c in CATEGORIES
    }

    seen_global: set[str] = set()
    for paper in candidates:
        key = normalize_title(paper.title)
        if not key or key in seen_global:
            continue
        match = best_category(paper.text)
        if not match:
            continue
        cat_id, _label, score, tags = match
        by_cat[cat_id].append((paper, score, tags))
        seen_global.add(key)

    def sort_key(item: tuple[PaperCandidate, int, list[str]]) -> int:
        if mixed_sources or highlight_conference_scores:
            return effective_category_score(item[0], item[1])
        return item[1]

    result: list[dict] = []
    highlight = highlight_conference_scores or mixed_sources
    for cat in CATEGORIES:
        cat_id = cat["id"]
        pool = sorted(by_cat[cat_id], key=sort_key, reverse=True)
        all_picks = pool_to_picks(cat_id, pool, highlight_conference_scores=highlight)
        if mixed_sources:
            top_pool = select_balanced_top_picks(pool, PER_CATEGORY_LIMIT)
        else:
            top_pool = pool[:PER_CATEGORY_LIMIT]
        top_picks = pool_to_picks(cat_id, top_pool, highlight_conference_scores=highlight)
        result.append(
            {
                "id": cat_id,
                "label": cat["label"],
                "total_count": len(all_picks),
                "count": len(top_picks),
                "picks": [asdict(p) for p in top_picks],
                "all_picks": [asdict(p) for p in all_picks],
            }
        )
    return result


def build_payload(
    *,
    kind: str,
    years: list[int],
    period: str,
    categories: list[dict],
    arxiv_pool: int,
    conference_pool: int,
    note: str,
    mixed_sources: bool,
) -> dict:
    return {
        "kind": kind,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "preview_limit": PER_CATEGORY_LIMIT,
        "period_label": period,
        "month_label": period,
        "arxiv_pool": arxiv_pool,
        "conference_pool": conference_pool,
        "mixed_sources": mixed_sources,
        "note": note,
        "ranking": {
            "conference_score_boost": CONFERENCE_SCORE_BOOST,
            "min_conference_preview": MIN_CONFERENCE_PREVIEW,
            "recency_boost_per_year": RECENCY_BOOST_PER_YEAR,
            "recency_base_year": RECENCY_BASE_YEAR,
        },
        "categories": categories,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build categorized top OS/LLM picks.")
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default=",".join(str(y) for y in DEFAULT_YEARS),
        help="comma-separated years for published conference pool (default: hub default_years)",
    )
    parser.add_argument(
        "--arxiv-years",
        default=None,
        help="comma-separated years for arXiv pool (default: hub arxiv_pick_years, e.g. 2025,2026)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="single year shorthand (overrides both --years and --arxiv-years)",
    )
    args = parser.parse_args()
    hub = load_hub(args.hub)
    configure_hub(hub)

    now = datetime.now(timezone.utc)
    if args.year is not None:
        published_years = [args.year]
        arxiv_years = [args.year]
    else:
        published_years = parse_years_list(args.years)
        arxiv_raw = args.arxiv_years or ",".join(str(y) for y in DEFAULT_ARXIV_YEARS)
        arxiv_years = parse_years_list(arxiv_raw)
    published_period = format_period_label(published_years)
    arxiv_period = format_period_label(arxiv_years)

    arxiv = load_arxiv_candidates(arxiv_years)
    conf = load_conference_candidates(published_years)

    if not arxiv:
        arxiv_path = _ACTIVE_WEB_DATA / "arxiv-recent.json"
        print(
            f"WARNING: no arXiv candidates for years {arxiv_years}. "
            f"Run crawl_arxiv_recent.py first (expected {arxiv_path}). "
            "top-monthly.json will have empty categories."
        )

    arxiv_categories = build_category_picks(arxiv, mixed_sources=False)
    published_categories = build_category_picks(
        conf,
        mixed_sources=False,
        highlight_conference_scores=True,
    )

    arxiv_payload = build_payload(
        kind="arxiv",
        years=arxiv_years,
        period=arxiv_period,
        categories=arxiv_categories,
        arxiv_pool=len(arxiv),
        conference_pool=0,
        mixed_sources=False,
        note=(
            f"Top {PER_CATEGORY_LIMIT} arXiv preprints per area (use More for full list), published "
            f"in {arxiv_period}. Ranked by keyword score on title and abstract."
        ),
    )
    published_payload = build_payload(
        kind="published",
        years=published_years,
        period=published_period,
        categories=published_categories,
        arxiv_pool=0,
        conference_pool=len(conf),
        mixed_sources=False,
        note=(
            f"Top {PER_CATEGORY_LIMIT} peer-reviewed papers per area from {published_period} proceedings "
            f"(SOSP, OSDI, NSDI, ASPLOS, EuroSys, ISCA, FAST, USENIX Security, USENIX ATC, ICSE). "
            f"Highlighted score = keyword match on title and abstract + {CONFERENCE_SCORE_BOOST} "
            "published boost (abstracts from DOI/OpenAlex/Semantic Scholar/arXiv when available)."
        ),
    )

    arxiv_path = _ACTIVE_WEB_DATA / "top-monthly.json"
    published_path = _ACTIVE_WEB_DATA / "top-published.json"
    arxiv_path.write_text(
        json.dumps(arxiv_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    published_path.write_text(
        json.dumps(published_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Legacy filename for older hub.js caches
    (_ACTIVE_WEB_DATA / "top-areas.json").write_text(
        json.dumps(published_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Categorized picks — arXiv {arxiv_period}, published {published_period}")
    print(f"  pools: arXiv={len(arxiv)}, conference={len(conf)}")
    print("  [arxiv] Recent arXiv picks:")
    for cat in arxiv_categories:
        print(f"    {cat['label']}: top {cat['count']} / {cat['total_count']}")
    print("  [published] Conference proceedings:")
    for cat in published_categories:
        print(f"    {cat['label']}: top {cat['count']} / {cat['total_count']}")
    print(f"Wrote {arxiv_path}")
    print(f"Wrote {published_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
