"""Build and query author affiliations from dblp person records in dblp.xml.gz.

Person metadata lives in the same daily dump as publications (``<www key="homepages/...">``
records with ``<note type="affiliation">``). There is no separate persons.xml artifact.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path
from typing import Any

from lxml import etree as ET

from core.author_profiles import normalize_author_key
from core.incremental import file_fingerprint, is_fresh, load_json, save_json, utc_now_iso

PERSON_INDEX_VERSION = 1
HOME_PAGE_TITLE = "Home Page"


def elem_text(el) -> str:
    if el is None:
        return ""
    import re

    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _clear_elem(elem) -> None:
    elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]


def parse_www_person(elem: ET.Element) -> tuple[str, list[str], list[str]] | None:
    """Return (pid, author_names, affiliations) for a dblp person record."""
    key = elem.get("key", "")
    if not key.startswith("homepages/"):
        return None
    if elem_text(elem.find("title")) != HOME_PAGE_TITLE:
        return None

    pid = key.removeprefix("homepages/")
    authors = [elem_text(a) for a in elem.findall("author") if elem_text(a)]
    affiliations: list[str] = []
    seen: set[str] = set()
    for note in elem.findall("note"):
        ntype = (note.get("type") or "").lower()
        if "affiliation" not in ntype:
            continue
        text = elem_text(note)
        if text and text not in seen:
            seen.add(text)
            affiliations.append(text)
    if not authors:
        return None
    return pid, authors, affiliations


def stream_build_person_index(xml_path: Path) -> dict[str, dict[str, Any]]:
    """Stream ``dblp.xml.gz`` and map normalized author names → pid + affiliations."""
    entries: dict[str, dict[str, Any]] = {}
    person_records = 0
    t0 = time.time()

    with gzip.open(xml_path, "rb") as fh:
        context = ET.iterparse(
            fh,
            events=("end",),
            tag="www",
            huge_tree=True,
            recover=True,
            resolve_entities=False,
        )
        for _event, elem in context:
            parsed = parse_www_person(elem)
            _clear_elem(elem)
            if parsed is None:
                continue
            person_records += 1
            pid, authors, affiliations = parsed
            for name in authors:
                key = normalize_author_key(name)
                if not key:
                    continue
                candidate = {"pid": pid, "affiliations": affiliations}
                prev = entries.get(key)
                if prev is None:
                    entries[key] = candidate
                    continue
                prev_affs = prev.get("affiliations") or []
                if affiliations and not prev_affs:
                    entries[key] = candidate
                elif affiliations and prev_affs and len(affiliations) > len(prev_affs):
                    entries[key] = candidate

            if person_records % 50000 == 0:
                elapsed = time.time() - t0
                print(
                    f"  ... {person_records} person records, "
                    f"{len(entries)} author keys ({elapsed:.0f}s)",
                    flush=True,
                )

    elapsed = time.time() - t0
    with_affs = sum(1 for e in entries.values() if e.get("affiliations"))
    print(
        f"Person index: {person_records} home pages → {len(entries)} author keys "
        f"({with_affs} with affiliations) in {elapsed:.1f}s",
        flush=True,
    )
    return entries


def person_index_path(hub_root: Path) -> Path:
    return hub_root / "data" / "dblp-person-index.json"


def person_index_manifest_path(hub_root: Path) -> Path:
    return hub_root / "data" / "dblp-person-index-manifest.json"


def build_person_index(xml_path: Path, index_path: Path) -> dict[str, Any]:
    print(f"Building dblp person index from {xml_path} …", flush=True)
    entries = stream_build_person_index(xml_path)
    payload = {
        "version": PERSON_INDEX_VERSION,
        "built_at": utc_now_iso(),
        "fingerprint": file_fingerprint(xml_path),
        "xml_path": str(xml_path),
        "entry_count": len(entries),
        "entries": entries,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {index_path} ({index_path.stat().st_size / 1e6:.1f} MB)", flush=True)
    return payload


def ensure_person_index(
    xml_path: Path,
    *,
    index_path: Path | None = None,
    manifest_path: Path | None = None,
    force: bool = False,
) -> Path:
    """Build or refresh the person index when ``dblp.xml.gz`` changes."""
    if not xml_path.is_file():
        raise FileNotFoundError(f"Missing dblp XML: {xml_path}")

    root = xml_path.parent.parent if xml_path.parent.name == "data" else xml_path.parent
    index_path = index_path or person_index_path(root)
    manifest_path = manifest_path or person_index_manifest_path(root)
    xml_fp = file_fingerprint(xml_path)
    manifest = load_json(manifest_path)

    if (
        not force
        and index_path.is_file()
        and is_fresh(manifest, fingerprint=xml_fp, max_age_hours=None)
    ):
        print(
            f"dblp person index up to date (xml {xml_fp[:40]}…); skip build → {index_path}",
            flush=True,
        )
        return index_path

    build_person_index(xml_path, index_path)
    save_json(
        manifest_path,
        {
            "source": "dblp-xml",
            "fingerprint": xml_fp,
            "built_at": utc_now_iso(),
            "index_path": str(index_path),
        },
    )
    return index_path


class DblpPersonIndex:
    """In-memory lookup for author name → affiliations from the offline person index."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self.loaded = False
        self.entry_count = 0

    def load(self) -> bool:
        if not self.path.is_file():
            return False
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return False
        self._entries = entries
        self.entry_count = len(entries)
        self.loaded = True
        return True

    def lookup(self, author_name: str) -> tuple[list[str], str | None] | None:
        """Return (affiliations, pid) when the author is indexed, else None."""
        if not self.loaded:
            return None
        key = normalize_author_key(author_name)
        if not key:
            return None
        entry = self._entries.get(key)
        if entry is None:
            return None
        affs = entry.get("affiliations")
        if not isinstance(affs, list):
            affs = []
        pid = entry.get("pid")
        return [a for a in affs if a], pid if isinstance(pid, str) else None


def load_person_index(hub_root: Path) -> DblpPersonIndex | None:
    index = DblpPersonIndex(person_index_path(hub_root))
    if index.load():
        return index
    return None


def main(argv: list[str] | None = None) -> int:
    import argparse

    from core.hub_config import add_hub_argument, load_hub

    parser = argparse.ArgumentParser(description="Build dblp person affiliation index from dblp.xml.gz")
    add_hub_argument(parser)
    parser.add_argument("--xml", type=Path, default=None, help="path to dblp.xml.gz")
    parser.add_argument("--force", action="store_true", help="rebuild even when xml fingerprint unchanged")
    parser.add_argument("--if-stale", action="store_true", help="skip when index matches current xml")
    args = parser.parse_args(argv)
    hub = load_hub(args.hub)
    xml_path = args.xml or hub.dblp_xml
    if not xml_path.is_file():
        print(f"Missing {xml_path}; download dblp.xml.gz first", file=sys.stderr)
        return 1
    if args.if_stale and not args.force:
        ensure_person_index(xml_path, force=False)
    else:
        ensure_person_index(xml_path, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
