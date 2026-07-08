#!/usr/bin/env bash
# Local workflow: enrich country data and print git push steps.
#
# Usage:
#   ./scripts/publish_country_data.sh
#   AUTHOR_ENRICH_FULL=1 ./scripts/publish_country_data.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== enrich + build country & author analytics ==="
"$ROOT/scripts/update_analytics.sh"

echo ""
echo "Next steps:"
echo "  git add website/data/country-analytics.json website/data/author-analytics.json website/data/*.json"
echo "  git commit -m 'Update analytics data'"
echo "  git push"
echo "  # Or wait for monthly Deploy Analytics Pages workflow (1st of month)."
