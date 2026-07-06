#!/usr/bin/env python3
"""Local online smoke test for author enrich reload.

1) Seed from dblp affiliation cache (offline hydrate).
2) Pass1 online: enrich a small slice.
3) Strip authors_structured (simulate fresh checkout).
4) Pass2 online: expect restore from disk; no new dblp cache growth for resolved authors.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.author_country import (  # noqa: E402
    AuthorCountryCache,
    AuthorCountryResolver,
    load_author_country_policy,
)
from core.author_profiles import normalize_author_key, paper_authors_complete  # noqa: E402
from core.author_reload import AuthorPaperReloadIndex, paper_needs_online_fetch  # noqa: E402
from core.dblp_affiliations import DblpAffiliationCache, DblpAffiliationFetcher  # noqa: E402
from core.hub_config import load_hub  # noqa: E402
from enrich_author_metadata import enrich_paper_list, reload_paper_from_disk  # noqa: E402

# First 4 asplos-2026 papers are all hit/miss in local dblp cache (no HTTP needed
# for unresolved "none" authors further down the list).
LIMIT = 4
CONF = "asplos-2026"


def papers_slice(papers: list) -> list:
    return papers[:LIMIT]


def strip_authors(papers: list) -> None:
    for paper in papers_slice(papers):
        paper["authors_structured"] = [
            {"name": n, "affiliations": []} for n in (paper.get("authors") or []) if n
        ]
        paper["first_author_affiliations"] = []


def run_pass(label: str, papers: list, *, online: bool) -> dict:
    hub = load_hub("os-kernel")
    policy = load_author_country_policy(hub.hub_dir)
    country_cache = AuthorCountryCache(ROOT / "data" / "author-country-cache-os-kernel.json")
    dblp_cache = DblpAffiliationCache(ROOT / "data" / "dblp-affiliation-cache-os-kernel.json")
    reload_index = AuthorPaperReloadIndex(ROOT / "data" / "author-paper-reload-os-kernel.json")
    resolver = AuthorCountryResolver(cache=country_cache, policy=policy, offline=True)
    fetcher = DblpAffiliationFetcher(cache=dblp_cache, offline=False) if online else None

    before_entries = len(dblp_cache._data.get("entries", {}))
    before_complete = sum(
        1 for p in papers_slice(papers) if paper_authors_complete(p, first_author_only=True)
    )
    before_pending = sum(
        1
        for p in papers_slice(papers)
        if paper_needs_online_fetch(p, dblp_cache=dblp_cache, first_author_only=True)
    )

    t0 = time.monotonic()
    changed, remaining = enrich_paper_list(
        papers,
        resolver=resolver,
        dblp_fetcher=fetcher,
        arxiv_by_title={},
        policy=policy,
        force=False,
        first_author_only=True,
        reload_index=reload_index,
        dblp_cache=dblp_cache,
        disk_reload=True,
        limit=LIMIT,
        label=label,
    )
    elapsed = time.monotonic() - t0

    after_entries = len(dblp_cache._data["entries"])
    after_complete = sum(
        1 for p in papers_slice(papers) if paper_authors_complete(p, first_author_only=True)
    )
    after_pending = sum(
        1
        for p in papers_slice(papers)
        if paper_needs_online_fetch(p, dblp_cache=dblp_cache, first_author_only=True)
    )

    country_cache.save()
    dblp_cache.save()
    reload_index.save()

    sample = None
    for p in papers_slice(papers):
        if paper_authors_complete(p, first_author_only=True):
            rows = p.get("authors_structured") or []
            sample = {
                "author": rows[0].get("name"),
                "aff": (rows[0].get("affiliations") or [None])[0],
                "country": rows[0].get("country_code"),
            }
            break

    return {
        "label": label,
        "online": online,
        "elapsed_sec": round(elapsed, 2),
        "changed": changed,
        "list_remaining": remaining,
        "complete_before": before_complete,
        "complete_after": after_complete,
        "online_pending_before": before_pending,
        "online_pending_after": after_pending,
        "dblp_cache_before": before_entries,
        "dblp_cache_after": after_entries,
        "dblp_cache_delta": after_entries - before_entries,
        "sample_complete": sample,
    }


def seed_from_dblp_cache(papers: list) -> int:
    """Offline-hydrate papers that already have real dblp affiliation cache hits."""
    hub = load_hub("os-kernel")
    policy = load_author_country_policy(hub.hub_dir)
    country_cache = AuthorCountryCache(ROOT / "data" / "author-country-cache-os-kernel.json")
    dblp_cache = DblpAffiliationCache(ROOT / "data" / "dblp-affiliation-cache-os-kernel.json")
    reload_index = AuthorPaperReloadIndex(ROOT / "data" / "author-paper-reload-os-kernel.json")
    resolver = AuthorCountryResolver(cache=country_cache, policy=policy, offline=True)
    n = 0
    for p in papers_slice(papers):
        if reload_paper_from_disk(
            p,
            resolver=resolver,
            dblp_cache=dblp_cache,
            reload_index=reload_index,
            policy=policy,
            first_author_only=True,
        ):
            n += 1
        if paper_authors_complete(p, first_author_only=True):
            reload_index.set_paper(p, first_author_only=True)
    country_cache.save()
    reload_index.save()
    return n


if __name__ == "__main__":
    path = ROOT / "website" / "data" / f"{CONF}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    papers = data["papers"]
    print(f"=== reload smoke: {CONF} first {LIMIT} papers ===", flush=True)

    seeded = seed_from_dblp_cache(papers)
    seeded_complete = sum(
        1 for p in papers_slice(papers) if paper_authors_complete(p, first_author_only=True)
    )
    print(f"seed reload-from-dblp: changed={seeded}, complete_now={seeded_complete}")

    r1 = run_pass("pass1-online", papers, online=True)
    print("PASS1:", json.dumps(r1, indent=2, ensure_ascii=False))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if r1["complete_after"] == 0:
        print("FAIL: pass1 produced 0 complete papers; cannot verify reload")
        dblp = DblpAffiliationCache(ROOT / "data" / "dblp-affiliation-cache-os-kernel.json")
        for p in papers_slice(papers):
            name = (p.get("authors") or [""])[0]
            key = normalize_author_key(name)
            print(f"  {name!r} hit={dblp.get(key)} miss={dblp.is_miss(key)}")
        raise SystemExit(1)

    strip_authors(papers)
    stripped_complete = sum(
        1 for p in papers_slice(papers) if paper_authors_complete(p, first_author_only=True)
    )
    print(f"stripped authors_structured; complete_now={stripped_complete}")

    r2 = run_pass("pass2-reload", papers, online=True)
    print("PASS2:", json.dumps(r2, indent=2, ensure_ascii=False))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(
        f"RESULT: complete pass1={r1['complete_after']} -> pass2={r2['complete_after']}; "
        f"dblp_new_entries pass2={r2['dblp_cache_delta']}; "
        f"time pass1={r1['elapsed_sec']}s pass2={r2['elapsed_sec']}s"
    )
    restored = r2["complete_after"] >= r1["complete_after"] and r2["complete_after"] > 0
    no_new_fetch = r2["dblp_cache_delta"] == 0
    if restored and no_new_fetch:
        print("OK: reload restored real affiliations without new dblp cache entries")
        raise SystemExit(0)
    if restored:
        print("PARTIAL: completeness restored but dblp cache grew")
        raise SystemExit(0)
    print("FAIL: reload did not restore completeness")
    raise SystemExit(1)
