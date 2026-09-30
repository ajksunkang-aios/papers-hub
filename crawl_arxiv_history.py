#!/usr/bin/env python3
"""
Crawl historical arXiv papers for a custom topic.

Unlike crawl_arxiv_recent.py (which pulls the latest ~200 per category per
day), this walks the arXiv Query API backwards in time to back-fill a
topic's full history — useful for custom topics (e.g. "agent memory")
that should surface papers beyond the recent window.

Usage:
  python3 crawl_arxiv_history.py --hub os-kernel --topic agent-memory
  python3 crawl_arxiv_history.py --hub os-kernel --topic agent-memory --max-per-query 1000

Output: data/arxiv-history/<topic>.json  (same per-paper shape as
arxiv-recent.json, so build_top_monthly.load_arxiv_candidates can ingest
it unchanged.)

arXiv Query API notes:
  - totalResults for a topic is usually < 1000 (agent-memory ≈ 508),
    well within the API's practical depth (start ≤ ~5000).
  - rate limit: wait ≥ 3s between requests (arXiv asks for no more than
    one request every 3 seconds).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
USER_AGENT = "papers-hub/1.0 (research; contact: ajksunkang@gmail.com)"

# arXiv categories most likely to host agent/systems-flavored topics.
DEFAULT_CATEGORIES = ("cs.AI", "cs.CL", "cs.MA", "cs.RO", "cs.LG", "cs.OS")

REQUEST_MIN_INTERVAL = 3.0  # seconds; arXiv asks for ≥ 3s between requests
_last_request_ts: float = 0.0


def throttle() -> None:
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < REQUEST_MIN_INTERVAL:
        time.sleep(REQUEST_MIN_INTERVAL - elapsed)
    _last_request_ts = time.monotonic()


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def parse_entry(entry: ET.Element) -> dict | None:
    """Parse one <entry> into the arxiv-recent.json per-paper shape."""
    id_url = _text(entry.find("atom:id", ATOM_NS))
    # id looks like http://arxiv.org/abs/2606.03895v1
    arxiv_id = id_url.rsplit("/", 1)[-1] if id_url else ""
    if not arxiv_id:
        return None
    title = _text(entry.find("atom:title", ATOM_NS))
    summary = _text(entry.find("atom:summary", ATOM_NS))
    published = _text(entry.find("atom:published", ATOM_NS))
    updated = _text(entry.find("atom:updated", ATOM_NS))

    authors: list[str] = []
    for a in entry.findall("atom:author", ATOM_NS):
        name = _text(a.find("atom:name", ATOM_NS))
        if name:
            authors.append(name)

    cats = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS) if c.get("term")]
    primary_cat_el = entry.find("arxiv:primary_category", ATOM_NS)
    primary_category = primary_cat_el.get("term", "") if primary_cat_el is not None else (cats[0] if cats else "")

    abs_url = id_url
    pdf_url = ""
    for link in entry.findall("atom:link", ATOM_NS):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": summary,
        "published": published,
        "updated": updated,
        "categories": cats,
        "primary_category": primary_category,
        "source_feed": "history",
        "abs_url": abs_url,
        "pdf_url": pdf_url,
        "relevance_score": "",
        "relevance_tags": [],
        "authors_structured": [{"name": n, "affiliations": [], "country_code": "XX",
                                "country_label": "Unknown", "source": "unknown", "confidence": "unknown"}
                               for n in authors],
        "first_author_affiliations": [],
    }


def fetch_page(session: requests.Session, search_query: str, start: int, max_results: int) -> tuple[list[dict], int]:
    """Fetch one page; return (papers, total_results)."""
    for attempt in range(5):
        throttle()
        params = {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": start,
            "max_results": max_results,
        }
        try:
            resp = session.get(ARXIV_API, params=params, timeout=90)
        except requests.RequestException as e:
            wait = min(120, 6 * (2 ** attempt)) + random.uniform(0, 3)
            print(f"  network error: {e}; waiting {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (400, 409):
            print(f"  arXiv rejected query ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return [], 0
        if resp.status_code == 429:
            wait = 60 + random.uniform(0, 10)
            print(f"  rate limited (429); waiting {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            print(f"  unexpected status {resp.status_code}", file=sys.stderr)
            time.sleep(10)
            continue
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            print(f"  parse error: {e}", file=sys.stderr)
            time.sleep(10)
            continue
        total = 0
        tr = root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
        if tr is not None and tr.text:
            total = int(tr.text)
        entries = root.findall("atom:entry", ATOM_NS)
        papers = [p for p in (parse_entry(e) for e in entries) if p]
        return papers, total
    return [], 0


def crawl_topic(topic_label: str, keywords: list[str], categories: list[str], max_per_query: int) -> list[dict]:
    """Crawl all matching papers for a topic.

    Strategy: run one keyword-only query per keyword (arXiv's `all:` search
    covers every category), then optionally one per category for the *primary*
    keyword only. This avoids the keyword×category cross-product blowup
    (15 keywords × 7 categories = 105 slow queries) while still surfacing
    papers that mention the keyword anywhere. Dedup by arxiv_id.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    seen: dict[str, dict] = {}

    def _phrase(kw: str) -> str:
        kw = kw.strip()
        return f'"{kw}"' if " " in kw else kw

    # Use only the top-weighted keywords for queries: arXiv `all:` search is
    # broad, so a handful of high-weight phrases already surface the bulk of
    # relevant papers without the keyword×category cross-product blowup.
    # Long tail keywords (weight <= 6) add noise and queries; skip them here.
    core_keywords = keywords[:6]
    queries: list[str] = [f"all:{_phrase(kw)}" for kw in core_keywords]
    print(f"  {len(queries)} queries to run (3s throttle each ≈ {len(queries)*3}s minimum)", flush=True)

    for q in queries:
        probe, total = fetch_page(session, q, 0, 1)
        print(f"  query {q!r}: total={total}", flush=True)
        if total == 0:
            continue
        start = 0
        fetched = 0
        cap = min(total, max_per_query)
        while fetched < cap:
            batch_size = min(200, cap - fetched)
            papers, _ = fetch_page(session, q, start, batch_size)
            if not papers:
                break
            for p in papers:
                seen[p["arxiv_id"]] = p
            fetched += len(papers)
            start += batch_size
            print(f"    fetched {fetched}/{cap} (cumulative unique={len(seen)})", flush=True)

    return list(seen.values())


