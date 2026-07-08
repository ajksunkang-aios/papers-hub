#!/usr/bin/env python3
"""Tests for broad topic tag extraction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.topic_tags import extract_paper_topic_tags, match_topic_tags, parent_area_for_topic  # noqa: E402


class TopicTagTests(unittest.TestCase):
    def test_match_memory_management(self) -> None:
        tags = match_topic_tags("CacheMind: trace-grounded reasoning for cache replacement")
        self.assertIn("Memory management", tags)

    def test_extract_quantum_title(self) -> None:
        tags = extract_paper_topic_tags(title="Borrowing Dirty Qubits in Quantum Programs")
        self.assertTrue(any("Quantum" in t for t in tags))

    def test_memory_management_parent_area(self) -> None:
        self.assertEqual(parent_area_for_topic("memory-cache"), "memory-resource")

    def test_fallback_title_tokens(self) -> None:
        tags = extract_paper_topic_tags(title="Arancini: Hybrid Binary Translator Architectures")
        self.assertTrue(tags)


if __name__ == "__main__":
    unittest.main()
