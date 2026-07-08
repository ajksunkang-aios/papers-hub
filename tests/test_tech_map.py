#!/usr/bin/env python3
"""Tests for technology map config."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPECTED_GROUP_IDS = [
    "classic-os",
    "arch-codesign",
    "security-formal",
    "agentic-infra",
    "scenario-ai",
    "aios",
]


class TechMapTests(unittest.TestCase):
    def test_hub_tech_map_schema(self) -> None:
        path = ROOT / "hubs" / "os-kernel" / "tech-map.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        groups = data["groups"]
        self.assertEqual(len(groups), 6)
        self.assertEqual([g["id"] for g in groups], EXPECTED_GROUP_IDS)

        by_id = {g["id"]: g for g in groups}
        self.assertEqual(len(by_id["classic-os"]["topics"]), 9)
        self.assertEqual(len(by_id["arch-codesign"]["topics"]), 2)
        self.assertEqual(len(by_id["security-formal"]["topics"]), 3)
        self.assertEqual(len(by_id["agentic-infra"]["topics"]), 5)
        agentic_ids = {t["id"] for t in by_id["agentic-infra"]["topics"]}
        self.assertEqual(
            agentic_ids,
            {"agentic-foundation", "dev-agent", "test-agent", "ops-agent", "security-agent"},
        )
        foundation = next(t for t in by_id["agentic-infra"]["topics"] if t["id"] == "agentic-foundation")
        foundation_els = {e["id"] for e in foundation["elements"]}
        self.assertTrue(
            {
                "multi-agent",
                "loop-harness",
                "memory-arch",
                "mcp-skill-protocol",
                "codegraph",
                "knowledgegraph",
            }.issubset(foundation_els)
        )
        self.assertEqual(len(by_id["scenario-ai"]["topics"]), 4)
        self.assertEqual(len(by_id["aios"]["topics"]), 2)

        aios_ids = {t["id"] for t in by_id["aios"]["topics"]}
        self.assertEqual(aios_ids, {"ai-inside-kernel", "agent-os"})

        agent_os = next(t for t in by_id["aios"]["topics"] if t["id"] == "agent-os")
        self.assertEqual(agent_os["label_en"], "Agentic OS")

        ai_kernel = next(t for t in by_id["aios"]["topics"] if t["id"] == "ai-inside-kernel")
        self.assertNotIn("area_id", ai_kernel)
        self.assertNotIn("area_id", agent_os)

        scenario_ids = {t["id"] for t in by_id["scenario-ai"]["topics"]}
        self.assertIn("embodied-intelligence", scenario_ids)
        self.assertIn("ai-hw-xr", scenario_ids)


if __name__ == "__main__":
    unittest.main()