def load_topic_config(hub_dir: Path, topic_id: str) -> tuple[str, list[str]]:
    cats = json.loads((hub_dir / "categories.json").read_text(encoding="utf-8"))
    for t in cats.get("custom_topics", []):
        if t["id"] == topic_id:
            # keywords may be [word, weight] pairs or plain strings; keep
            # them weight-sorted (categories.json lists them high→low) so the
            # crawler uses the most discriminative phrases first.
            kws: list[str] = []
            for k in t.get("keywords", []):
                if isinstance(k, list):
                    kws.append(k[0])
                elif isinstance(k, str):
                    kws.append(k)
            return t["label"], kws
    raise SystemExit(f"topic {topic_id!r} not found in custom_topics")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl historical arXiv papers for a custom topic.")
    parser.add_argument("--hub", default="os-kernel")
    parser.add_argument("--topic", required=True, help="custom topic id (e.g. agent-memory)")
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES),
                        help="comma-separated arXiv categories to scan")
    parser.add_argument("--max-per-query", type=int, default=1000,
                        help="max papers per query (default 1000)")
    parser.add_argument("--out", default=None, help="output path (default data/arxiv-history/<topic>.json)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    hub_dir = root / "hubs" / args.hub
    if not hub_dir.is_dir():
        raise SystemExit(f"hub dir not found: {hub_dir}")

    topic_label, keywords = load_topic_config(hub_dir, args.topic)
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    print(f"=== crawl_arxiv_history: topic={args.topic!r} label={topic_label!r} ===")
    print(f"  keywords: {keywords}")
    print(f"  categories: {categories}")

    papers = crawl_topic(topic_label, keywords, categories, args.max_per_query)
    print(f"\n=== total unique papers: {len(papers)} ===")

    out_dir = root / "data" / "arxiv-history"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / f"{args.topic}.json"
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "hub_id": args.hub,
        "topic_id": args.topic,
        "topic_label": topic_label,
        "keywords": keywords,
        "categories": categories,
        "count": len(papers),
        "papers": papers,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(papers)} papers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
