"""Tighter area scoring for analytics pages (author / country breakdown).

Unlike top picks, analytics should not treat venue names (e.g. USENIX Security)
as keyword hits, and should ignore very weak generic keywords such as ``security``.
"""

from __future__ import annotations

from typing import Any

from core.hub_config import Hub, pairs_from_json
from core.picks_scoring import AreaPickScoring

# Drop keywords below this weight when classifying papers for analytics only.
ANALYTICS_MIN_KEYWORD_WEIGHT = 6
# Keep min_score at 0; build_author_analytics treats score <= 0 as uncategorized.
ANALYTICS_MIN_CATEGORY_SCORE = 0


def analytics_scoring_text(paper: dict[str, Any]) -> str:
    """Title + abstract + authors only (no venue / conference name)."""
    parts = [
        paper.get("title", ""),
        paper.get("abstract", ""),
        " ".join(paper.get("authors") or []),
    ]
    return " ".join(p for p in parts if p)


def analytics_area_scoring(hub: Hub) -> AreaPickScoring:
    """Hub area scorer with analytics-specific tightening."""
    rows: list[dict[str, Any]] = []
    for cat in hub.categories.get("categories", []):
        keywords = [
            (kw, weight)
            for kw, weight in pairs_from_json(cat["keywords"])
            if weight >= ANALYTICS_MIN_KEYWORD_WEIGHT
        ]
        rows.append(
            {
                "id": cat["id"],
                "label": cat["label"],
                "keywords": keywords,
            }
        )
    return AreaPickScoring(categories=rows, min_score=ANALYTICS_MIN_CATEGORY_SCORE)
