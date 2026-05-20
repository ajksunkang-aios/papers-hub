# OS Kernel Papers Hub

A static **research paper hub**: dblp conference proceedings, arXiv recent papers, categorized top picks, and a daily-style broadcast bar.

## Run (default hub)

```bash
./publish.sh
# open http://localhost:8765/
```

Requires `data/dblp.xml.gz` on first build (downloaded automatically).

## Multiple research areas

Configuration lives under `hubs/<hub-id>/`. See **[docs/ADDING_A_HUB.md](docs/ADDING_A_HUB.md)** for creating a compiler hub, security hub, etc.

```bash
HUB=compiler ./publish.sh
```

## Repository map

| Path | Role |
|------|------|
| `hubs/os-kernel/` | OS/kernel hub config (venues, keywords, timeline) |
| `website/` | Built site for os-kernel |
| `core/` | Hub loader + shared scoring |
| `parse_dblp_xml.py` | Stream dblp ? per-conference JSON |
| `crawl_arxiv_recent.py` | arXiv feeds (hub-specific) |
| `publish.sh` | Full pipeline (`HUB=` env) |
