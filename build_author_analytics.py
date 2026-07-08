#!/usr/bin/env python3
"""Build top-author analytics JSON for the Author Analysis page."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.author_country import load_author_country_policy, resolve_author_local
from core.author_profiles import normalize_author_key, normalize_author_name
from core.dblp_affiliations import DblpAffiliationCache
from core.dblp_person_index import load_person_index
from core.analytics_scoring import analytics_area_scoring, analytics_scoring_text
from core.hub_config import add_hub_argument, load_hub
from core.topic_tags import TOPIC_BY_ID, extract_paper_topic_hits

from build_country_analytics import conference_years, format_period, load_dblp_papers, parse_years

TOP_AUTHORS = 50
TOP_AREAS_PER_AUTHOR = 3
TOP_TAGS_PER_AUTHOR = 6
TOP_TOPIC_TAGS_PER_AUTHOR = 8
TOP_PAPERS_PER_AUTHOR = 8


def pick_display_name(name_counts: Counter[str]) -> str:
    if not name_counts:
        return ""
    return max(name_counts.items(), key=lambda item: (item[1], len(item[0])))[0]


def merge_structured_profile(
    profiles: dict[str, dict[str, Any]],
    name: str,
    structured_rows: list[dict[str, Any]],
) -> None:
    key = normalize_author_key(name)
    if not key:
        return
    row = next(
        (r for r in structured_rows if normalize_author_key(r.get("name", "")) == key),
        None,
    )
    if row is None:
        return
    profile = profiles.setdefault(
        key,
        {
            "affiliations": Counter(),
            "countries": Counter(),
        },
    )
    for aff in row.get("affiliations") or []:
        text = str(aff).strip()
        if text and text != "Unknown affiliation":
            profile["affiliations"][text] += 1
    code = (row.get("country_code") or "").upper()
    if code and code != "XX":
        label = row.get("country_label") or code
        profile["countries"][f"{code}|{label}"] += 1


def finalize_profile(profiles: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    raw = profiles.get(key) or {}
    affs = raw.get("affiliations") or Counter()
    countries = raw.get("countries") or Counter()
    top_aff = affs.most_common(3)
    top_country = countries.most_common(1)
    out: dict[str, Any] = {}
    if top_aff:
        out["affiliations"] = [text for text, _count in top_aff]
        out["affiliation"] = top_aff[0][0]
    if top_country:
        code_label = top_country[0][0]
        code, _, label = code_label.partition("|")
        out["country_code"] = code
        out["country_label"] = label or code
    return out


def enrich_profile_from_caches(
    key: str,
    display_name: str,
    profile: dict[str, Any],
    *,
    dblp_cache: DblpAffiliationCache,
    person_index,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Fill affiliation/country from disk caches when paper JSON lacks enrich data."""
    out = dict(profile)
    affs: list[str] = list(out.get("affiliations") or [])
    if not affs and out.get("affiliation"):
        affs = [out["affiliation"]]

    if not affs:
        cached = dblp_cache.get(key)
        if cached:
            affs = cached
        elif person_index is not None and person_index.loaded:
            hit = person_index.lookup(display_name)
            if hit is not None:
                affs = hit[0] or []

    if not affs:
        return out

    resolved = resolve_author_local(display_name, affs, policy=policy)
    out["affiliations"] = affs[:3]
    out["affiliation"] = affs[0]
    if resolved.country_code and resolved.country_code != "XX":
        out["country_code"] = resolved.country_code
        out["country_label"] = resolved.country_label
    elif out.get("country_code"):
        pass
    return out


def soft_area_matches(scoring, paper: dict[str, Any], *, limit: int = 3) -> list[tuple[str, str, int]]:
    """Best-effort area hints when primary match is uncategorized."""
    text = analytics_scoring_text(paper)
    scored: list[tuple[int, str, str]] = []
    for cat in scoring.categories:
        score, _tags = scoring.score_category(text, cat)
        if score > 0:
            scored.append((score, cat["id"], cat["label"]))
    scored.sort(key=lambda item: (-item[0], item[2]))
    return [(area_id, label, score) for score, area_id, label in scored[:limit]]


