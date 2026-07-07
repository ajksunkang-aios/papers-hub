#!/usr/bin/env python3
"""Tests for dblp affiliation parsing and author profile helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.author_profiles import (  # noqa: E402
    attach_author_fields,
    ensure_all_authors_have_affiliations,
    merge_author_affiliations,
    paper_authors_complete,
)
from core.author_reload import (  # noqa: E402
    AuthorPaperReloadIndex,
    dblp_authors_resolved,
    paper_needs_online_fetch,
)
from core.dblp_affiliations import DblpAffiliationCache, parse_person_affiliations  # noqa: E402


SAMPLE_PERSON_HTML = """
<header><h2>Person information</h2></header>
<div class="hide-body"><ul>
<li itemprop="affiliation" itemscope itemtype="http://schema.org/Organization">
  <em>affiliation:</em> <span itemprop="name">University of Queensland, Brisbane, QLD, Australia</span>
</li>
<li itemprop="affiliation" itemscope itemtype="http://schema.org/Organization">
  <em>affiliation (PhD 2014):</em> <span itemprop="name">Peking University, Beijing, China</span>
</li>
</ul></div>
"""


class DblpAffiliationTests(unittest.TestCase):
    def test_parse_person_affiliations(self) -> None:
        affs = parse_person_affiliations(SAMPLE_PERSON_HTML)
        self.assertEqual(len(affs), 2)
        self.assertIn("Australia", affs[0])
        self.assertIn("China", affs[1])

    def test_merge_author_affiliations(self) -> None:
        rows = [{"name": "Alice", "affiliations": []}, {"name": "Bob", "affiliations": ["MIT"]}]
        merged = merge_author_affiliations(
            rows,
            {"alice": ["Tsinghua University, Beijing, China"]},
        )
        self.assertEqual(merged[0]["affiliations"][0], "Tsinghua University, Beijing, China")
        self.assertEqual(merged[1]["affiliations"], ["MIT"])

    def test_merge_replaces_unknown_placeholder(self) -> None:
        rows = [{"name": "Alice", "affiliations": ["Unknown affiliation"]}]
        merged = merge_author_affiliations(
            rows,
            {"alice": ["Tsinghua University, Beijing, China"]},
        )
        self.assertEqual(merged[0]["affiliations"][0], "Tsinghua University, Beijing, China")
        self.assertFalse(paper_authors_complete({"authors": ["Alice"], "authors_structured": rows}))

    def test_ensure_all_authors_have_affiliations(self) -> None:
        rows = ensure_all_authors_have_affiliations([{"name": "Alice", "affiliations": []}])
        self.assertEqual(rows[0]["affiliations"], ["Unknown affiliation"])

    def test_paper_authors_complete(self) -> None:
        paper = attach_author_fields({"authors": ["Alice", "Bob"]})
        self.assertFalse(paper_authors_complete(paper))
        self.assertEqual(len(paper["authors_structured"]), 2)

        complete = attach_author_fields(
            {
                "authors": ["Alice"],
                "authors_structured": [
                    {
                        "name": "Alice",
                        "affiliations": ["MIT CSAIL, Cambridge, MA, USA"],
                        "country_code": "US",
                    }
                ],
            }
        )
        self.assertTrue(paper_authors_complete(complete))


class AuthorReloadTests(unittest.TestCase):
    def test_dblp_miss_skips_online_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = DblpAffiliationCache(Path(tmp) / "dblp.json")
            cache.set_miss("alice")
            paper = {
                "authors": ["Alice"],
                "authors_structured": [{"name": "Alice", "affiliations": []}],
                "dblp_key": "conf/test/Alice26",
            }
            self.assertTrue(dblp_authors_resolved(["Alice"], cache))
            self.assertFalse(
                paper_needs_online_fetch(paper, dblp_cache=cache, first_author_only=True)
            )

    def test_unresolved_author_needs_online(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = DblpAffiliationCache(Path(tmp) / "dblp.json")
            paper = {
                "authors": ["Bob"],
                "authors_structured": [{"name": "Bob", "affiliations": []}],
            }
            self.assertTrue(
                paper_needs_online_fetch(
                    paper, dblp_cache=cache, first_author_only=True
                )
            )

    def test_reload_index_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reload.json"
            index = AuthorPaperReloadIndex(path)
            paper = {
                "title": "Hello World",
                "dblp_key": "conf/test/Hello26",
                "authors_structured": [
                    {
                        "name": "Alice",
                        "affiliations": ["MIT, USA"],
                        "country_code": "US",
                    }
                ],
                "first_author_affiliations": ["MIT, USA"],
            }
            index.set_paper(paper)
            index.save()
            loaded = AuthorPaperReloadIndex(path)
            rows = loaded.get(paper)
            self.assertIsNotNone(rows)
            assert rows is not None
            self.assertEqual(rows[0]["country_code"], "US")

    def test_fetcher_respects_max_lookups(self) -> None:
        from core.dblp_affiliations import DblpAffiliationFetcher

        with tempfile.TemporaryDirectory() as tmp:
            cache = DblpAffiliationCache(Path(tmp) / "dblp.json")
            fetcher = DblpAffiliationFetcher(
                cache=cache,
                offline=False,
                online_fallback=True,
                max_lookups=0,
            )
            self.assertEqual(fetcher.resolve_author("Alice"), [])
            self.assertTrue(fetcher.budget_exhausted)
            self.assertEqual(fetcher.online_lookups, 0)
            self.assertIsNone(cache.get("alice"))
            self.assertFalse(cache.is_miss("alice"))

    def test_fetcher_uses_person_index_without_http(self) -> None:
        from core.dblp_affiliations import DblpAffiliationFetcher
        from core.dblp_person_index import DblpPersonIndex

        with tempfile.TemporaryDirectory() as tmp:
            cache = DblpAffiliationCache(Path(tmp) / "dblp.json")
            index_path = Path(tmp) / "person-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            "alice example": {
                                "pid": "e/AliceExample",
                                "affiliations": ["MIT, Cambridge, MA, USA"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            person_index = DblpPersonIndex(index_path)
            person_index.load()
            fetcher = DblpAffiliationFetcher(
                cache=cache,
                offline=True,
                person_index=person_index,
                online_fallback=False,
            )
            affs = fetcher.resolve_author("Alice Example")
            self.assertEqual(affs, ["MIT, Cambridge, MA, USA"])
            self.assertEqual(fetcher.online_lookups, 0)
            self.assertEqual(cache.get("alice example"), ["MIT, Cambridge, MA, USA"])


if __name__ == "__main__":
    unittest.main()
