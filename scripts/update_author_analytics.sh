#!/usr/bin/env bash
# Build website/data/author-analytics.json from dblp conference JSON.
#
# Usage:
#   ./scripts/update_author_analytics.sh
#   PICK_YEARS=2020,2021,2022,2023,2024,2025,2026 ./scripts/update_author_analytics.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env_python.sh
source "$ROOT/scripts/env_python.sh"
papers_hub_setup_env

HUB="${HUB:-os-kernel}"
YEARS="${AUTHOR_ANALYTICS_YEARS:-${PICK_YEARS:-2020,2021,2022,2023,2024,2025,2026}}"

cd "$ROOT"
"$PYTHON" build_author_analytics.py --hub "$HUB" --years "$YEARS"

OUT="$ROOT/website/data/author-analytics.json"
"$PYTHON" - <<'PY'
import json
from pathlib import Path

path = Path("website/data/author-analytics.json")
data = json.loads(path.read_text(encoding="utf-8"))
for key in ("generated_at", "authors", "coverage", "category_labels"):
    if key not in data:
        raise SystemExit(f"author-analytics.json missing {key!r}")
cov = data["coverage"]
print(
    f"author analytics ok: papers={cov.get('total_papers')} "
    f"unique_authors={cov.get('unique_authors')} top={len(data.get('authors', []))}"
)
if data.get("authors"):
    top = data["authors"][0]
    print(f"  #1 {top.get('name')} ({top.get('paper_count')} papers)")
PY
