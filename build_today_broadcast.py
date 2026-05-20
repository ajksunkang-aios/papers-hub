#!/usr/bin/env python3
"""
Pick recent top arXiv papers (prior calendar day in UTC+8) for kernel / systems LLM.

Uses the same area keyword scoring as top picks (title + abstract via categories.json).
Reads website/data/arxiv-recent.json, writes today-broadcast.json + today-broadcast-data.js
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.hub_config import Hub, add_hub_argument, load_hub
from core.picks_scoring import AreaPickScoring
from crawl_arxiv_recent import passes_top_arxiv_gate, set_active_hub

ROOT = Path(__file__).resolve().parent
WEB_DATA = ROOT / "website" / "data"
LIMIT = 3
RECENT_LOOKBACK_DAYS = 7
_ACTIVE_WEB_DATA = WEB_DATA
_ACTIVE_SITE_DIR = ROOT / "website"
_AREA_SCORING: AreaPickScoring | None = None


def configure_hub(hub: Hub) -> None:
    global LIMIT, RECENT_LOOKBACK_DAYS, _ACTIVE_WEB_DATA, _ACTIVE_SITE_DIR, _AREA_SCORING
    broadcast = hub.broadcast_policy
    LIMIT = int(broadcast.get("limit", LIMIT))
    RECENT_LOOKBACK_DAYS = int(broadcast.get("lookback_days", RECENT_LOOKBACK_DAYS))
    _ACTIVE_WEB_DATA = hub.web_data
    _ACTIVE_SITE_DIR = hub.site_dir
    _AREA_SCORING = AreaPickScoring.from_hub(hub)
    set_active_hub(hub)


def scoring() -> AreaPickScoring:
    if _AREA_SCORING is None:
        raise RuntimeError("configure_hub() must be called first")
    return _AREA_SCORING


@dataclass
class BroadcastPick:
    rank: int
    title: str
    authors: list[str]
    score: int
    matched_tags: list[str] = field(default_factory=list)
    category_id: str | None = None
    category_label: str | None = None
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


def score_broadcast_paper(paper: dict) -> tuple[int, list[str], str | None, str | None]:
    """Same metrics as top picks: keyword score on title + abstract (+ feed id)."""
    return scoring().score_paper(paper)


def qualifies_for_broadcast(paper: dict, score: int) -> bool:
    if score < scoring().min_score:
        return False
    return passes_top_arxiv_gate(paper)


def load_scored_pool(path: Path) -> list[tuple[dict, int, list[str], str | None, str | None, datetime]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    pool: list[tuple[dict, int, list[str], str | None, str | None, datetime]] = []
    for paper in data.get("papers", []):
        dt = parse_utc_date(paper.get("published", ""))
        if dt is None:
            continue
        score, tags, cat_id, cat_label = score_broadcast_paper(paper)
        if not qualifies_for_broadcast(paper, score):
            continue
        pool.append((paper, score, tags, cat_id, cat_label, dt))
    pool.sort(key=lambda x: (x[5], x[1]), reverse=True)
    return pool


def pick_for_day(
    pool: list[tuple[dict, int, list[str], str | None, str | None, datetime]],
    day: datetime,
    *,
    limit: int,
    seen_ids: set[str],
) -> list[tuple[dict, int, list[str], str | None, str | None, datetime]]:
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    day_items = [item for item in pool if day_start <= paper_local_date(item[5]) < day_end]
    day_items.sort(key=lambda x: x[1], reverse=True)
    out: list[tuple[dict, int, list[str], str | None, str | None, datetime]] = []
    for item in day_items:
        paper, _score, _tags, _cid, _clab, _dt = item
        base_id = paper.get("arxiv_id", "").rsplit("v", 1)[0]
        if base_id in seen_ids:
            continue
        out.append(item)
        seen_ids.add(base_id)
        if len(out) >= limit:
            break
    return out


def pick_recent_window(
    pool: list[tuple[dict, int, list[str], str | None, str | None, datetime]],
    today: datetime,
    *,
    limit: int,
) -> tuple[
    list[tuple[dict, int, list[str], str | None, str | None, datetime]],
    list[tuple[dict, int, list[str], str | None, str | None, datetime]],
    datetime,
]:
    """Top `limit` papers plus all qualifying papers in the same UTC+8 window."""
    window_end = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    window_start = yesterday

    for lookback_days in range(2, RECENT_LOOKBACK_DAYS + 1):
        window_start = today - timedelta(days=lookback_days - 1)
        items = [item for item in pool if window_start <= paper_local_date(item[5]) < window_end]
        items.sort(key=lambda x: (x[5], x[1]), reverse=True)
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
    items: list[tuple[dict, int, list[str], str | None, str | None, datetime]],
) -> list[tuple[dict, int, list[str], str | None, str | None, datetime]]:
    seen_ids: set[str] = set()
    out: list[tuple[dict, int, list[str], str | None, str | None, datetime]] = []
    for item in items:
        paper = item[0]
        base_id = paper.get("arxiv_id", "").rsplit("v", 1)[0]
        if base_id in seen_ids:
            continue
        seen_ids.add(base_id)
        out.append(item)
    return out


def all_in_lookback(
    pool: list[tuple[dict, int, list[str], str | None, str | None, datetime]],
    today: datetime,
    *,
    lookback_days: int,
) -> list[tuple[dict, int, list[str], str | None, str | None, datetime]]:
    """All qualifying papers in the last N UTC+8 days."""
    window_end = today + timedelta(days=1)
    window_start = today - timedelta(days=lookback_days - 1)
    items = [item for item in pool if window_start <= paper_local_date(item[5]) < window_end]
    items.sort(key=lambda x: (x[5], x[1]), reverse=True)
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

    def to_pick(
        rank: int,
        paper: dict,
        score: int,
        tags: list[str],
        cat_id: str | None,
        cat_label: str | None,
    ) -> BroadcastPick:
        return BroadcastPick(
            rank=rank,
            title=paper["title"],
            authors=paper.get("authors", [])[:4],
            score=score,
            matched_tags=tags,
            category_id=cat_id,
            category_label=cat_label,
            published=paper.get("published", ""),
            abs_url=paper.get("abs_url", ""),
            pdf_url=paper.get("pdf_url", ""),
            source_feed=paper.get("source_feed", ""),
            arxiv_id=paper.get("arxiv_id", ""),
        )

    preview_items = selected[:LIMIT] if selected else all_in_window[:LIMIT]
    picks = [
        to_pick(rank, paper, score, tags, cat_id, cat_label)
        for rank, (paper, score, tags, cat_id, cat_label, _dt) in enumerate(preview_items, start=1)
    ]
    all_picks = [
        to_pick(rank, paper, score, tags, cat_id, cat_label)
        for rank, (paper, score, tags, cat_id, cat_label, _dt) in enumerate(all_in_window, start=1)
    ]

    if selected:
        date_label = (
            f"{window_start.strftime('%b %d')}–{today.strftime('%b %d, %Y')} (UTC+8)"
        )
    else:
        date_label = f"{today.strftime('%B %d, %Y')} (UTC+8)"

    default_note = (
        f"Top {LIMIT} arXiv papers from the last {RECENT_LOOKBACK_DAYS} days (UTC+8), "
        "ranked by area keyword score on title and abstract (same as Top picks by area)."
    )
    payload = {
        "generated_at": now.isoformat(),
        "date_label": date_label,
        "window_start_utc8": window_start.date().isoformat(),
        "window_end_utc8": today.date().isoformat(),
        "pool_note": pool_note,
        "scoring": "area-keywords-title-abstract",
        "min_score": scoring().min_score,
        "note": hub.broadcast_policy.get("note", default_note),
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
        area = f" [{p.category_label}]" if p.category_label else ""
        print(f"  #{p.rank} ({p.score}){area} {p.title[:55]}")
    if pool_note:
        print(f"  note: {pool_note}")
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
