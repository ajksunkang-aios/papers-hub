#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
hub_id = sys.argv[1]
meta = json.loads((ROOT / "hubs" / hub_id / "hub.json").read_text(encoding="utf-8"))
print(meta["paths"]["site_dir"])
