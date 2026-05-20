#!/usr/bin/env python3
"""Build conference timeline JSON for the homepage."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core.hub_config import add_hub_argument, load_hub

ROOT = Path(__file__).resolve().parent


def parse_day(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    args = parser.parse_args()
    hub = load_hub(args.hub)

    curated = hub.timeline
    year = curated["year"]
    web_data = hub.web_data
    out_json = web_data / "conference-timeline.json"
    out_js = hub.site_dir / "conference-timeline-data.js"

    manifest_path = web_data / "conferences.json"
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
        "hub_id": hub.id,
        "year": year,
        "today": today,
        "range_start": curated.get("range_start", f"{year}-01-01"),
        "range_end": curated.get("range_end", f"{year}-12-31"),
        "note": "Conference dates are event schedules; dblp badge means proceedings are indexed in this hub.",
        "events": events_out,
    }

    web_data.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_js.write_text(
        "export const conferenceTimeline = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )

    print(f"Timeline {year} ({hub.id}): {len(events_out)} venues, today={today}")
    for e in events_out:
        flag = "dblp" if e["in_dblp"] else "pending"
        print(f"  {e['short_name']:16} {e['event_start']}  [{e['status']}] {flag}")
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
