#!/usr/bin/env bash
# Install macOS launchd job: arXiv crawl every day at 9:00 AM.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/scripts/com.topconference.arxiv.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.topconference.arxiv.plist"

mkdir -p "$ROOT/logs"
chmod +x "$ROOT/scripts/arxiv_daily.sh"

sed "s|REPLACE_ROOT|$ROOT|g" "$PLIST_SRC" >"$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed: $PLIST_DST"
echo "Runs daily at 9:00 AM: $ROOT/scripts/arxiv_daily.sh"
echo "Test now: bash $ROOT/scripts/arxiv_daily.sh"
