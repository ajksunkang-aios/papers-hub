#!/usr/bin/env python3
"""
Build categorized top-10 recommendations (arXiv + conference for a calendar year).

Output: website/data/top-monthly.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.hub_config import Hub, add_hub_argument, load_hub
from crawl_arxiv_recent import passes_top_arxiv_gate, score_keywords

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
DEFAULT_YEARS = [2024, 2025, 2026]
_ACTIVE_WEB_DATA = WEB_DATA


def configure_hub(hub: Hub) -> None:
    global CATEGORIES, MIN_CATEGORY_SCORE, PER_CATEGORY_LIMIT, DEFAULT_YEARS, _ACTIVE_WEB_DATA
    CATEGORIES = hub.category_rows
    MIN_CATEGORY_SCORE = int(hub.categories.get("min_category_score", MIN_CATEGORY_SCORE))
    PER_CATEGORY_LIMIT = int(hub.categories.get("per_category_limit", PER_CATEGORY_LIMIT))
    DEFAULT_YEARS = [int(y) for y in hub.categories.get("default_years", DEFAULT_YEARS)]
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


@dataclass
class CategoryPick:
    rank: int
    title: str
    authors: list[str]
    category_score: int
    category_id: str
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


def score_for_category(text: str, cat: dict) -> tuple[int, list[str]]:
    keywords = cat["keywords"]
    strong = {kw for kw, w in keywords if w >= 10}
    return score_keywords(text, keywords, strong, max_tags=6)


def best_category(text: str) -> tuple[str, str, int, list[str]] | None:
    best_id = ""
    best_label = ""
    best_score = 0
    best_tags: list[str] = []
    for cat in CATEGORIES:
        s, tags = score_for_category(text, cat)
        if s > best_score:
            best_score = s
            best_id = cat["id"]
            best_label = cat["label"]
            best_tags = tags
    if best_score < MIN_CATEGORY_SCORE:
        return None
    return best_id, best_label, best_score, best_tags


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
        abstract = p.get("abstract", "")
        text = f"{p['title']} {abstract} {p.get('source_feed', '')}"
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
            authors_str = " ".join(paper.get("authors", []))
            text = f"{paper['title']} {authors_str}"
            url = conference_paper_url(paper, data)
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
                )
            )
    return out


def pool_to_picks(
    cat_id: str, pool: list[tuple[PaperCandidate, int, list[str]]]
) -> list[CategoryPick]:
    picks: list[CategoryPick] = []
    for rank, (paper, cat_score, tags) in enumerate(pool, start=1):
        picks.append(
            CategoryPick(
                rank=rank,
                title=paper.title,
                authors=paper.authors,
                category_score=cat_score,
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
            )
        )
    return picks


def build_category_picks(candidates: list[PaperCandidate]) -> list[dict]:
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

    result: list[dict] = []
    for cat in CATEGORIES:
        cat_id = cat["id"]
        pool = sorted(by_cat[cat_id], key=lambda x: x[1], reverse=True)
        all_picks = pool_to_picks(cat_id, pool)
        top_picks = all_picks[:PER_CATEGORY_LIMIT]
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build categorized top OS/LLM picks.")
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default=",".join(str(y) for y in DEFAULT_YEARS),
        help="comma-separated calendar years for arXiv + conference pools (default: 2024,2025,2026)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="single year shorthand (overrides --years)",
    )
    args = parser.parse_args()
    hub = load_hub(args.hub)
    configure_hub(hub)

    now = datetime.now(timezone.utc)
    years = [args.year] if args.year is not None else parse_years_list(args.years)
    period = format_period_label(years)

    arxiv = load_arxiv_candidates(years)
    conf = load_conference_candidates(years)
    all_candidates = arxiv + conf
    categories = build_category_picks(all_candidates)

    payload = {
        "generated_at": now.isoformat(),
        "years": years,
        "preview_limit": PER_CATEGORY_LIMIT,
        "period_label": period,
        "month_label": period,
        "arxiv_pool": len(arxiv),
        "conference_pool": len(conf),
        "note": (
            f"Top {PER_CATEGORY_LIMIT} per area (use More for full list): arXiv papers published "
            f"in {period}, plus {period} conference proceedings from dblp. Each paper is placed "
            "in its single best-matching category by keyword score."
        ),
        "categories": categories,
    }

    out_json = _ACTIVE_WEB_DATA / "top-monthly.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Categorized top picks for {period}")
    print(f"  pools: arXiv={len(arxiv)}, conference={len(conf)}")
    for cat in categories:
        print(f"  {cat['label']}: top {cat['count']} / {cat['total_count']} matched")
        for p in cat["picks"][:3]:
            print(f"    #{p['rank']} ({p['category_score']}) {p['title'][:55]}")
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
