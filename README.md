# OS Kernel Papers Hub

A static **research paper hub**: dblp conference proceedings, arXiv recent papers, categorized top picks, and a daily-style broadcast bar.

## Run (default hub)

```bash
./publish.sh
# open http://127.0.0.1:8765/  (default SITE_PORT)
```

**Custom port** (ports below 1024 need root):

```bash
SITE_PORT=8080 ./publish.sh
sudo -E env SITE_PORT=80 SITE_BIND=0.0.0.0 ./scripts/serve_site.sh
```

Build without starting the server: `NO_SERVE=1 ./publish.sh`

Requires `data/dblp.xml.gz` on first build (downloaded automatically).

**Year windows (default):** published picks `2023�2026`, arXiv picks `2025�2026`. Override with `PICK_YEARS` and `ARXIV_PICK_YEARS`.

## Site features

- **Top picks by area** � tabbed UI: published proceedings (left, default) and recent arXiv (right). **More** opens `area-picks.html` for the full list in that area.
- **Broadcast bar** � top arXiv papers from the last 7 days, scored like top picks.
- **Conference proceedings** � browse and search dblp-backed venue JSON.

## Daily automatic update (9:00 AM)

Refreshes **dblp** (incremental), **arXiv**, picks, and broadcast. Does not restart the HTTP server.

```bash
./scripts/install_daily_schedule.sh
SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
./scripts/daily_update.sh
```

Keep HTTP serving running separately (`./scripts/serve_site.sh`). Logs: `logs/daily-YYYYMMDD.log`, `logs/cron-daily.log`.

## Multiple research areas

Configuration lives under `hubs/<hub-id>/`. See **[docs/ADDING_A_HUB.md](docs/ADDING_A_HUB.md)** for creating a compiler hub, security hub, etc.

```bash
HUB=compiler ./publish.sh
```

Bootstrap static assets for a new hub site:

```bash
./scripts/bootstrap_hub_site.sh <hub-id>
./publish.sh  # generates data + bundled timeline/broadcast JS
```

## Repository map

| Path | Role |
|------|------|
| `hubs/os-kernel/` | OS/kernel hub config (venues, keywords, timeline) |
| `website/` | Built site for os-kernel |
| `core/` | Hub loader, incremental manifests, shared scoring |
| `parse_dblp_xml.py` | Stream dblp ? per-conference JSON |
| `crawl_arxiv_recent.py` | arXiv feeds (incremental, rate-limit aware) |
| `build_top_monthly.py` | `top-monthly.json`, `top-published.json` |
| `publish.sh` | Full pipeline (`HUB=` env) |
