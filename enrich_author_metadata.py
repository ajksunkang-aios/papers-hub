#!/usr/bin/env python3
"""
Enrich dblp conference JSON with per-author affiliations and countries.

Resolution order:
  1. Reload from disk caches (author-paper-reload / author-country / dblp-affiliation)
  2. dblp person-page affiliations (author search + profile HTML) — incremental only
  3. Local institution/country keyword rules on affiliation text
  4. Optional OpenAlex fallback (--openalex; off by default)
  5. Placeholder affiliation so every author row is populated; country XX if unknown

By default only conference proceedings (pick years) are enriched. arXiv recent
papers are opt-in via --with-arxiv (not used for country analytics).

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
    finalize_authors_structured,
    merge_author_affiliations,
    paper_authors_complete,
    rows_need_real_affiliations,
    upgrade_authors_structured,
)
from core.author_reload import (
    AuthorPaperReloadIndex,
    apply_dblp_cache_affiliations,
    dblp_authors_resolved,
    load_cached_authors_structured,
    paper_needs_online_fetch,
    target_author_names,
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
    dblp_cache: DblpAffiliationCache | None = None,
) -> bool:
    """True when paper still needs online dblp work (or force)."""
    return paper_needs_online_fetch(
        paper,
        dblp_cache=dblp_cache,
        force=force,
        first_author_only=first_author_only,
    )


def count_papers_missing_affiliations(
    papers: list[dict[str, Any]],
    *,
    first_author_only: bool = False,
    dblp_cache: DblpAffiliationCache | None = None,
) -> int:
    return sum(
        1
        for paper in papers
        if paper_needs_author_work(
            paper,
            first_author_only=first_author_only,
            dblp_cache=dblp_cache,
        )
    )


def _apply_rows_to_paper(
    paper: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> bool:
    rows = finalize_authors_structured(rows, policy=policy)
    before = json.dumps(paper.get("authors_structured") or [], sort_keys=True)
    paper["authors_structured"] = rows
    paper["first_author_affiliations"] = rows[0].get("affiliations") or [] if rows else []
    after = json.dumps(rows, sort_keys=True)
    return before != after


def reload_paper_from_disk(
    paper: dict[str, Any],
    *,
    resolver: AuthorCountryResolver,
    dblp_cache: DblpAffiliationCache | None,
    reload_index: AuthorPaperReloadIndex | None,
    policy: dict[str, Any],
    first_author_only: bool = False,
) -> bool:
    """Hydrate paper from local caches only (no HTTP). Returns True if modified."""
    if paper_authors_complete(paper, first_author_only=first_author_only):
        return False

    # 1) Prefer paper-level caches that already have real affiliations.
    rows = None
    if reload_index is not None:
        rows = reload_index.get(paper, first_author_only=first_author_only)
    if rows is None:
        rows = load_cached_authors_structured(
            paper, resolver.cache, first_author_only=first_author_only
        )
    if rows:
        return _apply_rows_to_paper(paper, rows, policy=policy)

    # 2) Rebuild from per-author dblp affiliation cache (hit or miss).
    if dblp_cache is None:
        return False
    names = target_author_names(paper, first_author_only=first_author_only)
    if not dblp_authors_resolved(names, dblp_cache):
        return False

    rows = apply_dblp_cache_affiliations(
        paper, dblp_cache, first_author_only=first_author_only
    )
    # force=True: do not let empty XX paper-cache entries override dblp affs.
    resolved = resolver.resolve_paper_authors(
        title=paper.get("title", ""),
        authors=paper.get("authors"),
        authors_structured=rows,
        ee_links=paper.get("ee_links"),
        dblp_key=paper.get("dblp_key"),
        arxiv_id=paper.get("arxiv_id"),
        force=True,
    )
    if resolved:
        rows = resolved
    return _apply_rows_to_paper(paper, rows, policy=policy)


def enrich_paper_authors(
    paper: dict[str, Any],
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    arxiv_by_title: dict[str, list[dict[str, Any]]],
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
    reload_index: AuthorPaperReloadIndex | None = None,
    dblp_cache: DblpAffiliationCache | None = None,
    disk_reload: bool = True,
) -> bool:
    if dblp_cache is None and dblp_fetcher is not None:
        dblp_cache = dblp_fetcher.cache

    # Always try disk caches first (CI restores these between runs).
    reloaded = False
    if disk_reload:
        reloaded = reload_paper_from_disk(
            paper,
            resolver=resolver,
            dblp_cache=dblp_cache,
            reload_index=reload_index,
            policy=policy,
            first_author_only=first_author_only,
        )

    if not force and not paper_needs_online_fetch(
        paper,
        dblp_cache=dblp_cache,
        force=False,
        first_author_only=first_author_only,
    ):
        if reloaded and reload_index is not None:
            reload_index.set_paper(paper, first_author_only=first_author_only)
        return reloaded

    if not force and paper_authors_complete(paper, first_author_only=first_author_only):
        return reloaded

    rows = upgrade_authors_structured(paper)
    if not rows:
        rows = [{"name": name, "affiliations": []} for name in (paper.get("authors") or []) if name]

    need_fetch = (
        rows_need_real_affiliations(rows[:1] if first_author_only and rows else rows)
        if first_author_only
        else rows_need_real_affiliations(rows)
    )
    # Placeholder "Unknown affiliation" must not block dblp person-page lookup.
    if need_fetch:
        if first_author_only:
            names = [rows[0].get("name", "")] if rows and rows[0].get("name") else []
        else:
            names = [row.get("name", "") for row in rows if row.get("name")]
        # Skip HTTP when every target author is already hit/miss in disk cache.
        if dblp_fetcher is not None and (force or not dblp_authors_resolved(names, dblp_cache)):
            aff_by_name = dblp_fetcher.resolve_authors(names, force=force)
            rows = merge_author_affiliations(rows, aff_by_name)
        elif dblp_cache is not None:
            rows = apply_dblp_cache_affiliations(
                paper, dblp_cache, first_author_only=first_author_only
            )

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

    changed = _apply_rows_to_paper(paper, rows, policy=policy) or reloaded
    if reload_index is not None and paper.get("authors_structured"):
        reload_index.set_paper(paper, first_author_only=first_author_only)
    return changed or not paper_authors_complete(paper, first_author_only=first_author_only)


def enrich_paper_list(
    papers: list[dict[str, Any]],
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    arxiv_by_title: dict[str, list[dict[str, Any]]],
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
    reload_index: AuthorPaperReloadIndex | None = None,
    dblp_cache: DblpAffiliationCache | None = None,
    disk_reload: bool = True,
    limit: int | None = None,
    label: str = "papers",
) -> tuple[int, int]:
    changed = 0
    lookups = 0
    if dblp_cache is None and dblp_fetcher is not None:
        dblp_cache = dblp_fetcher.cache
    work = papers[:limit] if limit is not None and limit > 0 else papers
    for idx, paper in enumerate(work, start=1):
        if enrich_paper_authors(
            paper,
            resolver=resolver,
            dblp_fetcher=dblp_fetcher,
            arxiv_by_title=arxiv_by_title,
            policy=policy,
            force=force,
            first_author_only=first_author_only,
            reload_index=reload_index,
            dblp_cache=dblp_cache,
            disk_reload=disk_reload,
        ):
            changed += 1
        lookups += 1
        if idx % PROGRESS_EVERY == 0:
            missing = count_papers_missing_affiliations(
                work,
                first_author_only=first_author_only,
                dblp_cache=dblp_cache,
            )
            log(f"  {label} ... {idx}/{len(work)} updated={changed} online_pending={missing}")
        if lookups % CACHE_SAVE_EVERY == 0:
            # Author-country cache can be huge; persist dblp cache every N papers.
            if dblp_fetcher is not None:
                dblp_fetcher.cache.save()
            elif dblp_cache is not None:
                dblp_cache.save()
            if idx % (CACHE_SAVE_EVERY * 5) == 0:
                resolver.cache.save()
                if reload_index is not None:
                    reload_index.save()
    return changed, count_papers_missing_affiliations(
        work,
        first_author_only=first_author_only,
        dblp_cache=dblp_cache,
    )



def enrich_arxiv_json(
    arxiv_path: Path,
    *,
    resolver: AuthorCountryResolver,
    dblp_fetcher: DblpAffiliationFetcher | None,
    policy: dict[str, Any],
    force: bool = False,
    first_author_only: bool = False,
    reload_index: AuthorPaperReloadIndex | None = None,
    dblp_cache: DblpAffiliationCache | None = None,
    disk_reload: bool = True,
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
        reload_index=reload_index,
        dblp_cache=dblp_cache,
        disk_reload=disk_reload,
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
    reload_index: AuthorPaperReloadIndex | None = None,
    dblp_cache: DblpAffiliationCache | None = None,
    disk_reload: bool = True,
) -> dict[str, int]:
    manifest = json.loads((web_data / "conferences.json").read_text(encoding="utf-8"))
    year_set = set(years)
    arxiv_index = build_arxiv_authors_index(arxiv_path)
    if dblp_cache is None and dblp_fetcher is not None:
        dblp_cache = dblp_fetcher.cache

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
            reload_index=reload_index,
            dblp_cache=dblp_cache,
            disk_reload=disk_reload,
            label=conf["id"],
        )
        stats["remaining"] += remaining
        if changed:
            data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stats["conferences"] += 1
            stats["updated"] += changed
            log(f"  done {conf['id']}: updated {changed}/{len(papers)} papers, online_pending={remaining}")

    resolver.cache.save()
    if dblp_fetcher is not None:
        dblp_fetcher.cache.save()
    elif dblp_cache is not None:
        dblp_cache.save()
    if reload_index is not None:
        reload_index.save()
    return stats


def coverage_stats(
    web_data: Path,
    years: list[int],
    arxiv_path: Path,
    *,
    first_author_only: bool = False,
    dblp_cache: DblpAffiliationCache | None = None,
) -> dict[str, int]:
    year_set = set(years)
    total = 0
    complete = 0
    online_pending = 0
    if arxiv_path.is_file():
        for paper in json.loads(arxiv_path.read_text(encoding="utf-8")).get("papers", []):
            total += 1
            if paper_authors_complete(paper, first_author_only=first_author_only):
                complete += 1
            elif paper_needs_online_fetch(
                paper,
                dblp_cache=dblp_cache,
                first_author_only=first_author_only,
            ):
                online_pending += 1
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
            elif paper_needs_online_fetch(
                paper,
                dblp_cache=dblp_cache,
                first_author_only=first_author_only,
            ):
                online_pending += 1
    return {
        "total": total,
        "complete": complete,
        "remaining": total - complete,
        "online_pending": online_pending,
    }


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
        help="skip online fetch when manifest is fresh and online_pending is 0 (still reloads caches into JSON)",
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
    parser.add_argument(
        "--skip-arxiv",
        action="store_true",
        help="deprecated no-op; arXiv is skipped by default (use --with-arxiv to opt in)",
    )
    parser.add_argument(
        "--with-arxiv",
        action="store_true",
        help="also enrich website/data/arxiv-recent.json (off by default; country analytics uses dblp only)",
    )
    parser.add_argument("--skip-conferences", action="store_true", help="only enrich arxiv-recent.json")
    parser.add_argument(
        "--first-author-only",
        action="store_true",
        help="only fetch/resolve first-author affiliations (enough for country analytics)",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="do not hydrate papers from disk caches before online fetch",
    )
    parser.add_argument(
        "--max-online-authors",
        type=int,
        default=None,
        help="cap new dblp person-page lookups this run (CI uses this so jobs finish and persist cache)",
    )
    parser.add_argument("--limit", type=int, default=None, help="max papers per dataset (testing)")
    args = parser.parse_args()
    # Country analytics only needs dblp conference papers; arXiv is opt-in.
    args.skip_arxiv = not args.with_arxiv

    hub = load_hub(args.hub)
    years = parse_years(args.years, hub.pick_years or [2023, 2024, 2025, 2026])
    policy = load_author_country_policy(hub.hub_dir)
    cache_path = hub.root / "data" / f"author-country-cache-{hub.id}.json"
    cache = AuthorCountryCache(cache_path)
    openalex_offline = args.offline or not args.openalex
    resolver = AuthorCountryResolver(cache=cache, policy=policy, offline=openalex_offline)
    dblp_cache_path = hub.root / "data" / f"dblp-affiliation-cache-{hub.id}.json"
    dblp_cache = DblpAffiliationCache(dblp_cache_path)
    dblp_fetcher = None
    if not args.offline and not args.skip_dblp_fetch:
        dblp_fetcher = DblpAffiliationFetcher(
            cache=dblp_cache,
            offline=False,
            max_lookups=args.max_online_authors,
        )
    arxiv_path = hub.site_json_path("arxiv-recent.json")
    reload_path = hub.root / "data" / f"author-paper-reload-{hub.id}.json"
    disk_reload = not args.no_reload
    reload_index = AuthorPaperReloadIndex(reload_path) if disk_reload else None

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
        dblp_cache=dblp_cache,
    )
    pending_online = before.get("online_pending", before["remaining"])

    # When online work is done and manifest is fresh, still hydrate website JSON
    # from disk caches, but disable the network fetcher.
    reload_only = (
        pending_online == 0
        and not args.force
        and args.if_stale_hours is not None
        and is_fresh(
            load_json(manifest_path),
            fingerprint=run_fp,
            max_age_hours=args.if_stale_hours,
            extra_keys={"years": years},
        )
    )
    if reload_only:
        log(
            f"Author online-complete for {hub.id} "
            f"(complete={before['complete']}/{before['total']}, online_pending=0); "
            f"reload-only pass (no dblp HTTP)"
        )
        dblp_fetcher = None

    log(
        f"Enriching author metadata for {hub.id} years={years} "
        f"offline={args.offline} dblp_fetch={dblp_fetcher is not None} "
        f"first_author_only={args.first_author_only} reload={disk_reload} "
        f"max_online={args.max_online_authors if args.max_online_authors is not None else 'unlimited'} "
        f"(complete {before['complete']}/{before['total']}, online_pending {pending_online})"
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
            reload_index=reload_index,
            dblp_cache=dblp_cache,
            disk_reload=disk_reload,
        )
        log(f"  arxiv-recent.json: updated {arxiv_changed}/{arxiv_total}, online_pending={arxiv_remaining}")

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
            reload_index=reload_index,
            dblp_cache=dblp_cache,
            disk_reload=disk_reload,
        )
        log(
            f"  conferences: updated {conf_stats['updated']} papers in "
            f"{conf_stats['conferences']} files, online_pending={conf_stats['remaining']}"
        )

    if dblp_fetcher is not None:
        log(
            f"  dblp online lookups this run: {dblp_fetcher.online_lookups}"
            + (
                f" (budget cap {args.max_online_authors}, remaining deferred to next run)"
                if dblp_fetcher.budget_exhausted
                else ""
            )
        )

    after = coverage_stats(
        hub.web_data,
        years,
        arxiv_path if not args.skip_arxiv else Path("/dev/null"),
        first_author_only=args.first_author_only,
        dblp_cache=dblp_cache,
    )
    rate = (after["complete"] / after["total"]) if after["total"] else 1.0
    log(
        f"Affiliation coverage: {after['complete']}/{after['total']} ({rate * 100:.1f}%), "
        f"online_pending={after.get('online_pending', '?')}"
    )

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
    log(f"dblp affiliation cache: {dblp_cache_path}")
    if reload_index is not None:
        reload_index.save()
        log(f"reload index: {reload_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
