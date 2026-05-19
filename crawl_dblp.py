#!/usr/bin/env python3
"""
Crawl papers for a dblp conference proceedings page (default: FAST 2026).

Usage:
  python crawl_dblp.py
  python crawl_dblp.py --year 2025 --output fast2025.json
  python crawl_dblp.py --venue fast --year 2026 --method api

dblp etiquette: set a descriptive User-Agent and avoid hammering the site.
See https://dblp.org/faq/13555478
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

DBLP_BASE = "https://dblp.org"
DEFAULT_USER_AGENT = (
    "top-conference-crawler/1.0 "
    "(+https://github.com/example/top-conference; research use)"
)


@dataclass
class Paper:
    title: str
    authors: list[str] = field(default_factory=list)
    pages: str | None = None
    year: str | None = None
    venue: str | None = None
    paper_type: str | None = None
    dblp_key: str | None = None
    dblp_url: str | None = None
    ee_links: list[str] = field(default_factory=list)


def proceedings_url(venue: str, year: int, volume_suffix: str = "") -> str:
    venue = venue.lower()
    return f"{DBLP_BASE}/db/conf/{venue}/{venue}{year}{volume_suffix}.html"


def proceedings_urls(venue: str, year: int, volume_suffixes: list[str]) -> list[str]:
    return [proceedings_url(venue, year, suffix) for suffix in volume_suffixes]


def bib_url(venue: str, year: int) -> str:
    venue = venue.lower()
    return f"{DBLP_BASE}/rec/conf/{venue}/{venue}{year}.bib"


def api_url(venue: str, year: int, max_hits: int) -> str:
    venue = venue.lower()
    # Restrict to records under this proceedings key prefix.
    query = f"key:conf/{venue}/{venue}{year}:*"
    return (
        f"{DBLP_BASE}/search/publ/api"
        f"?q={requests.utils.quote(query)}&format=json&h={max_hits}"
    )


def fetch(
    session: requests.Session,
    url: str,
    *,
    delay_s: float,
    retries: int,
) -> str:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(delay_s * attempt)
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            time.sleep(delay_s)
            return resp.text
        except requests.RequestException as exc:
            last_err = exc
    raise RuntimeError(f"Failed to fetch {url}") from last_err


def _text(el: Tag | None) -> str | None:
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _normalize_title(title: str) -> str:
    return title.rstrip(".").strip()


def parse_authors(entry: Tag) -> list[str]:
    authors: list[str] = []
    for author in entry.select('[itemprop="author"]'):
        name = _text(author)
        if name:
            authors.append(name)
    if authors:
        return authors

    # Older markup: author links inside span.authors
    for link in entry.select("span.authors a"):
        name = link.get_text(strip=True)
        if name:
            authors.append(name)
    return authors


def parse_ee_links(entry: Tag) -> list[str]:
    links: list[str] = []
    for a in entry.select("nav.publ a[href]"):
        href = a.get("href", "").strip()
        if href and href not in links:
            links.append(href)
    return links


def parse_entry_li(entry: Tag, *, venue_label: str | None) -> Paper | None:
    title_el = entry.select_one('span.title[itemprop="name"]') or entry.select_one(
        "span.title"
    )
    title = _text(title_el)
    if not title:
        return None

    dblp_key = None
    entry_id = entry.get("id")
    if entry_id:
        dblp_key = entry_id

    dblp_url = None
    if dblp_key:
        dblp_url = f"{DBLP_BASE}/rec/{dblp_key}.html"

    pages_el = entry.select_one("span.pages")
    year_el = entry.select_one('[itemprop="datePublished"]')

    paper_type = None
    classes = entry.get("class", [])
    for cls in classes:
        if cls in {"inproceedings", "article", "proceedings", "book", "incollection"}:
            paper_type = cls
            break

    return Paper(
        title=_normalize_title(title),
        authors=parse_authors(entry),
        pages=_text(pages_el),
        year=_text(year_el),
        venue=venue_label,
        paper_type=paper_type,
        dblp_key=dblp_key,
        dblp_url=dblp_url,
        ee_links=parse_ee_links(entry),
    )


def parse_proceedings_html(html: str, *, venue_label: str | None) -> list[Paper]:
    soup = BeautifulSoup(html, "lxml")
    papers: list[Paper] = []

    for entry in soup.select("ul.publ-list > li.entry"):
        paper = parse_entry_li(entry, venue_label=venue_label)
        if paper:
            papers.append(paper)

    # Some proceedings pages nest lists differently.
    if not papers:
        for entry in soup.select("li.entry.inproceedings, li.entry.article"):
            paper = parse_entry_li(entry, venue_label=venue_label)
            if paper:
                papers.append(paper)

    return papers


def _parse_api_authors(info: str) -> list[str]:
    # Example: "Alice Author, Bob Author: Title."
    if ":" not in info:
        return []
    head = info.split(":", 1)[0]
    if not head.strip():
        return []
    return [a.strip() for a in head.split(" and ") for a in a.split(", ") if a.strip()]


def _parse_api_title(info: str) -> str | None:
    if ":" not in info:
        return None
    rest = info.split(":", 1)[1].strip()
    # Drop trailing venue fragment after the last period before "In FAST ..."
    title = rest.split(" In ", 1)[0].strip()
    if title.endswith("."):
        title = title[:-1]
    return title or None


def crawl_via_html(
    session: requests.Session,
    venue: str,
    year: int,
    *,
    delay_s: float,
    retries: int,
    volume_suffixes: list[str] | None = None,
) -> list[Paper]:
    suffixes = volume_suffixes if volume_suffixes is not None else [""]
    venue_label = f"{venue.upper()} {year}"
    papers: list[Paper] = []
    for suffix in suffixes:
        url = proceedings_url(venue, year, suffix)
        html = fetch(session, url, delay_s=delay_s, retries=retries)
        papers.extend(parse_proceedings_html(html, venue_label=venue_label))
    return papers


def discover_volume_suffixes(
    session: requests.Session,
    venue: str,
    year: int,
    *,
    delay_s: float,
    retries: int,
    max_volumes: int = 8,
) -> list[str]:
    """Pick single-page or multi-volume proceedings (-1, -2, ...)."""
    venue = venue.lower()
    base = proceedings_url(venue, year, "")
    try:
        fetch(session, base, delay_s=delay_s, retries=retries)
        return [""]
    except RuntimeError:
        pass

    suffixes: list[str] = []
    for i in range(1, max_volumes + 1):
        suffix = f"-{i}"
        url = proceedings_url(venue, year, suffix)
        try:
            fetch(session, url, delay_s=delay_s, retries=retries)
            suffixes.append(suffix)
        except RuntimeError:
            break
    return suffixes


def crawl_via_api(
    session: requests.Session,
    venue: str,
    year: int,
    *,
    delay_s: float,
    retries: int,
    max_hits: int,
) -> list[Paper]:
    url = api_url(venue, year, max_hits)
    text = fetch(session, url, delay_s=delay_s, retries=retries)
    data = json.loads(text)
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if isinstance(hits, dict):
        hits = [hits]

    papers: list[Paper] = []
    for hit in hits:
        info = hit.get("info", {})
        if isinstance(info, list):
            info = info[0] if info else {}
        title = info.get("title")
        authors_raw = info.get("authors", {}).get("author", [])
        if isinstance(authors_raw, str):
            authors = [authors_raw]
        elif isinstance(authors_raw, dict):
            authors = [authors_raw.get("text", authors_raw.get("@text", ""))]
        else:
            authors = [
                a.get("text", a) if isinstance(a, dict) else str(a) for a in authors_raw
            ]
        authors = [a for a in authors if a]

        dblp_key = info.get("key")
        dblp_url = info.get("url") or (
            f"{DBLP_BASE}/rec/{dblp_key}.html" if dblp_key else None
        )
        ee = info.get("ee")
        ee_links: list[str] = []
        if isinstance(ee, str):
            ee_links = [ee]
        elif isinstance(ee, list):
            ee_links = [e for e in ee if isinstance(e, str)]

        if not title:
            title = _parse_api_title(info.get("text", ""))
        if not authors and info.get("text"):
            authors = _parse_api_authors(info.get("text", ""))

        if not title:
            continue

        papers.append(
            Paper(
                title=_normalize_title(title),
                authors=authors,
                pages=info.get("pages"),
                year=str(info.get("year") or year),
                venue=info.get("venue") or f"{venue.upper()} {year}",
                paper_type=info.get("type"),
                dblp_key=dblp_key,
                dblp_url=dblp_url,
                ee_links=ee_links,
            )
        )
    return papers


def crawl_via_bib(
    session: requests.Session,
    venue: str,
    year: int,
    *,
    delay_s: float,
    retries: int,
) -> list[Paper]:
    """Parse combined BibTeX export when available."""
    url = bib_url(venue, year)
    try:
        bib = fetch(session, url, delay_s=delay_s, retries=retries)
    except RuntimeError:
        return []

    # Minimal regex-based BibTeX parser (dblp export is well-formed).
    entries = re.split(r"\n@", bib)
    papers: list[Paper] = []
    for raw in entries:
        if not raw.strip():
            continue
        block = raw if raw.startswith("@") else "@" + raw
        title_m = re.search(r"\btitle\s*=\s*\{(.+?)\}\s*,", block, re.S)
        if not title_m:
            continue
        title = title_m.group(1).replace("\n", " ").strip()
        author_m = re.search(r"\bauthor\s*=\s*\{(.+?)\}\s*,", block, re.S)
        authors: list[str] = []
        if author_m:
            authors = [a.strip() for a in author_m.group(1).split(" and ") if a.strip()]
        pages_m = re.search(r"\bpages\s*=\s*\{(.+?)\}\s*,", block)
        year_m = re.search(r"\byear\s*=\s*\{(.+?)\}\s*,", block)
        key_m = re.match(r"@(\w+)\s*\{\s*([^,]+)\s*,", block)
        dblp_key = key_m.group(2).strip() if key_m else None
        ee_links = re.findall(r"\bee\s*=\s*\{(.+?)\}\s*,", block)
        papers.append(
            Paper(
                title=_normalize_title(title),
                authors=authors,
                pages=pages_m.group(1) if pages_m else None,
                year=year_m.group(1) if year_m else str(year),
                venue=f"{venue.upper()} {year}",
                paper_type=key_m.group(1) if key_m else None,
                dblp_key=dblp_key,
                dblp_url=f"{DBLP_BASE}/rec/{dblp_key}.html" if dblp_key else None,
                ee_links=ee_links,
            )
        )
    return papers


def dedupe_papers(papers: Iterable[Paper]) -> list[Paper]:
    seen: set[str] = set()
    out: list[Paper] = []
    for p in papers:
        key = p.dblp_key or p.title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crawl papers from a dblp conference proceedings page."
    )
    parser.add_argument("--venue", default="fast", help="dblp venue slug (default: fast)")
    parser.add_argument("--year", type=int, default=2026, help="proceedings year")
    parser.add_argument(
        "--method",
        choices=("html", "api", "bib", "auto"),
        default="auto",
        help="fetch strategy (default: auto = html then api)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="fast2026_papers.json",
        help="output JSON path",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--retries", type=int, default=2, help="retry count on failure")
    parser.add_argument("--max-hits", type=int, default=1000, help="API page size cap")
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent (dblp recommends a descriptive value)",
    )
    parser.add_argument(
        "--volumes",
        default="",
        help='volume suffixes comma-separated, e.g. "-1,-2" (default: auto-detect)',
    )
    parser.add_argument(
        "--conference-id",
        default="",
        help="optional id stored in output JSON (e.g. fast-2026)",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept": "*/*"})

    papers: list[Paper] = []
    if args.volumes.strip():
        volume_suffixes = [s.strip() for s in args.volumes.split(",") if s.strip() != ""]
        if args.volumes.strip() == '""' or args.volumes.strip() == "none":
            volume_suffixes = [""]
    else:
        volume_suffixes = discover_volume_suffixes(
            session, args.venue, args.year, delay_s=args.delay, retries=args.retries
        )

    source_urls = proceedings_urls(args.venue, args.year, volume_suffixes)
    source_url = source_urls[0] if len(source_urls) == 1 else source_urls

    try:
        if args.method == "html":
            papers = crawl_via_html(
                session,
                args.venue,
                args.year,
                delay_s=args.delay,
                retries=args.retries,
                volume_suffixes=volume_suffixes,
            )
        elif args.method == "api":
            papers = crawl_via_api(
                session,
                args.venue,
                args.year,
                delay_s=args.delay,
                retries=args.retries,
                max_hits=args.max_hits,
            )
        elif args.method == "bib":
            papers = crawl_via_bib(
                session, args.venue, args.year, delay_s=args.delay, retries=args.retries
            )
        else:
            papers = crawl_via_html(
                session,
                args.venue,
                args.year,
                delay_s=args.delay,
                retries=args.retries,
                volume_suffixes=volume_suffixes,
            )
            if not papers:
                papers = crawl_via_api(
                    session,
                    args.venue,
                    args.year,
                    delay_s=args.delay,
                    retries=args.retries,
                    max_hits=args.max_hits,
                )
    except requests.HTTPError as exc:
        print(f"HTTP error for {source_url}: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    papers = dedupe_papers(papers)

    payload = {
        "id": args.conference_id or f"{args.venue}-{args.year}",
        "venue": args.venue,
        "year": args.year,
        "source_url": source_url,
        "source_urls": source_urls,
        "volume_suffixes": volume_suffixes,
        "count": len(papers),
        "papers": [asdict(p) for p in papers],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(papers)} papers to {args.output}")
    if not papers:
        print(
            "No papers found. The proceedings may not be indexed yet on dblp.",
            file=sys.stderr,
        )
    return 0 if papers else 2


if __name__ == "__main__":
    raise SystemExit(main())
