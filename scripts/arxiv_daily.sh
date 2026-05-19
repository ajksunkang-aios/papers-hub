#!/usr/bin/env bash
# Daily arXiv refresh (intended for 9:00 AM via launchd or cron).
# Uses the same year window as publish.sh so picks stay consistent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/arxiv-$(date +%Y%m%d).log"
PICK_YEARS="${PICK_YEARS:-2024,2025,2026}"

{
  echo "=== arXiv crawl $(date -Iseconds) ==="
  echo "PICK_YEARS=${PICK_YEARS}"
  cd "$ROOT"
  python3 crawl_arxiv_recent.py --years "$PICK_YEARS" --os-max 200 --cl-max 500
  python3 build_top_monthly.py --years "$PICK_YEARS"
  python3 build_today_broadcast.py
} >>"$LOG" 2>&1
