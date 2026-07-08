#!/usr/bin/env bash
# Affiliation enrich + country analytics + author analytics.
#
# Usage:
#   ./scripts/update_analytics.sh
#   AUTHOR_ENRICH_ONLINE_DBLP=1 AUTHOR_USE_OPENALEX=1 ./scripts/update_analytics.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== analytics pipeline (enrich + country + author) ==="
"$ROOT/scripts/update_country_analytics.sh"
"$ROOT/scripts/update_author_analytics.sh"
