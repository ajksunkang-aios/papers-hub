#!/usr/bin/env bash
# Full incremental affiliation enrich for local runs (2020+ by default).
#
# Order per paper: reload disk caches → dblp.xml person index → dblp HTTP → OpenAlex.
# Network calls have per-request and per-paper timeouts (see core/fetch_limits.py).
#
# Usage:
#   ./scripts/enrich_affiliations_online.sh
#   AUTHOR_ENRICH_PAPER_TIMEOUT_SEC=90 ./scripts/enrich_affiliations_online.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env_python.sh
source "$ROOT/scripts/env_python.sh"
papers_hub_setup_env

export AUTHOR_ENRICH_FULL=1
export AUTHOR_ENRICH_STALE_HOURS=0
export PICK_YEARS="${PICK_YEARS:-2020,2021,2022,2023,2024,2025,2026}"
export COUNTRY_YEARS="${COUNTRY_YEARS:-$PICK_YEARS}"

echo "=== full affiliation enrich (reload → xml → dblp HTTP → OpenAlex) ==="
echo "  PICK_YEARS=${PICK_YEARS}"
echo "  AUTHOR_ENRICH_MAX_ONLINE=${AUTHOR_ENRICH_MAX_ONLINE:-unlimited}"

exec "$ROOT/scripts/update_country_analytics.sh"
