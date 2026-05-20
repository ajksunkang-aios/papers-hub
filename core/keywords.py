"""Keyword scoring shared by arXiv crawl, top picks, and broadcast builders."""

from __future__ import annotations


def score_keywords(
    text: str,
    keywords: list[tuple[str, int]],
    strong_keywords: set[str],
    *,
    max_tags: int = 6,
) -> tuple[int, list[str]]:
    """Match longest phrases first so bare 'kernel' does not double-count longer OS phrases."""
    text = text.lower()
    score = 0
    tags: list[str] = []
    matched_ranges: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(s < end and start < e for s, e in matched_ranges)

    for keyword, weight in sorted(keywords, key=lambda x: -len(x[0])):
        start = 0
        while True:
            idx = text.find(keyword, start)
            if idx < 0:
                break
            end = idx + len(keyword)
            if not overlaps(idx, end):
                score += weight
                if keyword not in tags:
                    tags.append(keyword)
                matched_ranges.append((idx, end))
            start = idx + 1

    if any(k in text for k in strong_keywords):
        score += 2
    return score, tags[:max_tags]
