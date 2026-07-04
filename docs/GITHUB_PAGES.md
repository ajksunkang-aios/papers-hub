# GitHub Pages + scheduled builds

The workflow [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) replaces a server cron job: it runs the same pipeline as `scripts/daily_update.sh` and publishes `website/` to GitHub Pages.

## One-time setup

1. Push the repo to GitHub.
2. **Settings ? Pages ? Build and deployment ? Source:** choose **GitHub Actions**.
3. (Optional) Wait for the first workflow run, or trigger **Actions ? Deploy Pages ? Run workflow**.

Site URL: `https://<user>.github.io/<repo>/` (or your custom domain).

## Schedule

| Event | When |
|-------|------|
| `cron: "0 1 * * *"` | **09:00 Asia/Shanghai** (01:00 UTC) daily |
| `workflow_dispatch` | Manual run from the Actions tab |
| `push` to `main` | Rebuild when code/config changes (path filters apply) |

To change timezone, edit the cron line in the workflow (GitHub Actions always uses UTC in `cron`).

## What the workflow runs

Same as local daily update:

- dblp parse (incremental, cached `data/dblp.xml.gz`)
- arXiv crawl (`--if-stale-hours 24`)
- top picks + broadcast + hub metadata  
- **country analytics** (`scripts/update_country_analytics.sh` → `website/data/country-analytics.json`)

CI defaults: `ABSTRACT_SKIP=1` (faster; enable in workflow env if you add abstract APIs later).  
Author country: `AUTHOR_COUNTRY_OFFLINE=1` skips OpenAlex; dblp person-page fetch still runs when cached data is stale.

Dedicated workflow: [`.github/workflows/country-analytics.yml`](../.github/workflows/country-analytics.yml) warms author-enrichment caches daily at **08:00 Asia/Shanghai** (one hour before Deploy Pages).

To force a live arXiv API fetch in CI, set `ARXIV_FORCE: "1"` on the build step (removes the 24h skip).

## Caches

Actions caches:

- `data/dblp.xml.gz` (large; speeds up repeat runs)
- abstract / arXiv / dblp build manifests under `data/`
- author country enrichment (`author-country-cache-*`, `dblp-affiliation-cache-*`, `author-enrich-*`)

First run may take a long time while dblp downloads.

## Server vs GitHub

| | Linux server cron | GitHub Actions |
|--|-------------------|----------------|
| Host | Your VPS | `ubuntu-latest` |
| Install | `./scripts/install_daily_schedule.sh` | Workflow file |
| Web | `./scripts/serve_site.sh` | GitHub Pages CDN |
| Logs | `logs/daily-*.log` | Actions run log |

Use one or both; if both run daily, they simply rebuild the same logic independently.

## Troubleshooting

- **Workflow fails on arXiv 429:** re-run later; crawl is incremental.
- **Pages 404:** confirm Pages source is **GitHub Actions**, not a branch folder.
- **Empty picks:** check `website/data/top-monthly.json` in the workflow artifact log.
- **Worldwide views bar hidden on Pages:** deploy the Cloudflare Worker, then add repository secret `VIEWS_API_URL` (see [VIEWS.md](VIEWS.md)). View counts update live at visit time; redeploying Pages only wires the API URL into the static site.