def build_analytics(hub, *, years: list[int]) -> dict[str, Any]:
    categories = hub.category_rows
    category_labels = {c["id"]: c["label"] for c in categories}
    category_labels["uncategorized"] = "Uncategorized"
    scoring = analytics_area_scoring(hub)
    year_set = set(years)
    papers = load_dblp_papers(hub.web_data, year_set)
    policy = load_author_country_policy(hub.hub_dir)
    dblp_cache = DblpAffiliationCache(hub.root / "data" / f"dblp-affiliation-cache-{hub.id}.json")
    person_index = load_person_index(hub.root)

    author_stats: dict[str, dict[str, Any]] = {}
    structured_profiles: dict[str, dict[str, Any]] = {}
    unique_author_keys: set[str] = set()
    uncategorized_papers = 0
    global_uncat_topics: Counter[str] = Counter()
    area_paper_counts: Counter[str] = Counter()

    def ensure_author(key: str) -> dict[str, Any]:
        return author_stats.setdefault(
            key,
            {
                "name_counts": Counter(),
                "paper_count": 0,
                "areas": Counter(),
                "tags": Counter(),
                "topic_tags": Counter(),
                "uncategorized_topics": Counter(),
                "secondary_areas": Counter(),
                "by_year": Counter(),
                "venues": Counter(),
                "papers": [],
            },
        )

    for paper in papers:
        match = scoring.best_match(analytics_scoring_text(paper))
        if match:
            area_id, area_label, area_score, matched_tags = match
            if not area_id or area_score <= 0:
                area_id, area_label, area_score, matched_tags = (
                    "uncategorized",
                    "Uncategorized",
                    0,
                    [],
                )
        else:
            area_id, area_label, area_score, matched_tags = "uncategorized", "Uncategorized", 0, []

        topic_hits: list = []
        soft_areas: list[tuple[str, str, int]] = []
        if area_id == "uncategorized":
            uncategorized_papers += 1
            topic_hits = extract_paper_topic_hits(
                title=paper.get("title", ""),
                abstract=paper.get("abstract", ""),
                venue=paper.get("venue") or "",
            )
            soft_areas = soft_area_matches(scoring, paper)
            for spec in topic_hits:
                global_uncat_topics[spec.topic_id] += 1

        area_paper_counts[area_id] += 1

        authors = paper.get("authors") or []
        structured = paper.get("authors_structured") or []
        for name in authors:
            key = normalize_author_key(name)
            if not key:
                continue
            unique_author_keys.add(key)
            stats = ensure_author(key)
            stats["name_counts"][normalize_author_name(name) or name.strip()] += 1
            stats["paper_count"] += 1
            stats["areas"][area_id] += 1
            for tag in matched_tags:
                stats["tags"][tag] += 1
            for spec in topic_hits:
                stats["topic_tags"][spec.label] += 1
                if area_id == "uncategorized":
                    stats["uncategorized_topics"][spec.label] += 1
            for soft_id, _soft_label, _soft_score in soft_areas:
                stats["secondary_areas"][soft_id] += 1
            year_key = str(paper.get("year") or "unknown")
            stats["by_year"][year_key] += 1
            venue = paper.get("venue") or ""
            if venue:
                stats["venues"][venue] += 1
            merge_structured_profile(structured_profiles, name, structured)
            stats["papers"].append(
                {
                    "title": paper.get("title", ""),
                    "year": paper.get("year"),
                    "venue": venue,
                    "area_id": area_id,
                    "area_label": area_label,
                    "area_score": area_score,
                    "matched_tags": matched_tags,
                    "topic_tags": [spec.label for spec in topic_hits],
                    "topic_ids": [spec.topic_id for spec in topic_hits],
                    "soft_areas": [
                        {"id": soft_id, "label": soft_label, "score": soft_score}
                        for soft_id, soft_label, soft_score in soft_areas
                    ],
                    "dblp_url": paper.get("dblp_url"),
                    "conference_id": paper.get("conference_id"),
                }
            )

    ranked = sorted(
        author_stats.items(),
        key=lambda item: (-item[1]["paper_count"], pick_display_name(item[1]["name_counts"]).lower()),
    )[:TOP_AUTHORS]

    authors_out: list[dict[str, Any]] = []
    for rank, (key, stats) in enumerate(ranked, start=1):
        primary_areas = [
            {
                "id": area_id,
                "label": category_labels.get(area_id, area_id),
                "count": count,
            }
            for area_id, count in stats["areas"].most_common(TOP_AREAS_PER_AUTHOR)
        ]
        tech_tags = [
            {"tag": tag, "count": count}
            for tag, count in stats["tags"].most_common(TOP_TAGS_PER_AUTHOR)
        ]
        topic_tag_rows = [
            {"tag": tag, "count": count}
            for tag, count in stats["topic_tags"].most_common(TOP_TOPIC_TAGS_PER_AUTHOR)
        ]
        uncategorized_count = stats["areas"].get("uncategorized", 0)
        uncategorized_topics = [
            {"tag": tag, "count": count}
            for tag, count in stats["uncategorized_topics"].most_common(TOP_TOPIC_TAGS_PER_AUTHOR)
        ]
        secondary_areas = [
            {
                "id": area_id,
                "label": category_labels.get(area_id, area_id),
                "count": count,
            }
            for area_id, count in stats["secondary_areas"].most_common(TOP_AREAS_PER_AUTHOR)
        ]
        display_tags = tech_tags if tech_tags else topic_tag_rows
        top_papers = sorted(
            stats["papers"],
            key=lambda p: (int(p.get("area_score") or 0), int(p.get("year") or 0)),
            reverse=True,
        )[:TOP_PAPERS_PER_AUTHOR]
        profile = finalize_profile(structured_profiles, key)
        display_name = pick_display_name(stats["name_counts"])
        profile = enrich_profile_from_caches(
            key,
            display_name,
            profile,
            dblp_cache=dblp_cache,
            person_index=person_index,
            policy=policy,
        )
        authors_out.append(
            {
                "rank": rank,
                "key": key,
                "name": display_name,
                "paper_count": stats["paper_count"],
                "primary_areas": primary_areas,
                "tech_tags": tech_tags,
                "topic_tags": topic_tag_rows,
                "display_tags": display_tags,
                "uncategorized_count": uncategorized_count,
                "uncategorized_topics": uncategorized_topics,
                "secondary_areas": secondary_areas,
                "by_year": dict(sorted(stats["by_year"].items())),
                "venues": dict(stats["venues"].most_common(8)),
                "top_papers": top_papers,
                **profile,
            }
        )

    authors_with_affiliation = sum(
        1 for key in unique_author_keys if (structured_profiles.get(key, {}).get("affiliations"))
    )
    top_with_affiliation = sum(1 for author in authors_out if author.get("affiliation"))
    top_with_country = sum(1 for author in authors_out if author.get("country_code"))

    research_areas = [
        {
            "kind": "area",
            "id": cat["id"],
            "label": cat["label"],
            "count": area_paper_counts.get(cat["id"], 0),
        }
        for cat in categories
        if area_paper_counts.get(cat["id"], 0) > 0
    ]
    research_areas.sort(key=lambda row: (-row["count"], row["label"]))

    uncategorized_topics = [
        {
            "kind": "topic",
            "id": topic_id,
            "label": TOPIC_BY_ID[topic_id].label,
            "count": count,
            "parent_area_id": TOPIC_BY_ID[topic_id].parent_area_id,
            "parent_area_label": (
                category_labels.get(TOPIC_BY_ID[topic_id].parent_area_id)
                if TOPIC_BY_ID[topic_id].parent_area_id
                else None
            ),
        }
        for topic_id, count in global_uncat_topics.most_common()
        if topic_id in TOPIC_BY_ID
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hub_id": hub.id,
        "years": years,
        "period_label": format_period(years),
        "data_source": "dblp",
        "coverage": {
            "total_papers": len(papers),
            "unique_authors": len(unique_author_keys),
            "authors_with_affiliation": authors_with_affiliation,
            "top_with_affiliation": top_with_affiliation,
            "top_with_country": top_with_country,
            "top_n": TOP_AUTHORS,
            "uncategorized_papers": uncategorized_papers,
            "uncategorized_rate": round(uncategorized_papers / len(papers), 4) if papers else 0.0,
        },
        "research_breakdown": {
            "areas": research_areas,
            "uncategorized_topics": uncategorized_topics,
        },
        "category_labels": category_labels,
        "authors": authors_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    parser.add_argument(
        "--years",
        default="all",
        help="Comma-separated years, or 'all' for every year in conferences.json",
    )
    args = parser.parse_args()

    hub = load_hub(args.hub)
    all_years = conference_years(hub.web_data) or list(hub.pick_years)
    years = parse_years(args.years, all_years)
    print(f"Building author analytics for {hub.id} years={years[0]}-{years[-1]} ({len(years)} years)")

    payload = build_analytics(hub, years=years)
    out_path = hub.web_data / "author-analytics.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cov = payload["coverage"]
    top = payload["authors"][0] if payload["authors"] else None
    print(
        f"Wrote {out_path}  papers={cov['total_papers']} "
        f"unique_authors={cov['unique_authors']} top50={len(payload['authors'])}"
    )
    if top:
        print(f"  #1 {top['name']} ({top['paper_count']} papers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
