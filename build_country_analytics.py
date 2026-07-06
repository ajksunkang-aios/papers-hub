#!/usr/bin/env python3
"""Build country-level analytics JSON for the standalone analytics page."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.author_country import (
    AuthorCountryCache,
    AuthorCountryResolver,
    FirstAuthorCountry,
    country_label,
    load_author_country_policy,
)
from core.hub_config import Hub, add_hub_argument, load_hub
from core.picks_scoring import AreaPickScoring

ROOT = Path(__file__).resolve().parent
TOP_PAPERS_PER_COUNTRY = 8
PROGRESS_EVERY = 40
CACHE_SAVE_EVERY = 50


def conference_years(web_data: Path) -> list[int]:
    manifest_path = web_data / "conferences.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    years = {
        int(conf["year"])
        for conf in manifest.get("conferences") or []
        if conf.get("year") is not None
    }
    return sorted(years)


def parse_years(raw: str | None, default: list[int]) -> list[int]:
    if not raw or raw.strip().lower() in {"all", "*"}:
        return list(default)
    years = sorted({int(p.strip()) for p in raw.split(",") if p.strip()})
    return years or list(default)


def parse_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).year
    except ValueError:
        m = re.search(r"(20\d{2})", str(value))
        return int(m.group(1)) if m else None


def load_dblp_papers(web_data: Path, years: set[int]) -> list[dict[str, Any]]:
    manifest = json.loads((web_data / "conferences.json").read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for conf in manifest.get("conferences", []):
        year = conf.get("year")
        if year not in years:
            continue
        data_path = web_data / f"{conf['id']}.json"
        if not data_path.is_file():
            continue
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        meta = payload.get("meta") or {}
        for paper in payload.get("papers") or []:
            out.append(
                {
                    "source": "dblp",
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors") or [],
                    "year": paper.get("year") or year,
                    "venue": paper.get("venue") or meta.get("short_name") or conf.get("short_name"),
                    "conference_id": conf.get("id"),
                    "ee_links": paper.get("ee_links") or [],
                    "dblp_key": paper.get("dblp_key"),
                    "dblp_url": paper.get("dblp_url"),
                    "authors_structured": paper.get("authors_structured") or [],
                    "abstract": paper.get("abstract") or "",
                }
            )
    return out


def scoring_text(paper: dict[str, Any]) -> str:
    parts = [
        paper.get("title", ""),
        paper.get("abstract", ""),
        " ".join(paper.get("authors") or []),
        paper.get("venue") or "",
        paper.get("source") or "",
    ]
    return " ".join(p for p in parts if p)


def build_analytics(
    hub: Hub,
    *,
    years: list[int],
    offline: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    policy = load_author_country_policy(hub.hub_dir)
    cache_path = hub.root / "data" / f"author-country-cache-{hub.id}.json"
    cache = AuthorCountryCache(cache_path)
    resolver = AuthorCountryResolver(cache=cache, policy=policy, offline=offline)
    labels = policy.get("country_labels", {})

    categories = hub.category_rows
    category_labels = {c["id"]: c["label"] for c in categories}
    scoring = AreaPickScoring(categories=categories, min_score=0)
    year_set = set(years)

    papers = load_dblp_papers(hub.web_data, year_set)

    country_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "dblp": 0,
            "areas": defaultdict(int),
            "by_year": defaultdict(int),
            "top_papers": [],
        }
    )
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resolved = 0
    enriched_papers: list[dict[str, Any]] = []

    for idx, paper in enumerate(papers, start=1):
        rows = resolver.resolve_paper_authors(
            title=paper["title"],
            authors=paper.get("authors"),
            authors_structured=paper.get("authors_structured"),
            ee_links=paper.get("ee_links"),
            dblp_key=paper.get("dblp_key"),
            arxiv_id=paper.get("arxiv_id"),
            force=force,
        )
        first_row = rows[0] if rows else {
            "name": (paper.get("authors") or [""])[0],
            "affiliations": paper.get("affiliations") or [],
            "country_code": "XX",
            "country_label": country_label("XX", labels),
            "source": "unknown",
            "confidence": "unknown",
        }
        first_author = FirstAuthorCountry(
            name=first_row.get("name") or "",
            country_code=(first_row.get("country_code") or "XX").upper(),
            country_label=first_row.get("country_label") or country_label(first_row.get("country_code", "XX"), labels),
            affiliations=first_row.get("affiliations") or [],
            source=first_row.get("source") or "unknown",
            confidence=first_row.get("confidence") or "unknown",
        )
        if first_author.country_code != "XX":
            resolved += 1

        match = scoring.best_match(scoring_text(paper))
        area_id = match[0] if match else "uncategorized"
        area_label = match[1] if match else "Uncategorized"
        area_score = match[2] if match else 0

        code = first_author.country_code
        stats = country_stats[code]
        stats["total"] += 1
        stats["by_year"][str(paper.get("year") or "unknown")] += 1
        stats["areas"][area_id] += 1
        matrix[code][area_id] += 1
        stats["dblp"] += 1

        enriched = {
            **paper,
            "authors_structured": rows,
            "first_author": first_author.to_dict(),
            "area_id": area_id,
            "area_label": area_label,
            "area_score": area_score,
        }
        enriched_papers.append(enriched)
        stats["top_papers"].append(enriched)

        if idx % PROGRESS_EVERY == 0:
            print(f"  processed {idx}/{len(papers)} papers", flush=True)
        if idx % CACHE_SAVE_EVERY == 0:
            cache.save()

    cache.save()

    countries_out: list[dict[str, Any]] = []
    for code, stats in country_stats.items():
        top = sorted(
            stats["top_papers"],
            key=lambda p: (
                int(p.get("area_score") or 0),
                int(p.get("year") or 0),
            ),
            reverse=True,
        )[:TOP_PAPERS_PER_COUNTRY]
        countries_out.append(
            {
                "code": code,
                "label": first_author_country_label(code, policy),
                "total": stats["total"],
                "dblp": stats["dblp"],
                "areas": dict(stats["areas"]),
                "by_year": dict(sorted(stats["by_year"].items())),
                "top_papers": [
                    {
                        "title": p["title"],
                        "authors": p.get("authors") or [],
                        "source": p["source"],
                        "year": p.get("year"),
                        "area_id": p.get("area_id"),
                        "area_label": p.get("area_label"),
                        "area_score": p.get("area_score"),
                        "first_author": p.get("first_author"),
                        "venue": p.get("venue"),
                        "dblp_url": p.get("dblp_url"),
                        "conference_id": p.get("conference_id"),
                    }
                    for p in top
                ],
            }
        )

    countries_out.sort(key=lambda c: (-c["total"], c["label"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hub_id": hub.id,
        "years": years,
        "period_label": format_period(years),
        "data_source": "dblp",
        "coverage": {
            "total_papers": len(papers),
            "resolved": resolved,
            "unknown": country_stats.get("XX", {}).get("total", 0),
            "resolution_rate": round(resolved / len(papers), 4) if papers else 0.0,
        },
        "category_labels": category_labels,
        "region_groups": policy.get("region_groups", {}),
        "country_labels": policy.get("country_labels", {}),
        "countries": countries_out,
        "matrix": {code: dict(cols) for code, cols in matrix.items()},
        "sources": {
            "dblp": len(papers),
        },
    }


def first_author_country_label(code: str, policy: dict[str, Any]) -> str:
    labels = policy.get("country_labels", {})
    return labels.get(code, code if code != "XX" else "Unknown")


def format_period(years: list[int]) -> str:
    years = sorted(set(years))
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default="all",
        help="Comma-separated years, or 'all' for every year in conferences.json (default: all)",
    )
    parser.add_argument(
        "--openalex",
        action="store_true",
        help="Enable OpenAlex fallback for country resolution (default: dblp affiliations + keyword rules only)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip OpenAlex network calls (default; kept for compatibility)",
    )
    parser.add_argument("--force", action="store_true", help="Ignore cache hits and re-fetch")
    args = parser.parse_args()

    hub = load_hub(args.hub)
    all_years = conference_years(hub.web_data) or list(hub.pick_years)
    years = parse_years(args.years, all_years)
    use_openalex = args.openalex and not args.offline
    print(
        f"Building country analytics for {hub.id} years={years[0]}-{years[-1]} "
        f"({len(years)} years) source=dblp openalex={use_openalex}"
    )

    payload = build_analytics(hub, years=years, offline=not use_openalex, force=args.force)
    out_path = hub.web_data / "country-analytics.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cov = payload["coverage"]
    print(
        f"Wrote {out_path}  papers={cov['total_papers']} resolved={cov['resolved']} "
        f"({cov['resolution_rate'] * 100:.1f}%) countries={len(payload['countries'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
