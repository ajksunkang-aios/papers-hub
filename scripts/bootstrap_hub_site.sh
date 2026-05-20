#!/usr/bin/env bash
# Copy shared static assets into a hub's site_dir (run once for new hubs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${1:?usage: bootstrap_hub_site.sh <hub-id>}"
SITE_REL="$(python3 "$ROOT/scripts/hub_site_dir.py" "$HUB")"
SITE="$ROOT/$SITE_REL"
mkdir -p "$SITE/data"
STATIC=(
  index.html styles.css shared.js picks-ui.js hub.js
  area-picks.html area-picks.js conference.html conference.js
)
for f in "${STATIC[@]}"; do
  cp "$ROOT/website/$f" "$SITE/$f"
done
for f in today-broadcast-data.js conference-timeline-data.js; do
  if [[ -f "$ROOT/website/$f" ]]; then
    cp "$ROOT/website/$f" "$SITE/$f"
  fi
done
echo "Bootstrapped $SITE from website/ (hub=$HUB)"
echo "Run publish.sh (or build_today_broadcast.py + build_conference_timeline.py) if bundled JS is missing."
