#!/usr/bin/env bash
# Daily data refresh: dblp (incremental) + arXiv + picks/broadcast. Does not start HTTP server.
#
# Run manually:
#   ./scripts/daily_update.sh
#   HUB=os-kernel ABSTRACT_OFFLINE=1 ./scripts/daily_update.sh
#
# Schedule at 9:00 AM (server): ./scripts/install_daily_schedule.sh
# Schedule at 9:00 AM (GitHub): .github/workflows/deploy-pages.yml
#
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
PYTHON="${PYTHON:-$(command -v python3 || echo python3)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-$(date +%Y%m%d).log"

HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")
PICK_YEARS="${PICK_YEARS:-2023,2024,2025,2026}"
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
    run "arxiv crawl" "$PYTHON" crawl_arxiv_recent.py "${HUB_FLAG[@]}" \
      --years "$ARXIV_PICK_YEARS" \
      --os-max 120 --cl-max 180 \
      --if-stale-hours 24
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

  run "top picks" "$PYTHON" build_top_monthly.py "${HUB_FLAG[@]}" \
    --years "$PICK_YEARS" --arxiv-years "$ARXIV_PICK_YEARS"
  run "broadcast" "$PYTHON" build_today_broadcast.py "${HUB_FLAG[@]}"
  run "sync hub meta" "$PYTHON" scripts/sync_hub_meta.py "${HUB_FLAG[@]}"

  run "daily_update done" echo "log=${LOG}"
}

if [[ "${CI:-}" == "true" ]]; then
  run_daily 2>&1 | tee "$LOG"
else
  { run_daily; } >>"$LOG" 2>&1
fi
