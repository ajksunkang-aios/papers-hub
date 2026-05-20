"""Shared area keyword scoring for top picks and the recent broadcast bar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.hub_config import Hub, pairs_from_json
from core.keywords import score_keywords


@dataclass
class AreaPickScoring:
    categories: list[dict[str, Any]]
    min_score: int = 4

    @classmethod
    def from_hub(cls, hub: Hub) -> AreaPickScoring:
        rows = []
        for cat in hub.categories.get("categories", []):
            rows.append(
                {
                    "id": cat["id"],
                    "label": cat["label"],
                    "keywords": pairs_from_json(cat["keywords"]),
                }
            )
        min_score = int(hub.categories.get("min_category_score", 4))
        return cls(categories=rows, min_score=min_score)

    @staticmethod
    def paper_text(paper: dict) -> str:
        return " ".join(
            p
            for p in (
                paper.get("title", ""),
                paper.get("abstract", ""),
                paper.get("source_feed", ""),
            )
            if p
        )

    def score_category(self, text: str, cat: dict) -> tuple[int, list[str]]:
        keywords = cat["keywords"]
        strong = {kw for kw, weight in keywords if weight >= 10}
        return score_keywords(text, keywords, strong, max_tags=6)

    def best_match(self, text: str) -> tuple[str, str, int, list[str]] | None:
        best_id = ""
        best_label = ""
        best_score = 0
        best_tags: list[str] = []
        for cat in self.categories:
            score, tags = self.score_category(text, cat)
            if score > best_score:
                best_score = score
                best_id = cat["id"]
                best_label = cat["label"]
                best_tags = tags
        if best_score < self.min_score:
            return None
        return best_id, best_label, best_score, best_tags

    def score_paper(self, paper: dict) -> tuple[int, list[str], str | None, str | None]:
        """Return (score, matched_tags, category_id, category_label)."""
        match = self.best_match(self.paper_text(paper))
        if not match:
            return 0, [], None, None
        cat_id, cat_label, score, tags = match
        return score, tags, cat_id, cat_label
