# Shared Python/PATH setup for papers-hub shell scripts.
# Source after ROOT is set:  source "$ROOT/scripts/env_python.sh"; papers_hub_setup_env

papers_hub_setup_env() {
  # Do not prepend system paths — that shadows venv / setup-python on CI.
  export PATH="${PATH:-}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

  if [[ -n "${PYTHON:-}" ]]; then
    export PYTHON
    return 0
  fi

  local root="${ROOT:-}"
  if [[ -n "$root" && -x "$root/.venv/bin/python3" ]]; then
    PYTHON="$root/.venv/bin/python3"
  elif [[ -n "$root" && -x "$root/venv/bin/python3" ]]; then
    PYTHON="$root/venv/bin/python3"
  else
    local c
    PYTHON=""
    for c in python3 python; do
      if command -v "$c" >/dev/null 2>&1 && "$c" -c "import lxml" 2>/dev/null; then
        PYTHON="$(command -v "$c")"
        break
      fi
    done
    PYTHON="${PYTHON:-$(command -v python3 || echo python3)}"
  fi
  export PYTHON
}
