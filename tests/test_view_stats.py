import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.view_stats import (  # noqa: E402
    build_zone_maps,
    china_city_bucket,
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

    def test_country_to_zone(self) -> None:
        self.assertEqual(country_to_zone("CN", self.maps["country_to_zone"]), "asia")
        self.assertEqual(country_to_zone("US", self.maps["country_to_zone"]), "americas")
        self.assertEqual(country_to_zone("XX", self.maps["country_to_zone"]), "other")

    def test_china_city_bucket_aliases(self) -> None:
        bucket_map = self.maps["city_to_bucket"]
        self.assertEqual(china_city_bucket("Shanghai", bucket_map), "shanghai")
        self.assertEqual(china_city_bucket("Beijing Shi", bucket_map), "beijing")
        self.assertEqual(china_city_bucket("Guangzhou", bucket_map), "guangzhou")
        self.assertIsNone(china_city_bucket("Chengdu", bucket_map))

    def test_record_hit_tracks_china_city(self) -> None:
        data = json.loads(json.dumps(stats_payload({}, self.maps)))
        data["zones"] = {z: 0 for z in self.maps["zone_order"]}
        data["countries"] = {code: 0 for code in self.maps["highlight_codes"]}
        data["china_cities"] = {city: 0 for city in self.maps["china_city_order"]}
        data["total"] = 0

        bucket = record_hit(data, self.maps, "CN", "Hangzhou")
        self.assertEqual(bucket, "hangzhou")
        self.assertEqual(data["countries"]["CN"], 1)
        self.assertEqual(data["china_cities"]["hangzhou"], 1)

    def test_load_stats_enriched_shape(self) -> None:
        stats = load_stats({"total": 2, "countries": {"CN": 1}}, self.maps)
        self.assertIn("order", stats["china_cities"])
        self.assertIn("counts", stats["china_cities"])
        self.assertEqual(len(stats["china_cities"]["order"]), 5)


if __name__ == "__main__":
    unittest.main()
