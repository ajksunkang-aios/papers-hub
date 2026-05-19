#!/usr/bin/env python3
"""
Pick yesterday's top 3 arXiv papers strongly tied to OS/Linux kernel or systems LLM.

Reads website/data/arxiv-recent.json, writes today-broadcast.json + today-broadcast-data.js
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crawl_arxiv_recent import (
    has_llm_systems_signal,
    passes_systems_gate,
    score_keywords,
)

ROOT = Path(__file__).resolve().parent
WEB_DATA = ROOT / "website" / "data"
LIMIT = 3
MIN_BROADCAST_SCORE = 4

# Strongest signals for the rolling news bar (longest phrases first via score_keywords).
BROADCAST_KEYWORDS: list[tuple[str, int]] = [
    ("linux kernel", 24),
    ("os kernel", 24),
    ("system software", 20),
    ("kernel module", 16),
    ("operating system", 12),
    ("file system", 10),
    ("memory management", 8),
    ("ebpf", 10),
    ("syscall", 8),
    ("device driver", 8),
    ("inference serving", 14),
    ("model serving", 14),
    ("llm serving", 14),
    ("llm inference", 12),
    ("kv cache", 10),
    ("speculative decoding", 10),
    ("training system", 8),
    ("vllm", 8),
    ("runtime system", 8),
    ("storage system", 8),
    ("kernel", 2),
    ("llm", 2),
]

BROADCAST_STRONG = {
    "linux kernel",
    "os kernel",
    "system software",
    "kernel module",
    "operating system",
    "inference serving",
    "model serving",
    "llm serving",
}


@dataclass
class BroadcastPick:
    rank: int
    title: str
    authors: list[str]
    score: int
    matched_tags: list[str] = field(default_factory=list)
    published: str = ""
    abs_url: str = ""
    pdf_url: str = ""
    source_feed: str = ""
    arxiv_id: str = ""


def parse_utc_date(iso_ts: str) -> datetime | None:
    if not iso_ts:
        return None
    try:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_broadcast_paper(paper: dict) -> tuple[int, list[str]]:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = f"{title} {abstract}"
    score, tags = score_keywords(text, BROADCAST_KEYWORDS, BROADCAST_STRONG, max_tags=4)
    blob = text.lower()
    if "linux kernel" in blob or "os kernel" in blob:
        score += 8
    if "system software" in blob and has_llm_systems_signal(title, abstract):
        score += 6
    return score, tags


def qualifies_for_broadcast(paper: dict, score: int) -> bool:
    """Systems-relevant papers with a minimum keyword score."""
    if score < MIN_BROADCAST_SCORE:
        return False
    return passes_systems_gate(
        title=paper.get("title", ""),
        abstract=paper.get("abstract", ""),
        categories=paper.get("categories") or [],
        source_feed=paper.get("source_feed", ""),
    )


def load_scored_pool(path: Path) -> list[tuple[dict, int, list[str], datetime]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    pool: list[tuple[dict, int, list[str], datetime]] = []
    for paper in data.get("papers", []):
        dt = parse_utc_date(paper.get("published", ""))
        if dt is None:
            continue
        score, tags = score_broadcast_paper(paper)
        if not qualifies_for_broadcast(paper, score):
            continue
        pool.append((paper, score, tags, dt))
    pool.sort(key=lambda x: (x[3], x[1]), reverse=True)
    return pool


def pick_for_day(
    pool: list[tuple[dict, int, list[str], datetime]],
    day: datetime,
    *,
    limit: int,
    seen_ids: set[str],
) -> list[tuple[dict, int, list[str], datetime]]:
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    day_items = [item for item in pool if day_start <= item[3] < day_end]
    day_items.sort(key=lambda x: x[1], reverse=True)
    out: list[tuple[dict, int, list[str], datetime]] = []
    for item in day_items:
        paper, _score, _tags, _dt = item
        base_id = paper.get("arxiv_id", "").rsplit("v", 1)[0]
        if base_id in seen_ids:
            continue
        out.append(item)
        seen_ids.add(base_id)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    path = WEB_DATA / "arxiv-recent.json"
    pool = load_scored_pool(path)

    seen: set[str] = set()
    selected = pick_for_day(pool, yesterday, limit=LIMIT, seen_ids=seen)
    pool_note = ""
    if not selected:
        pool_note = (
            f"No strong kernel/systems LLM papers were posted on "
            f"{yesterday.strftime('%b %d, %Y')} (UTC)."
        )

    picks: list[BroadcastPick] = []
    for rank, (paper, score, tags, _dt) in enumerate(selected[:LIMIT], start=1):
        picks.append(
            BroadcastPick(
                rank=rank,
                title=paper["title"],
                authors=paper.get("authors", [])[:4],
                score=score,
                matched_tags=tags,
                published=paper.get("published", ""),
                abs_url=paper.get("abs_url", ""),
                pdf_url=paper.get("pdf_url", ""),
                source_feed=paper.get("source_feed", ""),
                arxiv_id=paper.get("arxiv_id", ""),
            )
        )

    date_label = yesterday.strftime("%B %d, %Y")
    payload = {
        "generated_at": now.isoformat(),
        "date_label": date_label,
        "yesterday_utc": yesterday.date().isoformat(),
        "pool_note": pool_note,
        "note": (
            "Top 3 arXiv papers from yesterday (UTC) strongly related to Linux/OS kernel, "
            "system software, or systems LLM."
        ),
        "count": len(picks),
        "picks": [asdict(p) for p in picks],
    }

    out_json = WEB_DATA / "today-broadcast.json"
    out_js = ROOT / "website" / "today-broadcast-data.js"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_js.write_text(
        "export const todayBroadcast = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Yesterday broadcast ({date_label}): {len(picks)} picks")
    for p in picks:
        print(f"  #{p.rank} ({p.score}) {p.title[:60]}")
    if pool_note:
        print(f"  note: {pool_note}")
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
