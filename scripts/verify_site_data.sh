#!/usr/bin/env bash
# Compare on-disk data vs what the HTTP server returns (run while serve_site.sh is up).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${SITE_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"

echo "Repo: ${ROOT}"
echo "HTTP: ${BASE}"
echo ""

for f in today-broadcast.json top-monthly.json search-index.json arxiv-recent.json hub.json; do
  disk="${ROOT}/website/data/${f}"
  if [[ -f "$disk" ]]; then
    echo "=== disk: data/${f} ==="
    if [[ "$f" == "arxiv-recent.json" ]]; then
      grep -m1 '"fetched_at"' "$disk" || true
    else
      grep -m1 '"generated_at"' "$disk" 2>/dev/null || head -1 "$disk"
    fi
  fi
  code=$(curl -s -o /tmp/papers-hub-check.json -w "%{http_code}" "${BASE}/data/${f}?t=$(date +%s)" || echo "000")
  if [[ "$code" == "200" ]]; then
    echo "=== http: data/${f} (${code}) ==="
    if [[ "$f" == "arxiv-recent.json" ]]; then
      grep -m1 '"fetched_at"' /tmp/papers-hub-check.json || true
    else
      grep -m1 '"generated_at"' /tmp/papers-hub-check.json 2>/dev/null || true
    fi
  else
    echo "=== http: data/${f} FAILED (${code}) ù is serve_site.sh running from this repo? ==="
  fi
  echo ""
done

echo "hub.js version in index.html:"
grep -o 'hub.js?v=[^"]*' "${ROOT}/website/index.html" || true
