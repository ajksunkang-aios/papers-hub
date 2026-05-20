#!/usr/bin/env python3
"""
Download and stream-parse dblp.xml.gz; extract historical papers for top OS venues.

Usage:
  python3 parse_dblp_xml.py --download
  python3 parse_dblp_xml.py --build-website
  python3 parse_dblp_xml.py --all
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from collections import defaultdict
from lxml import etree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import requests

DBLP_XML_GZ = "https://dblp.org/xml/dblp.xml.gz"
USER_AGENT = "top-conference-xml/1.0 (research)"
ROOT = Path(__file__).resolve().parent
DEFAULT_XML = ROOT / "data" / "dblp.xml.gz"
WEB_DATA = ROOT / "website" / "data"

from core.hub_config import Hub, add_hub_argument, load_hub  # noqa: E402
from core.incremental import file_fingerprint, is_fresh, load_json, save_json, utc_now_iso  # noqa: E402

PROCEEDINGS_KEY = re.compile(r"^conf/[^/]+/\d{4}(-\d+)?$")


@dataclass
class VenueConfig:
    slug: str
    short_name: str
    full_name: str
    skip_title_patterns: list[str] = field(default_factory=list)
    link_priority: list[str] = field(default_factory=list)

    def skip_key(self, year: int, volume: int | None = None) -> list[str]:
        keys = [f"conf/{self.slug}/{year}"]
        if volume is not None:
            keys.append(f"conf/{self.slug}/{year}-{volume}")
        return keys


def load_venues(hub: Hub | None = None) -> dict[str, VenueConfig]:
    raw = hub.venues_raw if hub else json.loads((ROOT / "venues.json").read_text(encoding="utf-8"))
    out: dict[str, VenueConfig] = {}
    for v in raw["venues"]:
        out[v["slug"]] = VenueConfig(
            slug=v["slug"],
            short_name=v["short_name"],
            full_name=v["full_name"],
            skip_title_patterns=v.get("skip_title_patterns", []),
            link_priority=v.get("link_priority", []),
        )
    return out


def elem_text(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def parse_paper(elem: ET.Element, venue: VenueConfig, year: int) -> dict | None:
    key = elem.get("key", "")
    if not key or PROCEEDINGS_KEY.match(key):
        return None

    title = elem_text(elem.find("title"))
    if not title:
        return None

    authors = [elem_text(a) for a in elem.findall("author") if elem_text(a)]
    pages = elem_text(elem.find("pages")) or None
    year_text = elem_text(elem.find("year")) or str(year)

    ee_links: list[str] = []
    for ee in elem.findall("ee"):
        t = elem_text(ee)
        if t:
            ee_links.append(t)

    return {
        "title": title.rstrip("."),
        "authors": authors,
        "pages": pages,
        "year": year_text,
        "venue": f"{venue.short_name} {year}",
        "paper_type": elem.tag,
        "dblp_key": key,
        "dblp_url": f"https://dblp.org/rec/{key}.html",
        "ee_links": ee_links,
    }


def should_skip_paper(paper: dict, venue: VenueConfig, year: int) -> bool:
    key = paper.get("dblp_key", "")
    skip_keys = {f"conf/{venue.slug}/{year}"}
    for vol in range(1, 6):
        skip_keys.add(f"conf/{venue.slug}/{year}-{vol}")
    if key in skip_keys:
        return True
    for pat in venue.skip_title_patterns:
        if re.search(pat, paper["title"], re.I):
            return True
    return False


def match_venue(key: str, venues: dict[str, VenueConfig]) -> str | None:
    if not key.startswith("conf/"):
        return None
    parts = key.split("/")
    if len(parts) < 3:
        return None
    slug = parts[1]
    if slug in venues:
        return slug
    return None


def infer_year(elem: ET.Element, key: str) -> int | None:
    y = elem_text(elem.find("year"))
    if y and y.isdigit():
        return int(y)
    parts = key.split("/")
    if len(parts) >= 3:
        m = re.match(r"(\d{4})", parts[2])
        if m:
            return int(m.group(1))
    booktitle = elem_text(elem.find("booktitle"))
    m = re.search(r"\b(19|20)\d{2}\b", booktitle)
    if m:
        return int(m.group(0))
    return None


def _clear_elem(elem) -> None:
    """Drop parsed subtree to limit memory during streaming."""
    elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]


def download_xml(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DBLP_XML_GZ} -> {dest}", flush=True)
    print("(~1 GB compressed; may take several minutes)", flush=True)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    with session.get(DBLP_XML_GZ, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with dest.open("wb") as out:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                out.write(chunk)
                done += len(chunk)
                if total and done % (50 * 1024 * 1024) < len(chunk):
                    print(f"\r  {done * 100 / total:.1f}%", end="", flush=True)
    print(f"\nSaved {dest} ({dest.stat().st_size / 1e9:.2f} GB)", flush=True)


def stream_parse(xml_path: Path, venues: dict[str, VenueConfig]) -> dict[tuple[str, int], list[dict]]:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    counts = defaultdict(int)
    t0 = time.time()

    with gzip.open(xml_path, "rb") as fh:
        context = ET.iterparse(
            fh,
            events=("end",),
            tag="inproceedings",
            huge_tree=True,
            recover=True,
            resolve_entities=False,
        )
        for _event, elem in context:
            key = elem.get("key", "")
            slug = match_venue(key, venues)
            if not slug:
                _clear_elem(elem)
                continue
            year = infer_year(elem, key)
            if year is None or year < 1970 or year > 2035:
                _clear_elem(elem)
                continue
            venue = venues[slug]
            paper = parse_paper(elem, venue, year)
            if paper and not should_skip_paper(paper, venue, year):
                grouped[(slug, year)].append(paper)
                counts[slug] += 1
            _clear_elem(elem)

            total = sum(counts.values())
            if total % 5000 == 0 and total > 0:
                elapsed = time.time() - t0
                print(f"  ... {total} papers ({elapsed:.0f}s)", flush=True)

    print(f"Parsed {sum(counts.values())} papers in {time.time() - t0:.1f}s")
    for slug in sorted(venues):
        years = {y for s, y in grouped if s == slug}
        if years:
            print(f"  {slug}: {counts[slug]} papers, years {min(years)}-{max(years)}")
    return grouped


def source_urls_for(slug: str, year: int) -> list[str]:
    base = f"https://dblp.org/db/conf/{slug}/{slug}{year}"
    urls = [f"{base}.html"]
    if slug == "asplos" and year >= 2018:
        urls.append(f"{base}-1.html")
        urls.append(f"{base}-2.html")
    return urls


def dblp_manifest_path(hub: Hub) -> Path:
    return hub.root / "data" / f"dblp-build-{hub.id}.json"


def write_website(
    grouped: dict[tuple[str, int], list[dict]],
    venues: dict[str, VenueConfig],
    *,
    web_data: Path = WEB_DATA,
) -> int:
    web_data.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for (slug, year), papers in sorted(grouped.items(), key=lambda x: (-x[0][1], x[0][0])):
        venue = venues[slug]
        conf_id = f"{slug}-{year}"
        papers_sorted = sorted(papers, key=lambda p: p["title"].lower())
        src_urls = source_urls_for(slug, year)
        payload = {
            "id": conf_id,
            "venue": slug,
            "year": year,
            "short_name": venue.short_name,
            "full_name": venue.full_name,
            "source_url": src_urls[0],
            "source_urls": src_urls,
            "skip_dblp_keys": [f"conf/{slug}/{year}"] + [
                f"conf/{slug}/{year}-{v}" for v in range(1, 6)
            ],
            "skip_title_patterns": venue.skip_title_patterns,
            "link_priority": venue.link_priority,
            "count": len(papers_sorted),
            "display_count": len(papers_sorted),
            "papers": papers_sorted,
        }
        out = web_data / f"{conf_id}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_entries.append(
            {
                "id": conf_id,
                "short_name": venue.short_name,
                "full_name": venue.full_name,
                "year": year,
                "paper_count": payload["display_count"],
                "data_file": f"data/{conf_id}.json",
                "source_urls": src_urls,
            }
        )
        print(f"  {conf_id}: {payload['display_count']} papers")

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {"conferences": manifest_entries, "generated_at": generated_at}
    (web_data / "conferences.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (web_data / "build-info.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "conference_count": len(manifest_entries),
                "source": "dblp",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    valid_ids = {e["id"] for e in manifest_entries}
    for stale in web_data.glob("*.json"):
        if stale.name in (
            "conferences.json",
            "arxiv-recent.json",
            "build-info.json",
            "conference-timeline.json",
            "top-monthly.json",
            "top-published.json",
            "top-areas.json",
            "today-broadcast.json",
            "hub.json",
        ):
            continue
        stem = stale.stem
        if stem not in valid_ids:
            stale.unlink()
            print(f"  removed stale {stale.name}")

    print(f"Manifest: {len(manifest_entries)} conference-years")
    return len(manifest_entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse dblp XML for top OS venues.")
    add_hub_argument(parser)
    parser.add_argument("--download", action="store_true", help="download dblp.xml.gz")
    parser.add_argument("--build-website", action="store_true", help="parse XML and write website/data")
    parser.add_argument("--all", action="store_true", help="download + build")
    parser.add_argument("--xml", type=Path, default=None, help="path to dblp.xml.gz")
    parser.add_argument(
        "--if-stale",
        action="store_true",
        help="skip rebuild when dblp.xml.gz unchanged and conferences.json exists",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="always re-parse dblp XML and rewrite website/data",
    )
    args = parser.parse_args()
    hub = load_hub(args.hub)
    xml_path = args.xml or hub.dblp_xml

    if not (args.download or args.build_website or args.all):
        args.all = True

    if args.download or args.all:
        download_xml(xml_path)

    if args.build_website or args.all:
        if not xml_path.is_file():
            print(f"Missing {xml_path}; run with --download first", file=sys.stderr)
            return 1

        xml_fp = file_fingerprint(xml_path)
        manifest_path = dblp_manifest_path(hub)
        manifest = load_json(manifest_path)
        conf_manifest = hub.web_data / "conferences.json"

        if (
            args.if_stale
            and not args.force
            and conf_manifest.is_file()
            and is_fresh(manifest, fingerprint=xml_fp, max_age_hours=None)
        ):
            print(
                f"dblp build up to date (xml {xml_fp[:40]}…); "
                f"skip parse → {hub.web_data}"
            )
            return 0

        venues = load_venues(hub)
        print(f"Streaming parse for hub {hub.id} (this may take several minutes)...")
        grouped = stream_parse(xml_path, venues)
        if not grouped:
            print("No papers matched; check venue slugs.", file=sys.stderr)
            return 2
        print(f"Writing website data to {hub.web_data}...")
        n = write_website(grouped, venues, web_data=hub.web_data)
        save_json(
            manifest_path,
            {
                "hub_id": hub.id,
                "source": "dblp",
                "fingerprint": xml_fp,
                "built_at": utc_now_iso(),
                "xml_path": str(xml_path.relative_to(hub.root)),
                "conference_count": n,
                "web_data": str(hub.web_data.relative_to(hub.root)),
            },
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
