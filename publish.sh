#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")
PICK_YEARS="${PICK_YEARS:-2023,2024,2025,2026}"
ARXIV_PICK_YEARS="${ARXIV_PICK_YEARS:-2025,2026}"

if [[ ! -f "$ROOT/data/dblp.xml.gz" ]]; then
  echo "Downloading dblp.xml.gz (first run)..."
  python3 "$ROOT/parse_dblp_xml.py" "${HUB_FLAG[@]}" --download
fi

echo "Building hub: ${HUB}"
echo "Building conference data from dblp XML (incremental)..."
python3 "$ROOT/parse_dblp_xml.py" "${HUB_FLAG[@]}" --build-website --if-stale

echo "Building conference timeline..."
python3 "$ROOT/build_conference_timeline.py" "${HUB_FLAG[@]}"

echo "Fetching arXiv papers for ${ARXIV_PICK_YEARS} (incremental, skip if fresh 24h)..."
python3 "$ROOT/crawl_arxiv_recent.py" "${HUB_FLAG[@]}" \
  --years "$ARXIV_PICK_YEARS" \
  --os-max 120 --cl-max 180 \
  --if-stale-hours 24

echo "Enriching conference paper abstracts (skip if fresh 7d)..."
python3 "$ROOT/enrich_conference_abstracts.py" "${HUB_FLAG[@]}" \
  --years "$PICK_YEARS" \
  --if-stale-hours 168

echo "Building top picks (arXiv ${ARXIV_PICK_YEARS}, published ${PICK_YEARS})..."
python3 "$ROOT/build_top_monthly.py" "${HUB_FLAG[@]}" --years "$PICK_YEARS" --arxiv-years "$ARXIV_PICK_YEARS"

echo "Building recent broadcast ticker..."
python3 "$ROOT/build_today_broadcast.py" "${HUB_FLAG[@]}"

echo "Syncing frontend hub metadata..."
python3 "$ROOT/scripts/sync_hub_meta.py" "${HUB_FLAG[@]}"

SITE_DIR="$(python3 "$ROOT/scripts/hub_site_dir.py" "$HUB")"
SITE_DIR="$ROOT/$SITE_DIR"
echo "Starting site at http://localhost:8765/ (${HUB})"
cd "$SITE_DIR"
exec python3 -m http.server 8765
