"""Load per-research-area hub configuration from hubs/<id>/."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def pairs_from_json(rows: list[list[Any]]) -> list[tuple[str, int]]:
    return [(str(a), int(b)) for a, b in rows]


def set_from_json(items: list[str]) -> set[str]:
    return set(items)


@dataclass(frozen=True)
class Hub:
    id: str
    root: Path
    hub_dir: Path
    site_dir: Path
    web_data: Path
    dblp_xml: Path
    meta: dict[str, Any]
    venues_raw: dict[str, Any]
    categories: dict[str, Any]
    arxiv_policy: dict[str, Any]
    timeline: dict[str, Any]

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.id))

    @property
    def venue_order(self) -> list[str]:
        return list(self.meta.get("venue_order", []))

    @property
    def pick_years(self) -> list[int]:
        return [int(y) for y in self.meta.get("pick_years", [])]

    @property
    def arxiv_pick_years(self) -> list[int]:
        from_cats = self.categories.get("arxiv_pick_years")
        if from_cats:
            return [int(y) for y in from_cats]
        return [int(y) for y in self.meta.get("arxiv_pick_years", [])]

    @property
    def sections(self) -> dict[str, Any]:
        return dict(self.meta.get("sections", {}))

    @property
    def sys_keywords(self) -> list[tuple[str, int]]:
        return pairs_from_json(self.arxiv_policy["sys_keywords"])

    @property
    def sys_strong(self) -> set[str]:
        return set_from_json(self.arxiv_policy["sys_strong"])

    @property
    def cl_keywords(self) -> list[tuple[str, int]]:
        return pairs_from_json(self.arxiv_policy["cl_keywords"])

    @property
    def cl_strong(self) -> set[str]:
        return set_from_json(self.arxiv_policy["cl_strong"])

    @property
    def os_gate_keywords(self) -> list[str]:
        return list(self.arxiv_policy["os_gate_keywords"])

    @property
    def llm_systems_keywords(self) -> list[str]:
        return list(self.arxiv_policy.get("llm_systems_keywords", []))

    @property
    def noise_primary_categories(self) -> frozenset[str]:
        return frozenset(self.arxiv_policy.get("noise_primary_categories", []))

    @property
    def broadcast_policy(self) -> dict[str, Any]:
        return dict(self.arxiv_policy.get("broadcast", {}))

    @property
    def broadcast_keywords(self) -> list[tuple[str, int]]:
        return pairs_from_json(self.broadcast_policy.get("keywords", []))

    @property
    def broadcast_strong(self) -> set[str]:
        return set_from_json(self.broadcast_policy.get("strong", []))

    @property
    def category_rows(self) -> list[dict[str, Any]]:
        rows = []
        for c in self.categories.get("categories", []):
            rows.append(
                {
                    "id": c["id"],
                    "label": c["label"],
                    "keywords": pairs_from_json(c["keywords"]),
                }
            )
        return rows

    def site_json_path(self, name: str) -> Path:
        return self.web_data / name

    def site_js_path(self, name: str) -> Path:
        return self.site_dir / name

    def frontend_meta(self) -> dict[str, Any]:
        """Subset copied to website/data/hub.json for the static UI."""
        return {
            "id": self.id,
            "title": self.title,
            "tagline": self.meta.get("tagline", ""),
            "tagline_timezone": self.meta.get("tagline_timezone", "UTC+8"),
            "lede": self.meta.get("lede", ""),
            "venue_order": self.venue_order,
            "pick_years": self.pick_years,
            "arxiv_pick_years": self.arxiv_pick_years,
            "timeline_year": self.meta.get("timeline_year"),
            "views_api_url": self.meta.get("views_api_url", ""),
            "country_analytics_url": self.meta.get("country_analytics_url", ""),
            "author_analytics_url": self.meta.get("author_analytics_url", ""),
            "main_hub_url": self.meta.get("main_hub_url", ""),
            "sections": self.sections,
            "categories": {
                "section_heading": self.categories.get("section_heading", ""),
                "arxiv_mode_label": self.categories.get("arxiv_mode_label", ""),
                "published_mode_label": self.categories.get("published_mode_label", ""),
            },
            "arxiv": {
                "filter_note": self.arxiv_policy.get("filter_note", ""),
                "broadcast_note": self.broadcast_policy.get("note", ""),
            },
        }


def load_hub(hub_id: str, *, root: Path | None = None) -> Hub:
    root = root or REPO_ROOT
    hub_dir = root / "hubs" / hub_id
    if not hub_dir.is_dir():
        raise FileNotFoundError(f"Hub not found: {hub_dir}")

    meta = json.loads((hub_dir / "hub.json").read_text(encoding="utf-8"))
    paths = meta.get("paths", {})
    site_dir = (root / paths.get("site_dir", "website")).resolve()
    dblp_xml = (root / paths.get("dblp_xml", "data/dblp.xml.gz")).resolve()

    return Hub(
        id=hub_id,
        root=root,
        hub_dir=hub_dir,
        site_dir=site_dir,
        web_data=site_dir / "data",
        dblp_xml=dblp_xml,
        meta=meta,
        venues_raw=json.loads((hub_dir / "venues.json").read_text(encoding="utf-8")),
        categories=json.loads((hub_dir / "categories.json").read_text(encoding="utf-8")),
        arxiv_policy=json.loads((hub_dir / "arxiv_policy.json").read_text(encoding="utf-8")),
        timeline=json.loads((hub_dir / "conference_timeline.json").read_text(encoding="utf-8")),
    )


def add_hub_argument(parser: argparse.ArgumentParser, *, default: str = "os-kernel") -> None:
    parser.add_argument(
        "--hub",
        default=default,
        help=f"Hub id under hubs/ (default: {default})",
    )


def resolve_hub_from_args(args: argparse.Namespace, *, root: Path | None = None) -> Hub:
    return load_hub(getattr(args, "hub", "os-kernel"), root=root)


def sync_legacy_root_configs(hub: Hub) -> None:
    """Keep root-level venues.json in sync for older tooling."""
    legacy = hub.root / "venues.json"
    src = hub.hub_dir / "venues.json"
    if src.read_bytes() != legacy.read_bytes():
        legacy.write_bytes(src.read_bytes())
