#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$ROOT/data/dblp.xml.gz" ]]; then
  echo "Downloading dblp.xml.gz (first run)..."
  python3 "$ROOT/parse_dblp_xml.py" --download
fi
echo "Building conference data from dblp XML..."
python3 "$ROOT/parse_dblp_xml.py" --build-website

echo "Building 2026 conference timeline..."
python3 "$ROOT/build_conference_timeline.py"

PICK_YEARS="${PICK_YEARS:-2024,2025,2026}"
echo "Fetching arXiv papers for ${PICK_YEARS}..."
python3 "$ROOT/crawl_arxiv_recent.py" --years "$PICK_YEARS" --os-max 200 --cl-max 500

echo "Building top picks for ${PICK_YEARS}..."
python3 "$ROOT/build_top_monthly.py" --years "$PICK_YEARS"

echo "Building today's kernel/systems news ticker..."
python3 "$ROOT/build_today_broadcast.py"

echo "Starting site at http://localhost:8765/"
cd "$ROOT/website"
exec python3 -m http.server 8765
