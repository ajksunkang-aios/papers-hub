#!/usr/bin/env python3
"""Build client-side keyword search index (title + abstract, technical lookup)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.hub_config import Hub, add_hub_argument, load_hub

from build_country_analytics import conference_years, load_dblp_papers, parse_years

ABSTRACT_INDEX_MAX = 1200
ROOT = Path(__file__).resolve().parent


def is_proceedings_record(paper: dict[str, Any], meta: dict[str, Any]) -> bool:
    keys = meta.get("skip_dblp_keys") or []
    dblp_key = paper.get("dblp_key")
    if dblp_key and dblp_key in keys:
        return True
    title = paper.get("title") or ""
    for pat in meta.get("skip_title_patterns") or []:
        if re.search(pat, title, re.I):
            return True
    return False


def truncate_abstract(text: str, *, max_len: int = ABSTRACT_INDEX_MAX) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def parse_paper_year(value: str | int | None, fallback: int | None = None) -> int | None:
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except ValueError:
        m = re.search(r"(20\d{2})", str(value))
        return int(m.group(1)) if m else fallback


def load_dblp_entries(web_data: Path, years: set[int]) -> list[dict[str, Any]]:
    manifest = json.loads((web_data / "conferences.json").read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for conf in manifest.get("conferences") or []:
        year = conf.get("year")
        if year not in years:
            continue
        data_path = web_data / f"{conf['id']}.json"
        if not data_path.is_file():
            continue
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        meta = payload.get("meta") or payload
        for paper in payload.get("papers") or []:
            if is_proceedings_record(paper, meta):
                continue
            paper_year = parse_paper_year(paper.get("year"), fallback=year)
            abstract = truncate_abstract(paper.get("abstract") or "")
            dblp_key = paper.get("dblp_key") or ""
            out.append(
                {
                    "id": f"dblp:{dblp_key or conf['id']}:{paper.get('title', '')[:48]}",
                    "title": paper.get("title") or "",
                    "abstract": abstract,
                    "year": paper_year,
                    "venue": paper.get("venue") or meta.get("short_name") or conf.get("short_name"),
                    "source": "dblp",
                    "href": f"conference.html?id={conf['id']}",
                    "external_url": paper.get("dblp_url") or "",
                }
            )
    return out


def load_arxiv_entries(web_data: Path, years: set[int]) -> list[dict[str, Any]]:
    path = web_data / "arxiv-recent.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for paper in payload.get("papers") or []:
        arxiv_id = paper.get("arxiv_id") or ""
        base_id = arxiv_id.rsplit("v", 1)[0]
        if not base_id or base_id in seen:
            continue
        published = paper.get("published") or ""
        paper_year = None
        if published:
            try:
                paper_year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
            except ValueError:
                paper_year = None
        if paper_year is not None and paper_year not in years:
            continue
        seen.add(base_id)
        out.append(
            {
                "id": f"arxiv:{base_id}",
                "title": paper.get("title") or "",
                "abstract": truncate_abstract(paper.get("abstract") or ""),
                "year": paper_year,
                "venue": paper.get("source_feed") or paper.get("primary_category") or "arXiv",
                "source": "arxiv",
                "href": paper.get("abs_url") or "",
                "external_url": paper.get("pdf_url") or "",
            }
        )
    return out


def build_index(
    hub: Hub,
    *,
    years: list[int],
    arxiv_years: list[int],
) -> dict[str, Any]:
    year_set = set(years)
    arxiv_year_set = set(arxiv_years)
    dblp_rows = load_dblp_entries(hub.web_data, year_set)
    arxiv_rows = load_arxiv_entries(hub.web_data, arxiv_year_set)
    papers = dblp_rows + arxiv_rows
    with_abstract = sum(1 for row in papers if row.get("abstract"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hub_id": hub.id,
        "years": years,
        "arxiv_years": arxiv_years,
        "count": len(papers),
        "dblp_count": len(dblp_rows),
        "arxiv_count": len(arxiv_rows),
        "with_abstract_count": with_abstract,
        "match_fields": ["title", "abstract"],
        "papers": papers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default="all",
        help="Comma-separated dblp years, or 'all' for every year in conferences.json",
    )
    parser.add_argument(
        "--arxiv-years",
        default=None,
        help="Comma-separated arXiv years (default: hub arxiv_pick_years)",
    )
    args = parser.parse_args()

    hub = load_hub(args.hub)
    all_years = conference_years(hub.web_data) or list(hub.pick_years)
    years = parse_years(args.years, all_years)
    arxiv_default = list(hub.arxiv_pick_years)
    arxiv_years = parse_years(args.arxiv_years, arxiv_default) if args.arxiv_years else arxiv_default

    payload = build_index(hub, years=years, arxiv_years=arxiv_years)
    out_path = hub.web_data / "search-index.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out_path}  papers={payload['count']} "
        f"(dblp={payload['dblp_count']} arxiv={payload['arxiv_count']} "
        f"with_abstract={payload['with_abstract_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
