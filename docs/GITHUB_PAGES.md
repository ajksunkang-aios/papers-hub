# GitHub Pages + scheduled builds

The workflow [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) runs the daily pipeline (dblp + arXiv + picks) and publishes `website/` to GitHub Pages.

**Country analytics** is on a separate site — see [COUNTRY_PAGES.md](COUNTRY_PAGES.md).

## One-time setup

1. Push the repo to GitHub.
2. **Settings → Pages → Build and deployment → Source:** choose **GitHub Actions**.
3. (Optional) Wait for the first workflow run, or trigger **Actions → Deploy Pages → Run workflow**.

Site URL: `https://<user>.github.io/<repo>/` (or your custom domain).

## Schedule

| Event | When |
|-------|------|
| `cron: "0 1 * * *"` | **09:00 Asia/Shanghai** (01:00 UTC) daily |
| `workflow_dispatch` | Manual run from the Actions tab |

Push to `main` does **not** trigger this workflow (avoids running the heavy build on every code change). Use **Run workflow** when you need a deploy outside the schedule.

## What the workflow runs

Same as local daily update, **without** author enrich or country analytics:

- dblp parse (incremental, cached `data/dblp.xml.gz`)
- arXiv crawl (`--if-stale-hours 24`)
- top picks + broadcast + hub metadata

CI sets `DAILY_SKIP_AUTHOR_ENRICH=1` and `DAILY_SKIP_COUNTRY_ANALYTICS=1`.

To update country data locally and deploy: [COUNTRY_PAGES.md](COUNTRY_PAGES.md).

## Caches

Actions caches:

- `data/dblp.xml.gz` (large; speeds up repeat runs)
- abstract / arXiv / dblp build manifests under `data/`

## Server vs GitHub

| | Linux server cron | GitHub Actions |
|--|-------------------|----------------|
| Host | Your VPS | `ubuntu-latest` |
| Install | `./scripts/install_daily_schedule.sh` | Workflow file |
| Web | `./scripts/serve_site.sh` | GitHub Pages CDN |
| Logs | `logs/daily-*.log` | Actions run log |

## Troubleshooting

- **Workflow fails on arXiv 429:** re-run later; crawl is incremental.
- **Pages 404:** confirm Pages source is **GitHub Actions**, not a branch folder.
- **Empty picks:** check `website/data/top-monthly.json` in the workflow artifact log.
- **Worldwide views bar hidden on Pages:** deploy the Cloudflare Worker, then add repository secret `VIEWS_API_URL` (see [VIEWS.md](VIEWS.md)).
