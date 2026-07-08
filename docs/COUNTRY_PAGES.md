# Country analytics GitHub Pages

Country analytics lives on a **separate GitHub Pages site** from the main papers hub. Data is enriched **locally** and committed; CI only packages and deploys static files.

| Site | Workflow | URL (example) |
|------|----------|---------------|
| Main hub | [deploy-pages.yml](../.github/workflows/deploy-pages.yml) | `https://<user>.github.io/papers-hub/` |
| Country analytics | [deploy-country-pages.yml](../.github/workflows/deploy-country-pages.yml) | `https://<user>.github.io/papers-hub-country/` |

## One-time setup

### 1. Create the country Pages repository

1. Create a new repo, e.g. `papers-hub-country` (empty is fine).
2. **Settings → Pages → Build and deployment → Source:** choose **Deploy from a branch**.
3. Branch: `gh-pages` / root (the workflow pushes here via `peaceiris/actions-gh-pages`).

### 2. Configure this repository

In **papers-hub** repo settings:

| Setting | Value |
|---------|--------|
| Variable `COUNTRY_PAGES_REPOSITORY` | `owner/papers-hub-country` |
| Secret `COUNTRY_PAGES_DEPLOY_TOKEN` | PAT with `contents:write` on the country repo |

Edit `hubs/os-kernel/hub.json`:

```json
"main_hub_url": "https://<user>.github.io/papers-hub/",
"country_analytics_url": "https://<user>.github.io/papers-hub-country/"
```

Run `./scripts/sync_hub_meta.py` so `website/data/hub.json` picks up the URLs. The main site header link opens the external country site in a new tab.

## Local update workflow

```bash
# Full enrich + rebuild country-analytics.json (slow; run on your machine)
./scripts/publish_country_data.sh

# Or step by step:
./scripts/update_country_analytics.sh    # enrich + build JSON
./scripts/prepare_country_site.sh      # assemble website-country/

git add website/data/country-analytics.json website/data/*.json
git commit -m "Update country analytics data"
git push
```

Push to `main` when `website/data/country-analytics.json` changes triggers **Deploy Country Pages**.

Manual deploy: **Actions → Deploy Country Pages → Run workflow**.

## What CI does (country workflow)

1. `./scripts/prepare_country_site.sh` — copies `country-analytics.json` + static assets into `website-country/`
2. Validates JSON shape
3. Deploys `website-country/` to the external repo’s `gh-pages` branch

No dblp download, no person index build, no HTTP enrich on GitHub Actions.

## Main site (Deploy Pages cron)

The daily **Deploy Pages** workflow sets:

- `DAILY_SKIP_AUTHOR_ENRICH=1`
- `DAILY_SKIP_COUNTRY_ANALYTICS=1`

So scheduled builds only refresh dblp / arXiv / picks / broadcast. Country data stays as committed in git until you push a local update.

## Files

| Path | Role |
|------|------|
| `website/data/country-analytics.json` | Source of truth (committed after local build) |
| `website-country/index.html` | Standalone country site entry |
| `scripts/publish_country_data.sh` | Local one-shot enrich + prepare |
| `scripts/prepare_country_site.sh` | Copy JSON + assets into `website-country/` |
| `scripts/update_country_analytics.sh` | Enrich affiliations + build JSON |

See also [AUTHOR_COUNTRY.md](AUTHOR_COUNTRY.md) for enrich options and policy configuration.
