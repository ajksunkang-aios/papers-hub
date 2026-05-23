#!/usr/bin/env bash
# Rebuild "Recent top kernel & system LLM paper" from website/data/arxiv-recent.json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env_python.sh
source "$ROOT/scripts/env_python.sh"
papers_hub_setup_env
cd "$ROOT"
HUB="${HUB:-os-kernel}"

echo "Rebuilding today-broadcast from arxiv-recent.json (hub=${HUB})..."
"$PYTHON" build_today_broadcast.py --hub "$HUB"
echo ""
grep -E '"generated_at"|"date_label"|"total_count"' "$ROOT/website/data/today-broadcast.json" | head -5
echo ""
echo "Reload the site in your browser (Ctrl+Shift+R). No HTTP server restart needed."
