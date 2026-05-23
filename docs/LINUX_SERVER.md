# Linux server setup

## 1. One-time build

```bash
cd /path/to/papers-hub
NO_SERVE=1 ./publish.sh
```

## 2. HTTP server (keep running)

```bash
# unprivileged port
SITE_PORT=8080 ./scripts/serve_site.sh

# port 80 (requires root)
sudo -E env SITE_PORT=80 SITE_BIND=0.0.0.0 ./scripts/serve_site.sh
```

Use **systemd**, **screen**, or **tmux** so the server survives logout.

Example systemd user service for the site (optional):

```ini
# ~/.config/systemd/user/papers-hub-web.service
[Unit]
Description=Papers Hub static site

[Service]
WorkingDirectory=/path/to/papers-hub
Environment=SITE_PORT=8080
Environment=SITE_BIND=0.0.0.0
ExecStart=/path/to/papers-hub/scripts/serve_site.sh
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now papers-hub-web.service
```

## 3. Daily refresh at 9:00 AM (cron, recommended)

```bash
./scripts/install_daily_schedule.sh
```

9:00 AM in China time:

```bash
SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
```

Verify:

```bash
crontab -l | grep papers-hub
./scripts/daily_update.sh
tail -f logs/daily-$(date +%Y%m%d).log
```

The daily job updates `website/data/` only; it does **not** restart the HTTP server.

## 4. Alternative: systemd timer

```bash
SCHEDULE_METHOD=systemd SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
systemctl --user list-timers
```

Allow the timer when not logged in:

```bash
sudo loginctl enable-linger "$USER"
```

## 5. Environment flags

| Variable | Purpose |
|----------|---------|
| `ABSTRACT_OFFLINE=1` | No external abstract APIs (default in cron) |
| `ABSTRACT_SKIP=1` | Skip abstract enrichment |
| `HUB=os-kernel` | Hub id |

## 6. Logs

| File | Content |
|------|---------|
| `logs/daily-YYYYMMDD.log` | Full daily pipeline |
| `logs/cron-daily.log` | Cron stderr/stdout wrapper |
