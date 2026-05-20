"""Manifests and staleness checks for incremental dblp / arXiv builds."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_fingerprint(path: Path) -> str:
    """Fast local fingerprint (size + mtime). Good enough for large dblp.xml.gz."""
    if not path.is_file():
        return ""
    st = path.stat()
    return f"size={st.st_size}:mtime={int(st.st_mtime)}"


def policy_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_hours(ts: str) -> float | None:
    dt = parse_iso(ts)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def is_fresh(
    manifest: dict[str, Any],
    *,
    fingerprint: str,
    max_age_hours: float | None,
    extra_keys: dict[str, Any] | None = None,
) -> bool:
    """True when manifest matches fingerprint and is younger than max_age_hours."""
    if not manifest:
        return False
    if fingerprint and manifest.get("fingerprint") != fingerprint:
        return False
    if extra_keys:
        for key, val in extra_keys.items():
            if manifest.get(key) != val:
                return False
    if max_age_hours is None:
        return True
    built = manifest.get("built_at") or manifest.get("last_success_at")
    hrs = age_hours(built) if built else None
    if hrs is None:
        return False
    return hrs < max_age_hours
