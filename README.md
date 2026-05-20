# OS Kernel Papers Hub

A static **research paper hub**: dblp conference proceedings, arXiv recent papers, categorized top picks, and a daily-style broadcast bar.

## Run (default hub)

```bash
./publish.sh
# open http://localhost:8765/
```

Requires `data/dblp.xml.gz` on first build (downloaded automatically).

**Year windows (default):** published picks `2023–2026`, arXiv picks `2025–2026`. Override with `PICK_YEARS` and `ARXIV_PICK_YEARS`.

## Site features

- **Top picks by area** — tabbed UI: published proceedings (left, default) and recent arXiv (right). **More** opens `area-picks.html` for the full list in that area.
- **Broadcast bar** — top arXiv papers from the last 7 days, scored like top picks.
- **Conference proceedings** — browse and search dblp-backed venue JSON.

## Daily arXiv refresh

```bash
./scripts/arxiv_daily.sh
# or: launchd/cron — see scripts/ for examples
```

Uses the same year windows as `publish.sh` and skips a fresh crawl when data is younger than 24h (unless the last run had feed errors).

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
