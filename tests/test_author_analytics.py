#!/usr/bin/env python3
"""Tests for author analytics aggregation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_author_analytics import build_analytics, pick_display_name  # noqa: E402
from core.hub_config import load_hub  # noqa: E402


class AuthorAnalyticsTests(unittest.TestCase):
    def test_pick_display_name_prefers_most_common(self) -> None:
        from collections import Counter

        counts = Counter({"Shan Lu 0001": 3, "Shan Lu": 1})
        self.assertEqual(pick_display_name(counts), "Shan Lu 0001")

    def test_build_analytics_top50(self) -> None:
        hub = load_hub("os-kernel", root=ROOT)
        if not (hub.web_data / "conferences.json").is_file():
            self.skipTest("website data not present")
        payload = build_analytics(hub, years=[2025, 2026])
        self.assertLessEqual(len(payload["authors"]), 50)
        self.assertGreater(payload["coverage"]["unique_authors"], 0)
        if payload["authors"]:
            top = payload["authors"][0]
            self.assertIn("paper_count", top)
            self.assertIn("tech_tags", top)
            self.assertIn("primary_areas", top)
            self.assertEqual(top["rank"], 1)


if __name__ == "__main__":
    unittest.main()
