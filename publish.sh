#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")

if [[ ! -f "$ROOT/data/dblp.xml.gz" ]]; then
  echo "Downloading dblp.xml.gz (first run)..."
  python3 "$ROOT/parse_dblp_xml.py" "${HUB_FLAG[@]}" --download
fi

echo "Building hub: ${HUB}"
echo "Building conference data from dblp XML..."
python3 "$ROOT/parse_dblp_xml.py" "${HUB_FLAG[@]}" --build-website

echo "Building conference timeline..."
python3 "$ROOT/build_conference_timeline.py" "${HUB_FLAG[@]}"

PICK_YEARS="${PICK_YEARS:-2024,2025,2026}"
echo "Fetching arXiv papers for ${PICK_YEARS}..."
python3 "$ROOT/crawl_arxiv_recent.py" "${HUB_FLAG[@]}" --years "$PICK_YEARS" --os-max 200 --cl-max 500

echo "Building top picks for ${PICK_YEARS}..."
python3 "$ROOT/build_top_monthly.py" "${HUB_FLAG[@]}" --years "$PICK_YEARS"

echo "Building recent broadcast ticker..."
python3 "$ROOT/build_today_broadcast.py" "${HUB_FLAG[@]}"

echo "Syncing frontend hub metadata..."
python3 "$ROOT/scripts/sync_hub_meta.py" "${HUB_FLAG[@]}"

SITE_DIR="$(python3 "$ROOT/scripts/hub_site_dir.py" "$HUB")"
SITE_DIR="$ROOT/$SITE_DIR"
echo "Starting site at http://localhost:8765/ (${HUB})"
cd "$SITE_DIR"
exec python3 -m http.server 8765
