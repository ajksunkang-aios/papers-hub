# OS Kernel Papers Hub

A static **research paper hub**: dblp conference proceedings, arXiv recent papers, categorized top picks, and a daily-style broadcast bar.

## Run (default hub)

```bash
./publish.sh
# open http://127.0.0.1:8765/
```

**Default HTTP port is `8765`, not 80.** Port 80 is only used if you set `SITE_PORT=80` (requires root on Linux).

| Goal | Command |
|------|---------|
| Default local preview | `./publish.sh` ? **8765** |
| Custom port | `SITE_PORT=8080 ./publish.sh` |
| Port 80 on a server | `NO_SERVE=1 ./publish.sh` then `sudo -E env SITE_PORT=80 SITE_BIND=0.0.0.0 ./scripts/serve_site.sh` |
| Build only (no server) | `NO_SERVE=1 ./publish.sh` |

Confirm what is listening:

```bash
ss -tlnp | grep python
curl -sI http://127.0.0.1:8765/ | head -1
```

Requires `data/dblp.xml.gz` on first build (downloaded automatically).

**Year windows (default):** published picks `2023-2026`, arXiv picks `2025-2026`. Override with `PICK_YEARS` and `ARXIV_PICK_YEARS`.

**Abstract enrichment** during `publish.sh` defaults to years `2025,2026` only. Full backfill: `ABSTRACT_ENRICH_YEARS=2023,2024,2025,2026 ./publish.sh`. Skip: `ABSTRACT_SKIP=1`.

## Deploy on a Linux server (from scratch)

**[docs/DEPLOY.md](docs/DEPLOY.md)** — full steps: clone, venv, first build, HTTP server, cron 9:00 AM.
**[docs/LINUX_SERVER.md](docs/LINUX_SERVER.md)** — short reference.


## Daily automatic update (9:00 AM)

Refreshes dblp + arXiv + picks (does **not** restart the HTTP server).

```bash
./scripts/install_daily_schedule.sh          # Linux: cron
SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
./scripts/daily_update.sh                    # test once
```

Remove cron: `crontab -e` and delete the `os-kernel-papers-hub` lines.

## Site features

- **Top picks by area** � published proceedings (left, default) and recent arXiv (right). **More** opens `area-picks.html`.
- **Broadcast bar** � top arXiv papers from the last 7 days.
- **Conference proceedings** � browse and search dblp-backed venue JSON.

## Multiple research areas

Configuration lives under `hubs/<hub-id>/`. See **[docs/ADDING_A_HUB.md](docs/ADDING_A_HUB.md)**.

```bash
HUB=compiler ./publish.sh
```

## Repository map

| Path | Role |
|------|------|
| `hubs/os-kernel/` | Hub config (venues, keywords, timeline) |
| `website/` | Built site for os-kernel |
| `scripts/serve_site.sh` | Static HTTP server (`SITE_PORT`, default **8765**) |
| `scripts/daily_update.sh` | Daily dblp + arXiv refresh |
| `scripts/install_daily_schedule.sh` | Install 9:00 AM cron (Linux) |
| `publish.sh` | Full pipeline (`HUB=` env) |
