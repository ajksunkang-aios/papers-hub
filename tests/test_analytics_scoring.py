#!/usr/bin/env python3
"""Tests for analytics-only area scoring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.analytics_scoring import (  # noqa: E402
    analytics_area_scoring,
    analytics_scoring_text,
)
from core.hub_config import load_hub  # noqa: E402


class AnalyticsScoringTests(unittest.TestCase):
    def test_scoring_text_excludes_venue(self) -> None:
        paper = {
            "title": "A kernel paper",
            "abstract": "We improve scheduling.",
            "authors": ["Alice Example"],
            "venue": "USENIX Security Symposium",
        }
        text = analytics_scoring_text(paper)
        self.assertNotIn("USENIX", text)
        self.assertIn("kernel", text)

    def test_venue_only_security_does_not_match(self) -> None:
        hub = load_hub("os-kernel", root=ROOT)
        scoring = analytics_area_scoring(hub)
        paper = {
            "title": "Efficient file indexing",
            "abstract": "We propose a faster B-tree layout.",
            "authors": ["Bob Example"],
            "venue": "USENIX Security Symposium",
        }
        match = scoring.best_match(analytics_scoring_text(paper))
        self.assertTrue(match is None or not match[0] or match[2] <= 0)

    def test_strong_security_keywords_still_match(self) -> None:
        hub = load_hub("os-kernel", root=ROOT)
        scoring = analytics_area_scoring(hub)
        paper = {
            "title": "Side-channel attacks on confidential computing enclaves",
            "abstract": "We analyze trusted execution environments.",
            "authors": ["Carol Example"],
            "venue": "OSDI",
        }
        match = scoring.best_match(analytics_scoring_text(paper))
        self.assertIsNotNone(match)
        self.assertEqual(match[0], "system-security")


if __name__ == "__main__":
    unittest.main()
