import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.view_stats import (  # noqa: E402
    build_zone_maps,
    country_to_zone,
    load_stats,
    load_zones_config,
    record_hit,
    stats_payload,
)


class ViewStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.zones = load_zones_config()
        cls.maps = build_zone_maps(cls.zones)

    def test_zone_order_and_labels(self) -> None:
        self.assertEqual(
            self.maps["zone_order"],
            ["china", "americas", "europe", "asia", "oceania", "africa_me", "other"],
        )
        self.assertEqual(self.maps["zone_labels"]["china"], "China")
        self.assertEqual(self.maps["zone_labels"]["americas"], "America")
        self.assertEqual(self.maps["zone_labels"]["other"], "Others")

    def test_country_to_zone(self) -> None:
        self.assertEqual(country_to_zone("CN", self.maps["country_to_zone"]), "china")
        self.assertEqual(country_to_zone("US", self.maps["country_to_zone"]), "americas")
        self.assertEqual(country_to_zone("JP", self.maps["country_to_zone"]), "asia")
        self.assertEqual(country_to_zone("XX", self.maps["country_to_zone"]), "other")

    def test_record_hit_china_is_own_zone(self) -> None:
        data = json.loads(json.dumps(stats_payload({}, self.maps)))
        data["zones"] = {z: 0 for z in self.maps["zone_order"]}
        data["total"] = 0

        zone = record_hit(data, self.maps, "CN")
        self.assertEqual(zone, "china")
        self.assertEqual(data["zones"]["china"], 1)
        self.assertEqual(data["zones"]["asia"], 0)
        self.assertEqual(data["total"], 1)

    def test_load_stats_shape(self) -> None:
        stats = load_stats({"total": 2, "zones": {"china": 1}}, self.maps)
        self.assertEqual(stats["zone_order"][0], "china")
        self.assertNotIn("china_cities", stats)
        self.assertNotIn("highlight_countries", stats)


if __name__ == "__main__":
    unittest.main()
