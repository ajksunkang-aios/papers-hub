#!/usr/bin/env bash
# Back-compat wrapper: arXiv-only daily job. Prefer scripts/daily_update.sh (dblp + arXiv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DAILY_SKIP_DBLP=1
exec "$ROOT/scripts/daily_update.sh"
