#!/usr/bin/env bash
# Deprecated: use install_daily_schedule.sh (dblp + arXiv at 9:00 AM).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Use: $ROOT/scripts/install_daily_schedule.sh" >&2
exec "$ROOT/scripts/install_daily_schedule.sh"
