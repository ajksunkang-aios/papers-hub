#!/usr/bin/env python3
"""
Enrich arXiv and dblp conference JSON with per-author affiliations and countries.

Resolution order:
  1. dblp person-page affiliations (author search + profile HTML)
  2. arXiv XML / title-index affiliations (when available)
  3. Local institution/country keyword rules on affiliation text
  4. Optional OpenAlex fallback (--openalex; off by default)
  5. Placeholder affiliation so every author row is populated; country XX if unknown

Run after parse_dblp_xml --build-website and before build_country_analytics.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.author_country import (
    AuthorCountryCache,
    AuthorCountryResolver,
    build_arxiv_authors_index,
    load_author_country_policy,
)
from core.author_profiles import (
    attach_author_fields,
    finalize_authors_structured,
    merge_author_affiliations,
    paper_authors_complete,
    rows_need_real_affiliations,
    upgrade_authors_structured,
)
from core.dblp_affiliations import DblpAffiliationCache, DblpAffiliationFetcher
from core.hub_config import add_hub_argument, load_hub
from core.incremental import is_fresh, load_json, policy_fingerprint, save_json, utc_now_iso
from core.published_abstracts import normalize_title_key

ROOT = Path(__file__).resolve().parent
PROGRESS_EVERY = 10
CACHE_SAVE_EVERY = 10


def parse_years(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return list(default)
    years = sorted({int(p.strip()) for p in raw.split(",") if p.strip()})
    return years or list(default)


def log(msg: str) -> None:
    print(msg, flush=True)


def paper_needs_author_work(
    paper: dict[str, Any],
    *,
    force: bool = False,
    first_author_only: bool = False,
) -> bool:
    if force:
        return True
    return not paper_authors_complete(paper, first_author_only=first_author_only)


def count_papers_missing_affiliations(
    papers: list[dict[str, Any]],
    *,
    first_author_only: bool = False,
) -> int:
    return sum(
        1
        for paper in papers
        if paper_needs_author_work(paper, first_author_only=first_author_only)
    )


def enrich_paper_authors(
    paper: dict[str, Any],
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    arxiv_by_title: dict[str, list[dict[str, Any]]],
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
) -> bool:
    if not force and paper_authors_complete(paper, first_author_only=first_author_only):
        return False

    rows = upgrade_authors_structured(paper)
    if not rows:
        rows = [{"name": name, "affiliations": []} for name in (paper.get("authors") or []) if name]

    need_fetch = (
        rows_need_real_affiliations(rows[:1] if first_author_only and rows else rows)
        if first_author_only
        else rows_need_real_affiliations(rows)
    )
    # Placeholder "Unknown affiliation" must not block dblp person-page lookup.
    if dblp_fetcher is not None and need_fetch:
        if first_author_only:
            names = [rows[0].get("name", "")] if rows and rows[0].get("name") else []
        else:
            names = [row.get("name", "") for row in rows if row.get("name")]
        aff_by_name = dblp_fetcher.resolve_authors(names, force=force)
        rows = merge_author_affiliations(rows, aff_by_name)

    title_key = normalize_title_key(paper.get("title", ""))
    if need_fetch and title_key in arxiv_by_title:
        arxiv_rows = arxiv_by_title[title_key]
        if arxiv_rows:
            merged: list[dict[str, Any]] = []
            for idx, row in enumerate(rows):
                affs = [a for a in (row.get("affiliations") or []) if a]
                if not affs and idx < len(arxiv_rows):
                    affs = arxiv_rows[idx].get("affiliations") or []
                merged.append({"name": row.get("name") or "", "affiliations": affs})
            rows = merged

    resolved = resolver.resolve_paper_authors(
        title=paper.get("title", ""),
        authors=paper.get("authors"),
        authors_structured=rows,
        ee_links=paper.get("ee_links"),
        dblp_key=paper.get("dblp_key"),
        arxiv_id=paper.get("arxiv_id"),
        force=force,
    )
    if resolved:
        rows = resolved

    rows = finalize_authors_structured(rows, policy=policy)
    before = json.dumps(paper.get("authors_structured") or [], sort_keys=True)
    paper["authors_structured"] = rows
    paper["first_author_affiliations"] = rows[0].get("affiliations") or [] if rows else []
    after = json.dumps(rows, sort_keys=True)
    return before != after or not paper_authors_complete(paper, first_author_only=first_author_only)


def enrich_paper_list(
    papers: list[dict[str, Any]],
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    arxiv_by_title: dict[str, list[dict[str, Any]]],
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
    label: str = "papers",
) -> tuple[int, int]:
    changed = 0
    lookups = 0
    for idx, paper in enumerate(papers, start=1):
        if enrich_paper_authors(
            paper,
            resolver=resolver,
            dblp_fetcher=dblp_fetcher,
            arxiv_by_title=arxiv_by_title,
            policy=policy,
            force=force,
            first_author_only=first_author_only,
        ):
            changed += 1
        lookups += 1
        if idx % PROGRESS_EVERY == 0:
            missing = count_papers_missing_affiliations(
                papers, first_author_only=first_author_only
            )
            log(f"  {label} ... {idx}/{len(papers)} updated={changed} remaining={missing}")
        if lookups % CACHE_SAVE_EVERY == 0:
            # Author-country cache can be huge; persist dblp cache every N papers.
            if dblp_fetcher is not None:
                dblp_fetcher.cache.save()
            if idx % (CACHE_SAVE_EVERY * 5) == 0:
                resolver.cache.save()
    return changed, count_papers_missing_affiliations(
        papers, first_author_only=first_author_only
    )


def enrich_arxiv_json(
    arxiv_path: Path,
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
) -> tuple[int, int, int]:
    if not arxiv_path.is_file():
        return 0, 0, 0
    data = json.loads(arxiv_path.read_text(encoding="utf-8"))
    papers = data.get("papers", [])
    arxiv_index = build_arxiv_authors_index(arxiv_path)
    changed, remaining = enrich_paper_list(
        papers,
        resolver=resolver,
        dblp_fetcher=dblp_fetcher,
        arxiv_by_title=arxiv_index,
        policy=policy,
        force=force,
        first_author_only=first_author_only,
        label="arxiv",
    )
    if changed or remaining < len(papers):
        arxiv_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(papers), changed, remaining


def enrich_conferences(
    web_data: Path,
    years: list[int],
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    arxiv_path: Path,
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
) -> dict[str, int]:
    manifest = json.loads((web_data / "conferences.json").read_text(encoding="utf-8"))
    year_set = set(years)
    arxiv_index = build_arxiv_authors_index(arxiv_path)

    stats = {
        "papers": 0,
        "updated": 0,
        "conferences": 0,
        "remaining": 0,
    }

    for conf in manifest.get("conferences", []):
        if conf.get("year") not in year_set:
            continue
        data_path = web_data / f"{conf['id']}.json"
        if not data_path.is_file():
            continue
        data = json.loads(data_path.read_text(encoding="utf-8"))
        papers = data.get("papers", [])
        if not papers:
            continue
        stats["papers"] += len(papers)
        changed, remaining = enrich_paper_list(
            papers,
            resolver=resolver,
            dblp_fetcher=dblp_fetcher,
            arxiv_by_title=arxiv_index,
            policy=policy,
            force=force,
            first_author_only=first_author_only,
            label=conf["id"],
        )
        stats["remaining"] += remaining
        if changed:
            data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stats["conferences"] += 1
            stats["updated"] += changed
            log(f"  done {conf['id']}: updated {changed}/{len(papers)} papers, remaining={remaining}")

    resolver.cache.save()
    if dblp_fetcher is not None:
        dblp_fetcher.cache.save()
    return stats


def coverage_stats(
    web_data: Path,
    years: list[int],
    arxiv_path: Path,
    *,
    first_author_only: bool = False,
) -> dict[str, int]:
    year_set = set(years)
    total = 0
    complete = 0
    if arxiv_path.is_file():
        for paper in json.loads(arxiv_path.read_text(encoding="utf-8")).get("papers", []):
            total += 1
            if paper_authors_complete(paper, first_author_only=first_author_only):
                complete += 1
    manifest = json.loads((web_data / "conferences.json").read_text(encoding="utf-8"))
    for conf in manifest.get("conferences", []):
        if conf.get("year") not in year_set:
            continue
        path = web_data / f"{conf['id']}.json"
        if not path.is_file():
            continue
        for paper in json.loads(path.read_text(encoding="utf-8")).get("papers", []):
            total += 1
            if paper_authors_complete(paper, first_author_only=first_author_only):
                complete += 1
    return {"total": total, "complete": complete, "remaining": total - complete}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default=None,
        help="comma-separated years for conference proceedings (default hub pick years)",
    )
    parser.add_argument("--force", action="store_true", help="re-resolve even when affiliations exist")
    parser.add_argument(
        "--if-stale-hours",
        type=float,
        default=None,
        help="skip when manifest is fresh and all papers already have affiliations",
    )
    parser.add_argument(
        "--openalex",
        action="store_true",
        help="enable OpenAlex fallback when dblp/arXiv affiliations cannot resolve country (default: off)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="no HTTP calls (dblp person lookup and OpenAlex disabled)",
    )
    parser.add_argument(
        "--skip-dblp-fetch",
        action="store_true",
        help="do not fetch dblp person-page affiliations",
    )
    parser.add_argument("--skip-arxiv", action="store_true", help="only enrich conference JSON")
    parser.add_argument("--skip-conferences", action="store_true", help="only enrich arxiv-recent.json")
    parser.add_argument(
        "--first-author-only",
        action="store_true",
        help="only fetch/resolve first-author affiliations (enough for country analytics)",
    )
    parser.add_argument("--limit", type=int, default=None, help="max papers per dataset (testing)")
    args = parser.parse_args()

    hub = load_hub(args.hub)
    years = parse_years(args.years, hub.pick_years or [2023, 2024, 2025, 2026])
    policy = load_author_country_policy(hub.hub_dir)
    cache_path = hub.root / "data" / f"author-country-cache-{hub.id}.json"
    cache = AuthorCountryCache(cache_path)
    openalex_offline = args.offline or not args.openalex
    resolver = AuthorCountryResolver(cache=cache, policy=policy, offline=openalex_offline)
    dblp_cache_path = hub.root / "data" / f"dblp-affiliation-cache-{hub.id}.json"
    dblp_fetcher = None
    if not args.offline and not args.skip_dblp_fetch:
        dblp_fetcher = DblpAffiliationFetcher(cache=DblpAffiliationCache(dblp_cache_path), offline=False)
    arxiv_path = hub.site_json_path("arxiv-recent.json")

    manifest_path = hub.root / "data" / f"author-enrich-{hub.id}.json"
    run_fp = policy_fingerprint(
        {
            "hub": hub.id,
            "years": years,
            "openalex": args.openalex,
            "skip_dblp_fetch": args.skip_dblp_fetch,
            "first_author_only": args.first_author_only,
        }
    )

    before = coverage_stats(
        hub.web_data,
        years,
        arxiv_path if not args.skip_arxiv else Path("/dev/null"),
        first_author_only=args.first_author_only,
    )
    pending = before["remaining"]

    if (
        pending == 0
        and not args.force
        and args.if_stale_hours is not None
        and is_fresh(
            load_json(manifest_path),
            fingerprint=run_fp,
            max_age_hours=args.if_stale_hours,
            extra_keys={"years": years},
        )
    ):
        log(f"Author metadata complete for {hub.id} ({before['complete']}/{before['total']} papers)")
        return 0

    log(
        f"Enriching author metadata for {hub.id} years={years} "
        f"offline={args.offline} dblp_fetch={dblp_fetcher is not None} "
        f"first_author_only={args.first_author_only} "
        f"(pending {pending}/{before['total']} papers)"
    )

    arxiv_total = arxiv_changed = arxiv_remaining = 0
    if not args.skip_arxiv:
        arxiv_total, arxiv_changed, arxiv_remaining = enrich_arxiv_json(
            arxiv_path,
            resolver=resolver,
            dblp_fetcher=dblp_fetcher,
            policy=policy,
            force=args.force,
            first_author_only=args.first_author_only,
        )
        log(f"  arxiv-recent.json: updated {arxiv_changed}/{arxiv_total}, remaining={arxiv_remaining}")

    conf_stats = {"papers": 0, "updated": 0, "conferences": 0, "remaining": 0}
    if not args.skip_conferences:
        conf_stats = enrich_conferences(
            hub.web_data,
            years,
            resolver=resolver,
            dblp_fetcher=dblp_fetcher,
            arxiv_path=arxiv_path,
            policy=policy,
            force=args.force,
            first_author_only=args.first_author_only,
        )
        log(
            f"  conferences: updated {conf_stats['updated']} papers in "
            f"{conf_stats['conferences']} files, remaining={conf_stats['remaining']}"
        )

    after = coverage_stats(
        hub.web_data,
        years,
        arxiv_path if not args.skip_arxiv else Path("/dev/null"),
        first_author_only=args.first_author_only,
    )
    rate = (after["complete"] / after["total"]) if after["total"] else 1.0
    log(f"Affiliation coverage: {after['complete']}/{after['total']} ({rate * 100:.1f}%)")

    save_json(
        manifest_path,
        {
            "hub_id": hub.id,
            "source": "author-enrich",
            "fingerprint": run_fp,
            "years": years,
            "openalex": args.openalex,
            "skip_dblp_fetch": args.skip_dblp_fetch,
            "first_author_only": args.first_author_only,
            "built_at": utc_now_iso(),
            "coverage": after,
            "stats": {
                "arxiv_total": arxiv_total,
                "arxiv_updated": arxiv_changed,
                "arxiv_remaining": arxiv_remaining,
                **conf_stats,
            },
        },
    )
    log(f"Cache: {cache_path}")
    if dblp_fetcher is not None:
        log(f"dblp affiliation cache: {dblp_cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
