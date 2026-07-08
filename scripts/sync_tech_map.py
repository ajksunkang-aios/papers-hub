#!/usr/bin/env python3
"""Copy hubs/<id>/tech-map.json to website/data/tech-map.json."""

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
    src = hub.hub_dir / "tech-map.json"
    if not src.is_file():
        raise SystemExit(f"missing {src}")
    payload = json.loads(src.read_text(encoding="utf-8"))
    hub.web_data.mkdir(parents=True, exist_ok=True)
    out = hub.site_json_path("tech-map.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    topic_count = sum(len(g.get("topics") or []) for g in payload.get("groups") or [])
    print(f"Wrote {out}  groups={len(payload.get('groups', []))} topics={topic_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
