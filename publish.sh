#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")
PICK_YEARS="${PICK_YEARS:-2023,2024,2025,2026}"
ARXIV_PICK_YEARS="${ARXIV_PICK_YEARS:-2025,2026}"
# Abstract enrichment is slow on first run; default to recent proceedings only.
ABSTRACT_ENRICH_YEARS="${ABSTRACT_ENRICH_YEARS:-2025,2026}"

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

if [[ "${ABSTRACT_SKIP:-0}" == "1" ]]; then
  echo "Skipping abstract enrichment (ABSTRACT_SKIP=1)"
else
  echo "Enriching conference abstracts for ${ABSTRACT_ENRICH_YEARS} (skip if fresh 7d; may take a while on first run)..."
  echo "  Full backfill: ABSTRACT_ENRICH_YEARS=${PICK_YEARS} ./publish.sh"
  echo "  Skip entirely: ABSTRACT_SKIP=1 ./publish.sh"
  echo "  Restricted LAN (no external APIs): ABSTRACT_OFFLINE=1 ./publish.sh"
  ABSTRACT_ENRICH_FLAGS=()
  if [[ "${ABSTRACT_OFFLINE:-0}" == "1" ]]; then
    ABSTRACT_ENRICH_FLAGS+=(--offline)
  fi
  python3 -u "$ROOT/enrich_conference_abstracts.py" "${HUB_FLAG[@]}" \
    --years "$ABSTRACT_ENRICH_YEARS" \
    --if-stale-hours 168 \
    "${ABSTRACT_ENRICH_FLAGS[@]}"
fi

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
