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
    highlight_countries: dict[str, str] = zones.get("highlight_countries", {})
    china_city_config: dict[str, Any] = zones.get("china_cities", {})
    china_city_order: list[str] = china_city_config.get("order", [])
    china_city_labels: dict[str, str] = china_city_config.get("labels", {})

    country_to_zone: dict[str, str] = {}
    for zone in zone_order:
        if zone == "other":
            continue
        for code in zones.get("countries", {}).get(zone, []):
            country_to_zone[code.upper()] = zone

    city_to_bucket: dict[str, str] = {}
    for bucket, names in china_city_config.get("match", {}).items():
        city_to_bucket[bucket.lower()] = bucket
        for alias in names:
            city_to_bucket[normalize_city_name(alias)] = bucket

    return {
        "zone_order": zone_order,
        "zone_labels": zone_labels,
        "highlight_countries": highlight_countries,
        "highlight_codes": list(highlight_countries.keys()),
        "china_city_order": china_city_order,
        "china_city_labels": china_city_labels,
        "country_to_zone": country_to_zone,
        "city_to_bucket": city_to_bucket,
    }


def normalize_city_name(city: str | None) -> str:
    if not city:
        return ""
    normalized = city.strip().lower()
    for suffix in (" shi", " city", " municipality"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.replace(".", "").strip()


def country_to_zone(code: str | None, country_to_zone_map: dict[str, str]) -> str:
    c = (code or "").upper()
    if not c or c in {"XX", "T1"}:
        return "other"
    return country_to_zone_map.get(c, "other")


def china_city_bucket(city: str | None, city_to_bucket_map: dict[str, str]) -> str | None:
    normalized = normalize_city_name(city)
    if not normalized:
        return None
    if normalized in city_to_bucket_map:
        return city_to_bucket_map[normalized]
    for alias, bucket in city_to_bucket_map.items():
        if normalized.startswith(alias) or alias.startswith(normalized):
            return bucket
    return None


def default_china_city_counts(china_city_order: list[str]) -> dict[str, int]:
    return {city: 0 for city in china_city_order}


def enrich_china_cities(data: dict[str, Any], maps: dict[str, Any]) -> dict[str, Any]:
    counts = data.get("china_cities") or {}
    if isinstance(counts, dict) and "counts" in counts:
        counts = counts["counts"]
    order = maps["china_city_order"]
    return {
        "order": order,
        "labels": maps["china_city_labels"],
        "counts": {city: int(counts.get(city, 0)) for city in order},
    }


def flatten_china_counts(data: dict[str, Any], maps: dict[str, Any]) -> dict[str, int]:
    china = data.get("china_cities") or {}
    if isinstance(china, dict) and "counts" in china:
        china = china["counts"]
    return {city: int(china.get(city, 0)) for city in maps["china_city_order"]}


def load_stats(raw: dict[str, Any] | None, maps: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw or {})
    data.setdefault("total", 0)
    data.setdefault("zones", {})
    for zone in maps["zone_order"]:
        data["zones"].setdefault(zone, 0)
    data.setdefault("countries", {})
    for code in maps["highlight_codes"]:
        data["countries"].setdefault(code, 0)
    flat_china = flatten_china_counts(data, maps)
    data["china_cities"] = flat_china
    data["zone_labels"] = maps["zone_labels"]
    data["zone_order"] = maps["zone_order"]
    data["highlight_countries"] = maps["highlight_countries"]
    data["china_cities"] = enrich_china_cities(data, maps)
    return data


def stats_payload(data: dict[str, Any], maps: dict[str, Any]) -> dict[str, Any]:
    china_counts = flatten_china_counts(data, maps)
    return {
        "total": int(data.get("total", 0)),
        "zones": {z: int(data.get("zones", {}).get(z, 0)) for z in maps["zone_order"]},
        "countries": {
            code: int(data.get("countries", {}).get(code, 0)) for code in maps["highlight_codes"]
        },
        "china_cities": {city: int(china_counts.get(city, 0)) for city in maps["china_city_order"]},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def record_hit(
    data: dict[str, Any],
    maps: dict[str, Any],
    country: str,
    city: str | None = None,
) -> str | None:
    zone = country_to_zone(country, maps["country_to_zone"])
    data["total"] = int(data.get("total", 0)) + 1
    data["zones"][zone] = int(data["zones"].get(zone, 0)) + 1

    china_bucket = None
    if country in maps["highlight_countries"]:
        data["countries"][country] = int(data["countries"].get(country, 0)) + 1
        if country == "CN":
            china_counts = flatten_china_counts(data, maps)
            china_bucket = china_city_bucket(city, maps["city_to_bucket"])
            if china_bucket:
                china_counts[china_bucket] = int(china_counts.get(china_bucket, 0)) + 1
            data["china_cities"] = china_counts
    return china_bucket
