#!/usr/bin/env bash
# Install daily 9:00 AM job (Linux: cron by default, optional systemd timer).
#
#   ./scripts/install_daily_schedule.sh
#   SCHEDULE_METHOD=systemd ./scripts/install_daily_schedule.sh
#   SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
#
# Env:
#   SCHEDULE_HOUR=9  SCHEDULE_MINUTE=0  SCHEDULE_TZ=Asia/Shanghai  HUB=os-kernel
#   SCHEDULE_METHOD=cron|systemd  (Linux only; default cron)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${HUB:-os-kernel}"
HOUR="${SCHEDULE_HOUR:-9}"
MINUTE="${SCHEDULE_MINUTE:-0}"
TZ_NAME="${SCHEDULE_TZ:-}"
METHOD="${SCHEDULE_METHOD:-cron}"
JOB_SCRIPT="$ROOT/scripts/daily_update.sh"
LABEL="papers-hub-daily"
CRON_TAG="# papers-hub daily (${HUB})"
LEGACY_CRON_TAG="os-kernel-papers-hub"
SYSTEMD_DIR="${SYSTEMD_DIR:-$HOME/.config/systemd/user}"

chmod +x "$ROOT/scripts/daily_update.sh" "$ROOT/scripts/arxiv_daily.sh"
mkdir -p "$ROOT/logs" "$SYSTEMD_DIR"

if [[ ! -x "$JOB_SCRIPT" ]]; then
  echo "Missing $JOB_SCRIPT" >&2
  exit 1
fi

install_cron() {
  local cron_line tz_prefix=""
  if [[ -n "$TZ_NAME" ]]; then
    tz_prefix="CRON_TZ=${TZ_NAME}
"
  fi
  local python_env=""
  if [[ -x "${ROOT}/.venv/bin/python3" ]]; then
    python_env="PYTHON=${ROOT}/.venv/bin/python3 "
  elif [[ -x "${ROOT}/venv/bin/python3" ]]; then
    python_env="PYTHON=${ROOT}/venv/bin/python3 "
  fi
  cron_line="${tz_prefix}${MINUTE} ${HOUR} * * * PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin cd ${ROOT} && ${python_env}HUB=${HUB} ABSTRACT_OFFLINE=1 /bin/bash ${JOB_SCRIPT} >> ${ROOT}/logs/cron-daily.log 2>&1"
  local tmp
  tmp="$(mktemp)"
  (crontab -l 2>/dev/null | grep -v "$CRON_TAG" | grep -v "$LEGACY_CRON_TAG" | grep -v "$JOB_SCRIPT" || true) >"$tmp"
  {
    cat "$tmp"
    echo "$CRON_TAG"
    echo "$cron_line"
  } | crontab -
  rm -f "$tmp"
  echo "Installed user crontab (Linux):"
  echo "  $cron_line"
  echo "  crontab -l | grep papers-hub"
}

install_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found; use SCHEDULE_METHOD=cron" >&2
    exit 1
  fi
  local on_calendar
  if [[ -n "$TZ_NAME" ]]; then
    on_calendar="*-*-* ${HOUR}:$(printf '%02d' "$MINUTE"):00 ${TZ_NAME}"
  else
    on_calendar="*-*-* ${HOUR}:$(printf '%02d' "$MINUTE"):00"
  fi
  local svc="$SYSTEMD_DIR/${LABEL}.service"
  local tmr="$SYSTEMD_DIR/${LABEL}.timer"
  sed -e "s|@ROOT@|${ROOT}|g" -e "s|@HUB@|${HUB}|g" \
    "$ROOT/scripts/systemd/papers-hub-daily.service.in" >"$svc"
  sed -e "s|@ON_CALENDAR@|${on_calendar}|g" \
    "$ROOT/scripts/systemd/papers-hub-daily.timer.in" >"$tmr"
  systemctl --user daemon-reload
  systemctl --user enable --now "${LABEL}.timer"
  echo "Installed systemd user timer:"
  echo "  $tmr"
  echo "  systemctl --user status ${LABEL}.timer"
  echo "  systemctl --user list-timers | grep ${LABEL}"
  if ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q yes; then
    echo ""
    echo "Tip: enable linger so the timer runs when you are not logged in:"
    echo "  sudo loginctl enable-linger $(id -un)"
  fi
}

install_launchd() {
  local plist_dst="$HOME/Library/LaunchAgents/com.papers-hub.daily.plist"
  local tz_block=""
  if [[ -n "$TZ_NAME" ]]; then
    tz_block="    <key>TimeZone</key>
    <string>${TZ_NAME}</string>
"
  fi
  cat >"$plist_dst" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.papers-hub.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${JOB_SCRIPT}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HUB</key>
    <string>${HUB}</string>
    <key>ABSTRACT_OFFLINE</key>
    <string>1</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>${HOUR}</integer>
    <key>Minute</key>
    <integer>${MINUTE}</integer>
  </dict>
${tz_block}  <key>StandardOutPath</key>
  <string>${ROOT}/logs/daily-launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/daily-launchd.err.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/com.papers-hub.daily" 2>/dev/null || launchctl unload "$plist_dst" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist_dst" 2>/dev/null || launchctl load "$plist_dst"
  echo "Installed launchd: $plist_dst"
}

echo "OS: $(uname -s)"
echo "Hub: ${HUB}"
echo "Schedule: ${HOUR}:$(printf '%02d' "$MINUTE")${TZ_NAME:+ (${TZ_NAME})}"
echo "Job: ${JOB_SCRIPT}"
echo ""

case "$(uname -s)" in
  Linux)
    case "$METHOD" in
      cron) install_cron ;;
      systemd) install_systemd ;;
      *)
        echo "Unknown SCHEDULE_METHOD=${METHOD} (use cron or systemd)" >&2
        exit 1
        ;;
    esac
    ;;
  Darwin) install_launchd ;;
  *)
    echo "Add manually to crontab:" >&2
    echo "0 9 * * * cd ${ROOT} && HUB=${HUB} ${JOB_SCRIPT}" >&2
    exit 1
    ;;
esac

echo ""
echo "Test now:  HUB=${HUB} ${JOB_SCRIPT}"
echo "Logs:      tail -f ${ROOT}/logs/daily-\$(date +%Y%m%d).log"
