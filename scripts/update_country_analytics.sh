#!/usr/bin/env bash
# Enrich dblp author affiliations and rebuild country-analytics.json.
#
# Usage:
#   ./scripts/update_country_analytics.sh
#   AUTHOR_COUNTRY_OFFLINE=1 ./scripts/update_country_analytics.sh   # local fast build only
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env_python.sh
source "$ROOT/scripts/env_python.sh"
papers_hub_setup_env

HUB="${HUB:-os-kernel}"
HUB_FLAG=(--hub "$HUB")
# Author enrich + country analytics default to 2020–present (override via env).
PICK_YEARS="${PICK_YEARS:-2020,2021,2022,2023,2024,2025,2026}"
# Country analytics totals the same window (not full historical dump).
COUNTRY_YEARS="${COUNTRY_YEARS:-2020,2021,2022,2023,2024,2025,2026}"

cd "$ROOT"

if [[ ! -f "$ROOT/website/data/conferences.json" ]]; then
  echo "=== dblp build (conferences.json missing) ==="
  if [[ ! -f "$ROOT/data/dblp.xml.gz" ]]; then
    "$PYTHON" parse_dblp_xml.py "${HUB_FLAG[@]}" --download
  fi
  "$PYTHON" parse_dblp_xml.py "${HUB_FLAG[@]}" --build-website --if-stale
fi

AUTHOR_ENRICH_FLAGS=(--years "$PICK_YEARS" --skip-arxiv)
# Country analytics only needs first-author country; full author enrich is opt-in.
if [[ "${AUTHOR_ENRICH_ALL_AUTHORS:-0}" != "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--first-author-only)
fi
AUTHOR_ENRICH_FLAGS+=(--if-stale-hours "${AUTHOR_ENRICH_STALE_HOURS:-168}")
if [[ -n "${AUTHOR_ENRICH_MAX_ONLINE:-}" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--max-online-authors "$AUTHOR_ENRICH_MAX_ONLINE")
fi
if [[ "${AUTHOR_ENRICH_SKIP_DBLP:-0}" == "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--skip-dblp-fetch)
fi
if [[ "${AUTHOR_ENRICH_FORCE:-0}" == "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--force)
fi
if [[ "${AUTHOR_ENRICH_NO_RELOAD:-0}" == "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--no-reload)
fi
if [[ "${AUTHOR_ENRICH_OFFLINE:-0}" == "1" || "${AUTHOR_COUNTRY_OFFLINE:-0}" == "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--offline)
fi
if [[ "${AUTHOR_USE_OPENALEX:-0}" == "1" ]]; then
  AUTHOR_ENRICH_FLAGS+=(--openalex)
fi
if [[ "${SKIP_AUTHOR_ENRICH:-0}" != "1" ]]; then
  echo "=== author metadata (dblp affiliations) ==="
  "$PYTHON" -u enrich_author_metadata.py "${HUB_FLAG[@]}" "${AUTHOR_ENRICH_FLAGS[@]}"
fi

ANALYTICS_FLAGS=(--years "$COUNTRY_YEARS")
if [[ "${AUTHOR_USE_OPENALEX:-0}" == "1" ]]; then
  ANALYTICS_FLAGS+=(--openalex)
fi
if [[ "${AUTHOR_COUNTRY_FORCE:-0}" == "1" ]]; then
  ANALYTICS_FLAGS+=(--force)
fi

echo "=== country analytics (years=${COUNTRY_YEARS}) ==="
"$PYTHON" build_country_analytics.py "${HUB_FLAG[@]}" "${ANALYTICS_FLAGS[@]}"

OUT="$ROOT/website/data/country-analytics.json"
if [[ ! -f "$OUT" ]]; then
  echo "missing $OUT" >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import json
from pathlib import Path

path = Path("website/data/country-analytics.json")
data = json.loads(path.read_text(encoding="utf-8"))
for key in ("generated_at", "data_source", "countries", "coverage"):
    if key not in data:
        raise SystemExit(f"country-analytics.json missing {key!r}")
cov = data["coverage"]
print(
    f"country analytics ok: source={data.get('data_source')} "
    f"papers={cov.get('total_papers')} resolved={cov.get('resolved')} "
    f"countries={len(data.get('countries', []))}"
)
PY
