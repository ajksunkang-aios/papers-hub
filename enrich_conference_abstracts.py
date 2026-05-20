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
from core.incremental import is_fresh, load_json, policy_fingerprint, save_json, utc_now_iso
from core.published_abstracts import (
    AbstractCache,
    AbstractFetcher,
    build_arxiv_title_index,
    lookup_cache_keys,
)

ROOT = Path(__file__).resolve().parent

PROGRESS_EVERY = 25
CACHE_SAVE_EVERY = 50


def parse_years(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return list(default)
    years = sorted({int(p.strip()) for p in raw.split(",") if p.strip()})
    return years or list(default)


def log(msg: str) -> None:
    print(msg, flush=True)


def paper_needs_work(paper: dict, cache: AbstractCache, *, force: bool = False) -> bool:
    """True when this paper may still need a resolve() call (network or cache apply)."""
    if force:
        return True
    if (paper.get("abstract") or "").strip():
        return False
    keys = lookup_cache_keys(
        title=paper.get("title", ""),
        ee_links=paper.get("ee_links"),
        dblp_key=paper.get("dblp_key"),
    )
    if not keys:
        return True
    for key in keys:
        if cache.get(key):
            return True
    if all(cache.is_miss(key) for key in keys):
        return False
    return True


def plan_enrichment(
    web_data: Path,
    years: list[int],
    *,
    cache: AbstractCache,
    force: bool = False,
) -> tuple[list[dict], int, int, int]:
    """Return (jobs, total papers, papers needing work, papers with known cache miss)."""
    manifest_path = web_data / "conferences.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    year_set = set(years)
    jobs: list[dict] = []
    total_papers = 0
    need_work = 0
    skipped_miss = 0

    for conf in manifest.get("conferences", []):
        if conf.get("year") not in year_set:
            continue
        data_path = web_data / f"{conf['id']}.json"
        if not data_path.is_file():
            continue
        papers = json.loads(data_path.read_text(encoding="utf-8")).get("papers", [])
        pending = 0
        conf_skipped = 0
        for paper in papers:
            if (paper.get("abstract") or "").strip() and not force:
                continue
            if paper_needs_work(paper, cache, force=force):
                pending += 1
            else:
                conf_skipped += 1
        total_papers += len(papers)
        need_work += pending
        skipped_miss += conf_skipped
        jobs.append(
            {
                "id": conf["id"],
                "year": conf.get("year"),
                "path": data_path,
                "papers": len(papers),
                "missing": pending,
                "skipped_miss": conf_skipped,
            }
        )
    return jobs, total_papers, need_work, skipped_miss


def enrich_conferences(
    web_data: Path,
    years: list[int],
    *,
    cache_path: Path,
    force: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
    allow_arxiv_api: bool = False,
    progress_every: int = PROGRESS_EVERY,
) -> dict[str, int]:
    cache = AbstractCache(cache_path)
    jobs, total_papers, need_work, skipped_miss = plan_enrichment(
        web_data, years, cache=cache, force=force
    )
    log(
        f"  {len(jobs)} conferences, {total_papers} papers, "
        f"{need_work} to process, {skipped_miss} skipped (cached miss)"
        f"{', arXiv title API' if allow_arxiv_api else ', arXiv title API off'}"
    )
    if need_work == 0:
        log("  nothing to do (incremental complete for these years)")
        return {
            "papers": 0,
            "already_had": total_papers,
            "fetched": 0,
            "failed": 0,
            "cached_miss": skipped_miss,
            "conferences": 0,
        }
    arxiv_index = build_arxiv_title_index(web_data / "arxiv-recent.json")
    fetcher = AbstractFetcher(
        cache=cache, arxiv_by_title=arxiv_index, allow_arxiv_api=allow_arxiv_api
    )

    stats = {
        "papers": 0,
        "already_had": 0,
        "fetched": 0,
        "failed": 0,
        "cached_miss": skipped_miss,
        "cache_applied": 0,
        "conferences": 0,
    }
    lookups_since_cache_save = 0

    for job in jobs:
        if limit is not None and stats["papers"] >= limit:
            break
        if job["missing"] == 0:
            continue

        log(
            f"  [{job['id']}] {job['papers']} papers, {job['missing']} without abstract..."
        )
        data = json.loads(job["path"].read_text(encoding="utf-8"))
        papers = data.get("papers", [])
        changed = False
        conf_fetched = 0
        conf_processed = 0

        for paper in papers:
            if limit is not None and stats["papers"] >= limit:
                break
            stats["papers"] += 1
            conf_processed += 1

            existing = (paper.get("abstract") or "").strip()
            if existing and not force:
                stats["already_had"] += 1
                continue

            if not paper_needs_work(paper, cache, force=force):
                stats["cached_miss"] += 1
                continue

            abstract, source = fetcher.resolve(
                title=paper.get("title", ""),
                ee_links=paper.get("ee_links"),
                dblp_key=paper.get("dblp_key"),
                force=force,
            )
            lookups_since_cache_save += 1
            if abstract:
                paper["abstract"] = abstract
                paper["abstract_source"] = source
                stats["fetched"] += 1
                if source == "cache":
                    stats["cache_applied"] += 1
                conf_fetched += 1
                changed = True
            elif source == "cache-miss":
                stats["cached_miss"] += 1
            else:
                stats["failed"] += 1

            if conf_processed % progress_every == 0:
                log(
                    f"    ... {conf_processed}/{job['papers']} in {job['id']} "
                    f"(+{stats['fetched']} fetched, {stats['failed']} missed)"
                )
            if not dry_run and lookups_since_cache_save >= CACHE_SAVE_EVERY:
                cache.save()
                lookups_since_cache_save = 0

        if changed and not dry_run:
            job["path"].write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if conf_fetched or changed:
            stats["conferences"] += 1
            with_abstract = sum(1 for p in papers if (p.get("abstract") or "").strip())
            log(
                f"  done {job['id']}: +{conf_fetched} abstracts "
                f"({with_abstract}/{len(papers)} total)"
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
        help="comma-separated years (default: hub pick_years or 2023-2026)",
    )
    parser.add_argument("--force", action="store_true", help="re-fetch even if abstract exists")
    parser.add_argument("--limit", type=int, default=None, help="max papers to process (testing)")
    parser.add_argument("--dry-run", action="store_true", help="do not write JSON or cache")
    parser.add_argument(
        "--if-stale-hours",
        type=float,
        default=None,
        help="with no pending papers, skip if manifest is newer than N hours (incremental always runs when work remains)",
    )
    parser.add_argument(
        "--arxiv-api",
        action="store_true",
        help="allow slow per-title arXiv API search when DOI lookup fails (off by default)",
    )
    args = parser.parse_args()

    hub = load_hub(args.hub)
    default_years = hub.pick_years or [2023, 2024, 2025, 2026]
    years = parse_years(args.years, default_years)
    manifest_path = hub.root / "data" / f"abstract-enrich-{hub.id}.json"
    run_fp = policy_fingerprint(
        {"hub": hub.id, "years": years, "arxiv_api": args.arxiv_api}
    )
    cache_path = hub.root / "data" / f"abstract-cache-{hub.id}.json"
    cache = AbstractCache(cache_path)
    _, _, pending_work, _ = plan_enrichment(
        hub.web_data, years, cache=cache, force=args.force
    )

    if (
        pending_work == 0
        and not args.force
        and (
            args.if_stale_hours is None
            or is_fresh(
                load_json(manifest_path),
                fingerprint=run_fp,
                max_age_hours=args.if_stale_hours,
                extra_keys={"years": years},
            )
        )
    ):
        log(f"Abstract enrichment up to date for {years} (no pending papers)")
        return 0

    log(f"Enriching abstracts for {hub.id} ({years}) -> {hub.web_data}")
    log(f"  incremental: {pending_work} papers still need work")
    if not args.arxiv_api:
        log("  (arXiv title API disabled; pass --arxiv-api for slower backfill)")
    stats = enrich_conferences(
        hub.web_data,
        years,
        cache_path=cache_path,
        force=args.force,
        limit=args.limit,
        dry_run=args.dry_run,
        allow_arxiv_api=args.arxiv_api,
    )
    log(
        f"Done: {stats['fetched']} new ({stats.get('cache_applied', 0)} from cache), "
        f"{stats['already_had']} already in JSON, "
        f"{stats.get('cached_miss', 0)} cached miss, "
        f"{stats['failed']} not found, {stats['papers']} scanned"
    )
    if not args.dry_run:
        log(f"Cache: {cache_path}")
        save_json(
            manifest_path,
            {
                "hub_id": hub.id,
                "source": "abstract-enrich",
                "fingerprint": run_fp,
                "years": years,
                "arxiv_api": args.arxiv_api,
                "built_at": utc_now_iso(),
                "stats": stats,
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
