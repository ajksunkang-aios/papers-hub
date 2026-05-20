#!/usr/bin/env bash
# Copy shared static assets into a hub's site_dir (run once for new hubs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${1:?usage: bootstrap_hub_site.sh <hub-id>}"
SITE_REL="$(python3 "$ROOT/scripts/hub_site_dir.py" "$HUB")"
SITE="$ROOT/$SITE_REL"
mkdir -p "$SITE/data"
for f in index.html styles.css shared.js hub.js conference.html conference.js; do
  cp "$ROOT/website/$f" "$SITE/$f"
done
echo "Bootstrapped $SITE from website/ (hub=$HUB)"
