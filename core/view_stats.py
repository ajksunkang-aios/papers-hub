"""Shared view-counting helpers for the dev API and tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ZONES_PATH = ROOT / "core" / "view_zones.json"


def load_zones_config(path: Path | None = None) -> dict[str, Any]:
    zones_path = path or DEFAULT_ZONES_PATH
    return json.loads(zones_path.read_text(encoding="utf-8"))


def build_zone_maps(zones: dict[str, Any]) -> dict[str, Any]:
    zone_order: list[str] = zones["zone_order"]
    zone_labels: dict[str, str] = zones["zone_labels"]

    country_to_zone_map: dict[str, str] = {}
    for zone in zone_order:
        if zone == "other":
            continue
        for code in zones.get("countries", {}).get(zone, []):
            country_to_zone_map[code.upper()] = zone

    return {
        "zone_order": zone_order,
        "zone_labels": zone_labels,
        "country_to_zone": country_to_zone_map,
    }


def country_to_zone(code: str | None, country_to_zone_map: dict[str, str]) -> str:
    c = (code or "").upper()
    if not c or c in {"XX", "T1"}:
        return "other"
    return country_to_zone_map.get(c, "other")


def load_stats(raw: dict[str, Any] | None, maps: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw or {})
    data.setdefault("total", 0)
    data.setdefault("zones", {})
    for zone in maps["zone_order"]:
        data["zones"].setdefault(zone, 0)
    data["zone_labels"] = maps["zone_labels"]
    data["zone_order"] = maps["zone_order"]
    return data


def stats_payload(data: dict[str, Any], maps: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": int(data.get("total", 0)),
        "zones": {z: int(data.get("zones", {}).get(z, 0)) for z in maps["zone_order"]},
        "zone_labels": maps["zone_labels"],
        "zone_order": maps["zone_order"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def record_hit(
    data: dict[str, Any],
    maps: dict[str, Any],
    country: str,
    city: str | None = None,
) -> str:
    del city  # geo city unused after region-only simplification
    zone = country_to_zone(country, maps["country_to_zone"])
    data["total"] = int(data.get("total", 0)) + 1
    data["zones"][zone] = int(data["zones"].get(zone, 0)) + 1
    return zone
