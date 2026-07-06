#!/usr/bin/env bash
# Daily data refresh: dblp (incremental) + arXiv + picks/broadcast. Does not start HTTP server.
#
# Run manually:
#   ./scripts/daily_update.sh
#   HUB=os-kernel ABSTRACT_OFFLINE=1 ./scripts/daily_update.sh
#   AUTHOR_COUNTRY_OFFLINE=1 ./scripts/daily_update.sh   # skip dblp person-page fetch
#
# Country analytics: ONLINE by default (first-author affiliations from dblp person pages).
# Schedule at 9:00 AM (server): ./scripts/install_daily_schedule.sh
# Schedule at 9:00 AM (GitHub): .github/workflows/deploy-pages.yml
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env_python.sh
source "$ROOT/scripts/env_python.sh"
papers_hub_setup_env
if [[ "${CI:-}" == "true" ]]; then
  echo "PYTHON=${PYTHON} ($("$PYTHON" --version 2>&1))"
  "$PYTHON" -c "import sys, lxml; print('lxml', lxml.__version__, 'at', sys.executable)"
fi
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-$(date +%Y%m%d).log"

HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")
PICK_YEARS="${PICK_YEARS:-2020,2021,2022,2023,2024,2025,2026}"
# Country totals use the same window unless COUNTRY_YEARS is set explicitly.
COUNTRY_YEARS="${COUNTRY_YEARS:-$PICK_YEARS}"
export COUNTRY_YEARS
ARXIV_PICK_YEARS="${ARXIV_PICK_YEARS:-2025,2026}"
ABSTRACT_ENRICH_YEARS="${ABSTRACT_ENRICH_YEARS:-2025,2026}"

run() {
  echo "=== $1 $(date -Iseconds) ==="
  shift
  "$@"
}

run_daily() {
  run "daily_update start" echo "HUB=${HUB} ROOT=${ROOT}"
  cd "$ROOT"

  if [[ "${DAILY_SKIP_DBLP:-0}" != "1" ]]; then
    if [[ ! -f "$ROOT/data/dblp.xml.gz" ]]; then
      run "dblp download" "$PYTHON" parse_dblp_xml.py "${HUB_FLAG[@]}" --download
    fi
    run "dblp build" "$PYTHON" parse_dblp_xml.py "${HUB_FLAG[@]}" --build-website --if-stale
    run "conference timeline" "$PYTHON" build_conference_timeline.py "${HUB_FLAG[@]}"
  else
    echo "=== skip dblp (DAILY_SKIP_DBLP=1) ==="
  fi

  if [[ "${DAILY_SKIP_ARXIV:-0}" != "1" ]]; then
    ARXIV_FLAGS=(--years "$ARXIV_PICK_YEARS" --os-max 120 --cl-max 180)
    if [[ "${ARXIV_FORCE:-0}" == "1" ]]; then
      ARXIV_FLAGS+=(--force)
    else
      ARXIV_FLAGS+=(--if-stale-hours 24)
    fi
    run "arxiv crawl" "$PYTHON" crawl_arxiv_recent.py "${HUB_FLAG[@]}" "${ARXIV_FLAGS[@]}"
  else
    echo "=== skip arxiv (DAILY_SKIP_ARXIV=1) ==="
  fi

  if [[ "${ABSTRACT_SKIP:-0}" == "1" ]]; then
    echo "=== skip abstracts (ABSTRACT_SKIP=1) ==="
  else
    ABSTRACT_ENRICH_FLAGS=()
    if [[ "${ABSTRACT_OFFLINE:-0}" == "1" ]]; then
      ABSTRACT_ENRICH_FLAGS+=(--offline)
    fi
    run "abstract enrich" "$PYTHON" -u enrich_conference_abstracts.py "${HUB_FLAG[@]}" \
      --years "$ABSTRACT_ENRICH_YEARS" \
      --if-stale-hours 168 \
      "${ABSTRACT_ENRICH_FLAGS[@]}"
  fi

  # Online dblp person-page affiliations by default (GitHub Pages + local).
  # Opt out: AUTHOR_ENRICH_OFFLINE=1 or AUTHOR_COUNTRY_OFFLINE=1
  # Reload: disk caches hydrate website JSON; only unresolved authors hit dblp.
  AUTHOR_ENRICH_FLAGS=(--years "$PICK_YEARS" --skip-arxiv)
  if [[ "${AUTHOR_ENRICH_ALL_AUTHORS:-0}" != "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--first-author-only)
  fi
  # Skip online fetch when caches already cover all authors (still reloads into JSON).
  AUTHOR_ENRICH_FLAGS+=(--if-stale-hours "${AUTHOR_ENRICH_STALE_HOURS:-168}")
  if [[ "${AUTHOR_ENRICH_OFFLINE:-0}" == "1" || "${AUTHOR_COUNTRY_OFFLINE:-0}" == "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--offline)
    echo "  author enrich: OFFLINE (no dblp person-page fetch)"
  elif [[ -n "${AUTHOR_ENRICH_MAX_ONLINE:-}" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--max-online-authors "$AUTHOR_ENRICH_MAX_ONLINE")
    echo "  author enrich: ONLINE dblp (reload, max_online=${AUTHOR_ENRICH_MAX_ONLINE})"
  else
    echo "  author enrich: ONLINE dblp (reload disk caches, full person-page fetch)"
  fi
  if [[ "${AUTHOR_USE_OPENALEX:-0}" == "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--openalex)
  fi
  if [[ "${AUTHOR_ENRICH_SKIP_DBLP:-0}" == "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--skip-dblp-fetch)
  fi
  if [[ "${AUTHOR_ENRICH_FORCE:-0}" == "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--force)
  fi
  if [[ "${AUTHOR_ENRICH_NO_RELOAD:-0}" == "1" ]]; then
    AUTHOR_ENRICH_FLAGS+=(--no-reload)
  fi
  run "author metadata" "$PYTHON" -u enrich_author_metadata.py "${HUB_FLAG[@]}" \
    "${AUTHOR_ENRICH_FLAGS[@]}"

  run "top picks" "$PYTHON" build_top_monthly.py "${HUB_FLAG[@]}" \
    --years "$PICK_YEARS" --arxiv-years "$ARXIV_PICK_YEARS"
  run "country analytics" env SKIP_AUTHOR_ENRICH=1 "$ROOT/scripts/update_country_analytics.sh"
  run "broadcast" "$PYTHON" build_today_broadcast.py "${HUB_FLAG[@]}"
  if [[ -f "$ROOT/website/data/today-broadcast.json" ]]; then
    echo "  broadcast generated_at: $(grep -m1 '"generated_at"' "$ROOT/website/data/today-broadcast.json" || true)"
  fi
  run "sync hub meta" "$PYTHON" scripts/sync_hub_meta.py "${HUB_FLAG[@]}"

  run "daily_update done" echo "log=${LOG}"
  echo ""
  echo "Browser: hard refresh (Ctrl+Shift+R). If still old, run: ./scripts/verify_site_data.sh"
}

echo "papers-hub daily_update → also logging to ${LOG}"
echo ""
# Show progress on the terminal and append to the daily log.
run_daily 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
