# GitHub Pages + scheduled builds

The workflow [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) replaces a server cron job: it runs the same pipeline as `scripts/daily_update.sh` and publishes `website/` to GitHub Pages.

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
| `push` to `main` | Rebuild when code/config changes (path filters apply) |

To change timezone, edit the cron line in the workflow (GitHub Actions always uses UTC in `cron`).

## What the workflow runs

Same as local daily update:

- dblp parse (incremental, cached `data/dblp.xml.gz`)
- arXiv crawl (`--if-stale-hours 24`)
- top picks + broadcast + hub metadata
- **online country analytics** — dblp person-page affiliations for recent pick years (`PICK_YEARS`, first-author-only), keyword country codes → `website/data/country-analytics.json`, then deploy to Pages

CI defaults:

- `ABSTRACT_SKIP=1` (faster abstract step)
- **Online** dblp author enrich (`AUTHOR_ENRICH_OFFLINE=0`)
- OpenAlex off unless `AUTHOR_USE_OPENALEX=1`
- Job timeout 360 minutes so person-page fetches can finish; warm affiliation cache makes later days much faster

Emergency offline deploy (no dblp person-page HTTP):

```yaml
# on the Daily build step env:
AUTHOR_ENRICH_OFFLINE: "1"
```

To force a live arXiv API fetch in CI, set `ARXIV_FORCE: "1"` on the build step (removes the 24h skip).

## Caches

Actions caches:

- `data/dblp.xml.gz` (large; speeds up repeat runs)
- abstract / arXiv / dblp build manifests under `data/`
- dblp person-page affiliation cache (`dblp-affiliation-cache-*`) — **required for incremental online country analytics**
- author-country / author-enrich manifests

First run may take a long time while dblp downloads and affiliation cache warms up. Later scheduled runs reuse the affiliation cache and only fetch remaining authors.

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
- **country analytics `resolved=0`:** online enrich failed or was skipped; check the author metadata step and dblp connectivity from the runner. Do not set `AUTHOR_ENRICH_OFFLINE=1` unless intentional.
- **Worldwide views bar hidden on Pages:** deploy the Cloudflare Worker, then add repository secret `VIEWS_API_URL` (see [VIEWS.md](VIEWS.md)). View counts update live at visit time; redeploying Pages only wires the API URL into the static site.
