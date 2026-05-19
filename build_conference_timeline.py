#!/usr/bin/env python3
"""Build conference timeline JSON for the homepage (2026 editions + today)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURATED = ROOT / "conference_timeline_2026.json"
WEB_DATA = ROOT / "website" / "data"
OUT_JSON = WEB_DATA / "conference-timeline.json"
OUT_JS = ROOT / "website" / "conference-timeline-data.js"


def parse_day(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def main() -> int:
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    year = curated["year"]
    manifest_path = WEB_DATA / "conferences.json"
    by_slug: dict[str, dict] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for conf in manifest.get("conferences", []):
            if conf.get("year") != year:
                continue
            slug = conf.get("venue") or conf.get("id", "").rsplit("-", 1)[0]
            by_slug[slug] = conf

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    events_out: list[dict] = []
    for ev in curated["events"]:
        slug = ev["slug"]
        start = ev["event_start"]
        end = ev.get("event_end") or start
        start_dt = parse_day(start)
        end_dt = parse_day(end)
        conf = by_slug.get(slug)
        in_dblp = conf is not None
        if start_dt.date() <= now.date() <= end_dt.date():
            status = "in_progress"
        elif end_dt.date() < now.date():
            status = "past"
        else:
            status = "upcoming"

        events_out.append(
            {
                "slug": slug,
                "short_name": ev["short_name"],
                "event_start": start,
                "event_end": end,
                "location": ev.get("location", ""),
                "status": status,
                "in_dblp": in_dblp,
                "conference_id": conf.get("id") if conf else None,
                "paper_count": conf.get("paper_count") if conf else None,
                "proceedings_url": (conf.get("dblp_urls") or [None])[0] if conf else None,
            }
        )

    events_out.sort(key=lambda e: e["event_start"])

    payload = {
        "generated_at": now.isoformat(),
        "year": year,
        "today": today,
        "range_start": curated.get("range_start", f"{year}-01-01"),
        "range_end": curated.get("range_end", f"{year}-12-31"),
        "note": "Conference dates are event schedules; dblp badge means proceedings are indexed in this hub.",
        "events": events_out,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_JS.write_text(
        "export const conferenceTimeline = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )

    print(f"Timeline {year}: {len(events_out)} venues, today={today}")
    for e in events_out:
        flag = "dblp" if e["in_dblp"] else "pending"
        print(f"  {e['short_name']:16} {e['event_start']}  [{e['status']}] {flag}")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
