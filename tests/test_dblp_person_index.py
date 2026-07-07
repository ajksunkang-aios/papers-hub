#!/usr/bin/env python3
"""Tests for offline dblp person index parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from lxml import etree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.dblp_person_index import parse_www_person  # noqa: E402


SAMPLE_WWW = """
<www key="homepages/t/TorvaldsLinus" mdate="2020-01-01">
  <author>Linus Torvalds</author>
  <note type="affiliation">Linux Foundation, USA</note>
  <note type="affiliation" label="former">University of Helsinki, Finland</note>
  <note type="award">Award</note>
  <title>Home Page</title>
  <url>https://example.org/</url>
</www>
"""


class DblpPersonIndexParseTests(unittest.TestCase):
    def test_parse_www_person(self) -> None:
        elem = ET.fromstring(SAMPLE_WWW)
        parsed = parse_www_person(elem)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        pid, authors, affiliations = parsed
        self.assertEqual(pid, "t/TorvaldsLinus")
        self.assertEqual(authors, ["Linus Torvalds"])
        self.assertEqual(
            affiliations,
            ["Linux Foundation, USA", "University of Helsinki, Finland"],
        )

    def test_parse_www_person_skips_non_home_page(self) -> None:
        elem = ET.fromstring(
            """
            <www key="homepages/x/X" mdate="2020-01-01">
              <author>X</author>
              <title>Other</title>
            </www>
            """
        )
        self.assertIsNone(parse_www_person(elem))


if __name__ == "__main__":
    unittest.main()
