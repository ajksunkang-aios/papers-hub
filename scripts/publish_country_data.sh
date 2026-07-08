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

echo "=== enrich + build country-analytics.json ==="
"$ROOT/scripts/update_country_analytics.sh"

echo ""
echo "Next steps:"
echo "  git add website/data/country-analytics.json website/data/*.json"
echo "  git commit -m 'Update country analytics data'"
echo "  git push   # triggers Deploy Country Pages (same site, no dblp rebuild)"
echo ""
echo "Country page: website/country-analytics.html (linked from main hub header)."
