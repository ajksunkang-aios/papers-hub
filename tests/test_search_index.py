#!/usr/bin/env python3
"""Tests for search index builder."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_search_index import (  # noqa: E402
    build_index,
    is_proceedings_record,
    truncate_abstract,
)
from core.hub_config import load_hub  # noqa: E402


class SearchIndexTests(unittest.TestCase):
    def test_is_proceedings_record(self) -> None:
        meta = {"skip_dblp_keys": ["conf/fast/2026"], "skip_title_patterns": []}
        self.assertTrue(is_proceedings_record({"dblp_key": "conf/fast/2026", "title": "x"}, meta))
        self.assertFalse(is_proceedings_record({"dblp_key": "conf/fast/Zhao0", "title": "Real paper"}, meta))

    def test_truncate_abstract(self) -> None:
        text = "word " * 400
        out = truncate_abstract(text, max_len=120)
        self.assertLessEqual(len(out), 120)
        self.assertTrue(out.endswith("…"))

    def test_build_index(self) -> None:
        hub = load_hub("os-kernel", root=ROOT)
        if not (hub.web_data / "conferences.json").is_file():
            self.skipTest("website data not present")
        payload = build_index(hub, years=[2025, 2026], arxiv_years=[2025, 2026])
        self.assertGreater(payload["count"], 0)
        self.assertEqual(payload["dblp_count"] + payload["arxiv_count"], payload["count"])
        sample = payload["papers"][0]
        for key in ("id", "title", "source", "href"):
            self.assertIn(key, sample)


if __name__ == "__main__":
    unittest.main()
