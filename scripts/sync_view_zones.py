#!/usr/bin/env python3
"""Keep workers/view-stats/zones.json in sync with core/view_zones.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "core" / "view_zones.json"
DST = ROOT / "workers" / "view-stats" / "zones.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if worker zones.json is out of sync",
    )
    args = parser.parse_args()

    if not SRC.is_file():
        print(f"Missing source: {SRC}", file=sys.stderr)
        return 1

    if args.check:
        if not DST.is_file():
            print("workers/view-stats/zones.json missing; run scripts/sync_view_zones.py", file=sys.stderr)
            return 1
        if json.loads(SRC.read_text(encoding="utf-8")) != json.loads(DST.read_text(encoding="utf-8")):
            print("view zones out of sync; run scripts/sync_view_zones.py", file=sys.stderr)
            return 1
        print("view zones in sync")
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Synced {SRC.relative_to(ROOT)} -> {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
