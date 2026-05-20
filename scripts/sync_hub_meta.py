#!/usr/bin/env python3
"""Write website/data/hub.json from hubs/<id>/hub.json for the static frontend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.hub_config import add_hub_argument, load_hub  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_hub_argument(parser)
    args = parser.parse_args()
    hub = load_hub(args.hub, root=ROOT)
    hub.web_data.mkdir(parents=True, exist_ok=True)
    out = hub.site_json_path("hub.json")
    out.write_text(json.dumps(hub.frontend_meta(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
