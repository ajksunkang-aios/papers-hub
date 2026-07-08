#!/usr/bin/env python3
"""Tests for technology map config."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TechMapTests(unittest.TestCase):
    def test_hub_tech_map_schema(self) -> None:
        path = ROOT / "hubs" / "os-kernel" / "tech-map.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        classic = next(g for g in data["groups"] if g["id"] == "classic-os")
        extended = next(g for g in data["groups"] if g["id"] == "extended")
        self.assertEqual(len(classic["topics"]), 10)
        self.assertEqual(len(extended["topics"]), 7)
        ebpf = next(t for t in classic["topics"] if t["id"] == "ebpf-programmable")
        self.assertEqual(ebpf.get("area_id"), "ebpf")
        scheduling = next(t for t in classic["topics"] if t["id"] == "scheduling")
        self.assertEqual(scheduling["label_en"], "Scheduling")
        ai_kernel = next(t for t in extended["topics"] if t["id"] == "ai-inside-kernel")
        agent_os = next(t for t in extended["topics"] if t["id"] == "agent-os")
        self.assertNotIn("area_id", ai_kernel)
        self.assertNotIn("area_id", agent_os)


if __name__ == "__main__":
    unittest.main()
