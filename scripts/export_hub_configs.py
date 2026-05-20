#!/usr/bin/env python3
"""
Re-export hubs/<id>/*.json from Python sources (dev utility).

Run after editing keyword constants in crawl_arxiv_recent.py or build_top_monthly.py.
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def literal_value(node: ast.AST):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset":
        return frozenset(ast.literal_eval(node.args[0]))
    return ast.literal_eval(node)


def load_ann_or_assign(name: str, path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        val = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            val = node.value
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    val = node.value
        if val is not None:
            return literal_value(val)
    raise SystemExit(f"missing {name} in {path}")


def kw(kws: list[tuple[str, int]]) -> list[list]:
    return [[a, b] for a, b in kws]


def export_os_kernel() -> None:
    hub_dir = ROOT / "hubs" / "os-kernel"
    hub_dir.mkdir(parents=True, exist_ok=True)

    cats = load_ann_or_assign("CATEGORIES", ROOT / "build_top_monthly.py")
    categories = [{"id": c["id"], "label": c["label"], "keywords": kw(c["keywords"])} for c in cats]
    (hub_dir / "categories.json").write_text(
        json.dumps(
            {
                "min_category_score": 4,
                "per_category_limit": 5,
                "default_years": [2023, 2024, 2025, 2026],
                "arxiv_pick_years": [2025, 2026],
                "section_heading": "Top picks by area",
                "arxiv_mode_label": "Recent arXiv picks by areas",
                "published_mode_label": "Published paper picks by area",
                "categories": categories,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    ar_path = ROOT / "crawl_arxiv_recent.py"
    noise = load_ann_or_assign("NOISE_PRIMARY_CATEGORIES", ar_path)
    arxiv_policy = {
        "feeds": [
            {"id": "cs.OS", "max_param": "os_max", "default_max": 40},
            {"id": "cs.CL", "max_param": "cl_max", "default_max": 120, "filter": "cl_systems"},
        ],
        "sys_keywords": kw(load_ann_or_assign("SYS_LLM_KEYWORDS", ar_path)),
        "sys_strong": sorted(load_ann_or_assign("STRONG_KEYWORDS", ar_path)),
        "cl_keywords": kw(load_ann_or_assign("CL_SYS_KEYWORDS", ar_path)),
        "cl_strong": sorted(load_ann_or_assign("CL_STRONG_KEYWORDS", ar_path)),
        "os_gate_keywords": load_ann_or_assign("OS_GATE_KEYWORDS", ar_path),
        "llm_systems_keywords": load_ann_or_assign("LLM_SYSTEMS_KEYWORDS", ar_path),
        "noise_primary_categories": sorted(noise),
        "cl_min_score_default": 6,
        "days_default": 14,
        "years_fetch_boost": {"os_max": 200, "cl_max": 500},
        "filter_note": (
            "cs.CL: OS cross-list or system-software terms required; "
            "generic LLM/NLP or serving-only papers excluded."
        ),
        "broadcast": {
            "limit": 3,
            "min_score": 4,
            "lookback_days": 7,
            "keywords": kw(load_ann_or_assign("BROADCAST_KEYWORDS", ROOT / "build_today_broadcast.py")),
            "strong": sorted(load_ann_or_assign("BROADCAST_STRONG", ROOT / "build_today_broadcast.py")),
            "note": (
                "Top arXiv papers from the last 7 days (UTC+8), ranked by area keyword score "
                "on title and abstract (same as Top picks by area)."
            ),
        },
    }
    (hub_dir / "arxiv_policy.json").write_text(json.dumps(arxiv_policy, indent=2) + "\n", encoding="utf-8")
    shutil.copy(ROOT / "venues.json", hub_dir / "venues.json")
    shutil.copy(ROOT / "conference_timeline_2026.json", hub_dir / "conference_timeline.json")
    print(f"Updated {hub_dir}")


def main() -> int:
    export_os_kernel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
