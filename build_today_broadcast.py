#!/usr/bin/env python3
"""
Pick recent top arXiv papers (prior calendar day in UTC+8) for kernel / systems LLM.

Reads website/data/arxiv-recent.json, writes today-broadcast.json + today-broadcast-data.js
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.hub_config import Hub, add_hub_argument, load_hub
from crawl_arxiv_recent import (
    active_hub,
    has_llm_systems_signal,
    passes_systems_gate,
    score_keywords,
    set_active_hub,
)

ROOT = Path(__file__).resolve().parent
WEB_DATA = ROOT / "website" / "data"
LIMIT = 3
MIN_BROADCAST_SCORE = 4
RECENT_LOOKBACK_DAYS = 7
_ACTIVE_WEB_DATA = WEB_DATA
_ACTIVE_SITE_DIR = ROOT / "website"


def configure_hub(hub: Hub) -> None:
    global LIMIT, MIN_BROADCAST_SCORE, RECENT_LOOKBACK_DAYS, _ACTIVE_WEB_DATA, _ACTIVE_SITE_DIR
    broadcast = hub.broadcast_policy
    LIMIT = int(broadcast.get("limit", LIMIT))
    MIN_BROADCAST_SCORE = int(broadcast.get("min_score", MIN_BROADCAST_SCORE))
    RECENT_LOOKBACK_DAYS = int(broadcast.get("lookback_days", RECENT_LOOKBACK_DAYS))
    _ACTIVE_WEB_DATA = hub.web_data
    _ACTIVE_SITE_DIR = hub.site_dir
    set_active_hub(hub)

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
    hub = active_hub()
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = f"{title} {abstract}"
    score, tags = score_keywords(
        text, hub.broadcast_keywords, hub.broadcast_strong, max_tags=4
    )
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
    day_items = [item for item in pool if day_start <= paper_local_date(item[3]) < day_end]
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


def pick_recent_window(
    pool: list[tuple[dict, int, list[str], datetime]],
    today: datetime,
    *,
    limit: int,
) -> tuple[
    list[tuple[dict, int, list[str], datetime]],
    list[tuple[dict, int, list[str], datetime]],
    datetime,
]:
    """Top `limit` papers plus all qualifying papers in the same UTC+8 window."""
    window_end = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    window_start = yesterday

    for lookback_days in range(2, RECENT_LOOKBACK_DAYS + 1):
        window_start = today - timedelta(days=lookback_days - 1)
        items = [item for item in pool if window_start <= paper_local_date(item[3]) < window_end]
        items.sort(key=lambda x: (x[3], x[1]), reverse=True)
        all_in_window = dedupe_pool_items(items)
        top = all_in_window[:limit]
        if len(top) >= limit or lookback_days == RECENT_LOOKBACK_DAYS:
            return top, all_in_window, window_start
    return [], [], yesterday


TZ_UTC8 = timezone(timedelta(hours=8))


def paper_local_date(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_UTC8)


def dedupe_pool_items(
    items: list[tuple[dict, int, list[str], datetime]],
) -> list[tuple[dict, int, list[str], datetime]]:
    seen_ids: set[str] = set()
    out: list[tuple[dict, int, list[str], datetime]] = []
    for item in items:
        paper = item[0]
        base_id = paper.get("arxiv_id", "").rsplit("v", 1)[0]
        if base_id in seen_ids:
            continue
        seen_ids.add(base_id)
        out.append(item)
    return out


def all_in_lookback(
    pool: list[tuple[dict, int, list[str], datetime]],
    today: datetime,
    *,
    lookback_days: int,
) -> list[tuple[dict, int, list[str], datetime]]:
    """All qualifying papers in the last N UTC+8 days."""
    window_end = today + timedelta(days=1)
    window_start = today - timedelta(days=lookback_days - 1)
    items = [item for item in pool if window_start <= paper_local_date(item[3]) < window_end]
    items.sort(key=lambda x: (x[3], x[1]), reverse=True)
    return dedupe_pool_items(items)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build recent arXiv broadcast picks.")
    add_hub_argument(parser)
    args = parser.parse_args()
    hub = load_hub(args.hub)
    configure_hub(hub)

    now = datetime.now(TZ_UTC8)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    path = _ACTIVE_WEB_DATA / "arxiv-recent.json"
    pool = load_scored_pool(path)

    selected, _narrow_window, window_start = pick_recent_window(pool, today, limit=LIMIT)
    all_in_window = all_in_lookback(pool, today, lookback_days=RECENT_LOOKBACK_DAYS)
    pool_note = ""
    if not selected:
        pool_note = (
            f"No strong kernel/system LLM papers in the last {RECENT_LOOKBACK_DAYS} days "
            f"({window_start.strftime('%b %d')}–{today.strftime('%b %d, %Y')}, UTC+8)."
        )

    def to_pick(rank: int, paper: dict, score: int, tags: list[str]) -> BroadcastPick:
        return BroadcastPick(
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

    preview_items = selected[:LIMIT] if selected else all_in_window[:LIMIT]
    picks = [
        to_pick(rank, paper, score, tags)
        for rank, (paper, score, tags, _dt) in enumerate(preview_items, start=1)
    ]
    all_picks = [
        to_pick(rank, paper, score, tags)
        for rank, (paper, score, tags, _dt) in enumerate(all_in_window, start=1)
    ]

    if selected:
        date_label = (
            f"{window_start.strftime('%b %d')}–{today.strftime('%b %d, %Y')} (UTC+8)"
        )
    else:
        date_label = f"{today.strftime('%B %d, %Y')} (UTC+8)"
    payload = {
        "generated_at": now.isoformat(),
        "date_label": date_label,
        "window_start_utc8": window_start.date().isoformat(),
        "window_end_utc8": today.date().isoformat(),
        "pool_note": pool_note,
        "note": hub.broadcast_policy.get(
            "note",
            (
                f"Top {LIMIT} arXiv papers from the last {RECENT_LOOKBACK_DAYS} days (UTC+8), "
                "preferring today and yesterday. Use More for all qualifying papers in that window."
            ),
        ),
        "preview_limit": LIMIT,
        "count": len(picks),
        "total_count": len(all_picks),
        "picks": [asdict(p) for p in picks],
        "all_picks": [asdict(p) for p in all_picks],
    }

    out_json = _ACTIVE_WEB_DATA / "today-broadcast.json"
    out_js = _ACTIVE_SITE_DIR / "today-broadcast-data.js"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_js.write_text(
        "export const todayBroadcast = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Recent broadcast UTC+8 ({date_label}): {len(picks)} shown / {len(all_picks)} in window")
    for p in picks:
        print(f"  #{p.rank} ({p.score}) {p.title[:60]}")
    if pool_note:
        print(f"  note: {pool_note}")
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
