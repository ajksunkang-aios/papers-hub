#!/usr/bin/env python3
"""Tests for author affiliation and country resolution helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.author_country import (  # noqa: E402
    AuthorCountryResolver,
    build_institution_matcher,
    enrich_authors_structured_local,
    infer_country_from_text,
    parse_openalex_authorship,
    parse_openalex_authorship_rows,
    resolve_author_local,
    upgrade_authors_structured,
)


class AuthorCountryTests(unittest.TestCase):
    def test_institution_hints(self) -> None:
        matcher = build_institution_matcher([["tsinghua", "CN"], ["mit", "US"]])
        self.assertEqual(infer_country_from_text("Tsinghua University", matcher), "CN")
        self.assertEqual(infer_country_from_text("MIT CSAIL", matcher), "US")
        self.assertIsNone(infer_country_from_text("mechanisms to mitigate hallucination", matcher))

    def test_country_keywords(self) -> None:
        matcher = build_institution_matcher([["china", "CN"], ["usa", "US"]])
        self.assertEqual(infer_country_from_text("Some Lab, Beijing, China", matcher), "CN")
        self.assertEqual(infer_country_from_text("Dept of CS, California, USA", matcher), "US")

    def test_openalex_first_author(self) -> None:
        work = {
            "authorships": [
                {
                    "author_position": "first",
                    "author": {"display_name": "Alice Zhang"},
                    "institutions": [{"display_name": "Tsinghua University", "country_code": "CN"}],
                    "raw_affiliation_strings": ["Tsinghua University"],
                }
            ]
        }
        name, code, affs = parse_openalex_authorship(work)
        self.assertEqual(name, "Alice Zhang")
        self.assertEqual(code, "CN")
        self.assertTrue(affs)

    def test_openalex_all_authors(self) -> None:
        work = {
            "authorships": [
                {
                    "author": {"display_name": "Alice Zhang"},
                    "institutions": [{"display_name": "Tsinghua University", "country_code": "CN"}],
                },
                {
                    "author": {"display_name": "Bob Lee"},
                    "institutions": [{"display_name": "MIT", "country_code": "US"}],
                },
            ]
        }
        rows = parse_openalex_authorship_rows(work, policy={"country_labels": {}})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["country_code"], "CN")
        self.assertEqual(rows[1]["country_code"], "US")

    def test_upgrade_authors_structured(self) -> None:
        paper = {
            "authors": ["Alice", "Bob"],
            "first_author_affiliations": ["Tsinghua University"],
        }
        rows = upgrade_authors_structured(paper)
        self.assertEqual(rows[0]["affiliations"], ["Tsinghua University"])
        self.assertEqual(rows[1]["affiliations"], [])

    def test_enrich_authors_structured_local(self) -> None:
        policy = {
            "country_labels": {"CN": "China", "US": "United States", "XX": "Unknown"},
            "institution_hints": [["tsinghua", "CN"], ["mit", "US"]],
            "country_keywords": [],
        }
        rows = enrich_authors_structured_local(
            [
                {"name": "Alice", "affiliations": ["Tsinghua University"]},
                {"name": "Bob", "affiliations": ["MIT CSAIL"]},
            ],
            policy=policy,
        )
        self.assertEqual(rows[0]["country_code"], "CN")
        self.assertEqual(rows[1]["country_code"], "US")

    def test_offline_resolver_uses_affiliations(self) -> None:
        resolver = AuthorCountryResolver(
            cache=type("C", (), {"get": lambda *a, **k: None, "is_miss": lambda *a, **k: False, "set": lambda *a, **k: None, "set_miss": lambda *a, **k: None, "save": lambda *a, **k: None})(),  # type: ignore
            policy={
                "country_labels": {"CN": "China", "XX": "Unknown"},
                "institution_hints": [["tsinghua", "CN"]],
                "country_keywords": [],
            },
            offline=True,
        )
        result = resolver.resolve(
            title="Demo Paper",
            authors=["Bob"],
            affiliations=["Tsinghua University"],
        )
        self.assertEqual(result.country_code, "CN")
        self.assertEqual(result.confidence, "medium")

    def test_resolve_author_local_unknown(self) -> None:
        profile = resolve_author_local(
            "Unknown Author",
            ["Generic Research Lab"],
            policy={"country_labels": {"XX": "Unknown"}, "institution_hints": [], "country_keywords": []},
        )
        self.assertEqual(profile.country_code, "XX")


if __name__ == "__main__":
    unittest.main()
