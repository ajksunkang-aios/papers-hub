#!/usr/bin/env python3
"""Tests for dblp affiliation parsing and author profile helpers."""

from __future__ import annotations

import sys
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
from core.dblp_affiliations import parse_person_affiliations  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
