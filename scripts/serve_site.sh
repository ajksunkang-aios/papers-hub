#!/usr/bin/env bash
# Serve a hub's static site (used by publish.sh and for manual preview).
#
#   ./scripts/serve_site.sh              # hub=os-kernel, port=8765
#   SITE_PORT=8080 ./scripts/serve_site.sh
#   sudo SITE_PORT=80 ./scripts/serve_site.sh os-kernel   # port < 1024 needs root
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${1:-${HUB:-os-kernel}}"
PORT="${SITE_PORT:-${PORT:-8765}}"
BIND="${SITE_BIND:-127.0.0.1}"

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid SITE_PORT/PORT=${PORT} (use 1-65535)" >&2
  exit 1
fi

if (( PORT < 1024 )) && [[ "$(id -u)" -ne 0 ]]; then
  cat >&2 <<EOF
Cannot bind to port ${PORT}: privileged ports (< 1024) require root on macOS/Linux.

Options:
  SITE_PORT=8765 ./scripts/serve_site.sh ${HUB}
  sudo -E env HUB=${HUB} SITE_PORT=80 SITE_BIND=0.0.0.0 ${ROOT}/scripts/serve_site.sh ${HUB}

Or keep port 8765 and forward 80 -> 8765 with your router or reverse proxy.
EOF
  exit 1
fi

SITE_DIR="$(python3 "$ROOT/scripts/hub_site_dir.py" "$HUB")"
SITE_DIR="$ROOT/$SITE_DIR"
if [[ ! -d "$SITE_DIR" ]]; then
  echo "Site directory not found: ${SITE_DIR} (run publish.sh or bootstrap first)" >&2
  exit 1
fi

echo "Serving ${HUB} at http://${BIND}:${PORT}/"
echo "  directory: ${SITE_DIR}"
cd "$SITE_DIR"
exec python3 -m http.server "$PORT" --bind "$BIND"
