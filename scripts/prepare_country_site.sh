#!/usr/bin/env bash
# Assemble website-country/ from committed website assets + country-analytics.json.
#
# Usage:
#   ./scripts/prepare_country_site.sh
#   MAIN_HUB_URL=https://user.github.io/papers-hub/ ./scripts/prepare_country_site.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/website"
OUT="$ROOT/website-country"
DATA_JSON="$SRC/data/country-analytics.json"

if [[ ! -f "$DATA_JSON" ]]; then
  echo "missing $DATA_JSON — run ./scripts/update_country_analytics.sh locally first" >&2
  exit 1
fi

mkdir -p "$OUT/data"

for file in country-analytics.js shared.js views.js styles.css; do
  cp "$SRC/$file" "$OUT/$file"
done
cp "$DATA_JSON" "$OUT/data/country-analytics.json"

export MAIN_HUB_URL="${MAIN_HUB_URL:-}"
export VIEWS_API_URL="${VIEWS_API_URL:-}"
python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(".")
meta_path = root / "hubs/os-kernel/hub.json"
meta = {}
if meta_path.is_file():
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

main_hub_url = (os.environ.get("MAIN_HUB_URL") or meta.get("main_hub_url") or "").strip()
views_api_url = (os.environ.get("VIEWS_API_URL") or meta.get("views_api_url") or "").strip()
title = meta.get("title") or "OS Kernel Papers Hub"

if not main_hub_url:
    print("warning: main_hub_url not set in hubs/os-kernel/hub.json; eyebrow link may be wrong")

out = {
    "title": title,
    "main_hub_url": main_hub_url or "/",
    "views_api_url": views_api_url,
}
(root / "website-country/data/hub.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"main_hub_url={out['main_hub_url']}")
PY

BYTES=$(wc -c < "$OUT/data/country-analytics.json" | tr -d ' ')
echo "Prepared $OUT (country-analytics.json ${BYTES} bytes)"
