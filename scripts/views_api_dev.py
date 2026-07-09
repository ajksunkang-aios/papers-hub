#!/usr/bin/env python3
"""Local dev API for cumulative views by zone (mirrors workers/view-stats)."""

from __future__ import annotations

import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.view_stats import (
    build_zone_maps,
    load_stats,
    load_zones_config,
    record_hit,
    stats_payload,
)

DEFAULT_STATS = ROOT / "data" / "view-stats.json"
ZONES = load_zones_config()
MAPS = build_zone_maps(ZONES)


class Handler(BaseHTTPRequestHandler):
    stats_path = DEFAULT_STATS

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_raw_stats(self) -> dict:
        if self.stats_path.is_file():
            return json.loads(self.stats_path.read_text(encoding="utf-8"))
        return stats_payload({}, MAPS)

    def _write_raw_stats(self, data: dict) -> None:
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        self.stats_path.write_text(
            json.dumps(stats_payload(data, MAPS), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path != "/stats":
            self._json(404, {"error": "Not found"})
            return
        data = load_stats(self._read_raw_stats(), MAPS)
        self._json(200, data)

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path != "/hit":
            self._json(404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            req = {}

        country = (req.get("country") or "XX").upper()
        if self.client_address[0] in {"127.0.0.1", "::1"} and req.get("country"):
            country = str(req["country"]).upper()

        raw = self._read_raw_stats()
        zone = record_hit(raw, MAPS, country)
        self._write_raw_stats(raw)
        data = load_stats(self._read_raw_stats(), MAPS)
        self._json(
            200,
            {
                "ok": True,
                "zone": zone,
                "country": country,
                **data,
            },
        )

    def log_message(self, fmt: str, *args) -> None:
        print(f"[views-api] {self.address_string()} {fmt % args}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    stats_path = args.stats.resolve()
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    if not stats_path.is_file():
        stats_path.write_text(
            json.dumps(stats_payload({}, MAPS), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    Handler.stats_path = stats_path
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Views API on http://{args.host}:{args.port}  stats={Handler.stats_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
