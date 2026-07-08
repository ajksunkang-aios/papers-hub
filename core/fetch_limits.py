"""Shared network time budgets to avoid enrich jobs hanging on slow HTTP."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# dblp curl: connect + total wall clock (seconds)
DBLP_CONNECT_TIMEOUT_SEC = 5
DBLP_MAX_TIME_SEC = int(os.environ.get("DBLP_HTTP_MAX_TIME_SEC", "12"))

# OpenAlex requests (connect, read)
OPENALEX_TIMEOUT = (
    float(os.environ.get("OPENALEX_CONNECT_TIMEOUT_SEC", "3")),
    float(os.environ.get("OPENALEX_READ_TIMEOUT_SEC", "8")),
)

# Per-author dblp HTTP budget (search + person page)
DBLP_AUTHOR_BUDGET_SEC = float(os.environ.get("DBLP_AUTHOR_BUDGET_SEC", "35"))

# OpenAlex lookups per paper (doi + arxiv + title)
OPENALEX_PAPER_BUDGET_SEC = float(os.environ.get("OPENALEX_PAPER_BUDGET_SEC", "25"))

# Log when a single paper enrich exceeds this wall time
PAPER_SLOW_LOG_SEC = float(os.environ.get("AUTHOR_ENRICH_SLOW_LOG_SEC", "20"))


class TimeBudget:
    """Simple monotonic deadline helper."""

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + max(0.0, seconds)

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


def run_with_wall_clock(
    fn: Callable[[], T],
    *,
    timeout_sec: float,
    on_timeout: Callable[[], T],
) -> T:
    """Run ``fn`` with a soft wall clock; returns ``on_timeout()`` if exceeded.

    Uses a worker thread so the main enrich loop can continue. A stuck network
    call may linger in the background, but subsequent papers are not blocked
    indefinitely.
    """
    if timeout_sec <= 0:
        return fn()
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except FuturesTimeout:
            return on_timeout()
