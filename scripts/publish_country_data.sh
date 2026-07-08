#!/usr/bin/env bash
# Local workflow: enrich country data, prepare the country Pages bundle, print next steps.
#
# Usage:
#   ./scripts/publish_country_data.sh              # offline rebuild only
#   AUTHOR_ENRICH_FULL=1 ./scripts/publish_country_data.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== 1/2 enrich + build country-analytics.json ==="
"$ROOT/scripts/update_country_analytics.sh"

echo ""
echo "=== 2/2 prepare website-country/ ==="
"$ROOT/scripts/prepare_country_site.sh"

echo ""
echo "Next steps:"
echo "  git add website/data/country-analytics.json website/data/*.json"
echo "  git add website-country/index.html"
echo "  git commit -m 'Update country analytics data'"
echo "  git push   # triggers Deploy Country Pages when country-analytics.json changes"
echo ""
echo "Main site (Deploy Pages cron) does not rebuild country analytics."
