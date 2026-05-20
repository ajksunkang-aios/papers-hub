#!/usr/bin/env python3
"""
Enrich conference proceedings JSON with paper abstracts (via DOI / arXiv lookup).

Run after parse_dblp_xml --build-website and before build_top_monthly.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.hub_config import add_hub_argument, load_hub
from core.published_abstracts import (
    AbstractCache,
    AbstractFetcher,
    build_arxiv_title_index,
)

ROOT = Path(__file__).resolve().parent


def parse_years(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return list(default)
    years = sorted({int(p.strip()) for p in raw.split(",") if p.strip()})
    return years or list(default)


def enrich_conferences(
    web_data: Path,
    years: list[int],
    *,
    cache_path: Path,
    force: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    manifest_path = web_data / "conferences.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cache = AbstractCache(cache_path)
    arxiv_index = build_arxiv_title_index(web_data / "arxiv-recent.json")
    fetcher = AbstractFetcher(cache=cache, arxiv_by_title=arxiv_index)

    stats = {
        "papers": 0,
        "already_had": 0,
        "fetched": 0,
        "failed": 0,
        "conferences": 0,
    }

    for conf in manifest.get("conferences", []):
        year = conf.get("year")
        if year not in years:
            continue
        data_path = web_data / f"{conf['id']}.json"
        if not data_path.is_file():
            continue

        data = json.loads(data_path.read_text(encoding="utf-8"))
        papers = data.get("papers", [])
        changed = False
        conf_fetched = 0

        for paper in papers:
            if limit is not None and stats["papers"] >= limit:
                break
            stats["papers"] += 1

            existing = (paper.get("abstract") or "").strip()
            if existing and not force:
                stats["already_had"] += 1
                continue

            abstract, source = fetcher.resolve(
                title=paper.get("title", ""),
                ee_links=paper.get("ee_links"),
                dblp_key=paper.get("dblp_key"),
                force=force,
            )
            if abstract:
                paper["abstract"] = abstract
                paper["abstract_source"] = source
                stats["fetched"] += 1
                conf_fetched += 1
                changed = True
            else:
                stats["failed"] += 1

        if changed and not dry_run:
            data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if conf_fetched or changed:
            stats["conferences"] += 1
            print(
                f"  {conf['id']}: +{conf_fetched} abstracts "
                f"({sum(1 for p in papers if (p.get('abstract') or '').strip())}/{len(papers)} total)"
            )

        if limit is not None and stats["papers"] >= limit:
            break

    if not dry_run:
        cache.save()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch abstracts for conference papers and write them into proceedings JSON."
    )
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default=None,
        help="comma-separated years (default: hub pick_years or 2024,2025,2026)",
    )
    parser.add_argument("--force", action="store_true", help="re-fetch even if abstract exists")
    parser.add_argument("--limit", type=int, default=None, help="max papers to process (testing)")
    parser.add_argument("--dry-run", action="store_true", help="do not write JSON or cache")
    args = parser.parse_args()

    hub = load_hub(args.hub)
    default_years = hub.pick_years or [2023, 2024, 2025, 2026]
    years = parse_years(args.years, default_years)
    cache_path = hub.root / "data" / f"abstract-cache-{hub.id}.json"

    print(f"Enriching abstracts for {hub.id} ({years}) -> {hub.web_data}")
    stats = enrich_conferences(
        hub.web_data,
        years,
        cache_path=cache_path,
        force=args.force,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(
        f"Done: {stats['fetched']} new, {stats['already_had']} skipped (had abstract), "
        f"{stats['failed']} not found, {stats['papers']} scanned"
    )
    if not args.dry_run:
        print(f"Cache: {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
