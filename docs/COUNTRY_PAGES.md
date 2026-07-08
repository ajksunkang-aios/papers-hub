# Country analytics (same GitHub Pages site)

Country analytics is a **page on the main papers hub**, not a separate repository:

- Page: `website/country-analytics.html`
- Data: `website/data/country-analytics.json`
- Navigation: header tab on `index.html` → `country-analytics.html` (same site)

Data is enriched **locally** and committed; CI only redeploys static files.

## Local update

```bash
./scripts/publish_country_data.sh

git add website/data/country-analytics.json website/data/*.json
git commit -m "Update country analytics data"
git push
```

Push triggers [deploy-country-pages.yml](../.github/workflows/deploy-country-pages.yml) — a **fast redeploy** of `website/` to the same GitHub Pages URL (no dblp / arXiv / enrich on Actions).

## Workflows

| Workflow | When | What |
|----------|------|------|
| [deploy-pages.yml](../.github/workflows/deploy-pages.yml) | Daily cron / manual | dblp + arXiv + picks; **skips** country enrich |
| [deploy-country-pages.yml](../.github/workflows/deploy-country-pages.yml) | Push country JSON / manual | Redeploy committed `website/` (includes country page) |

Both publish to the **same** GitHub Pages site (`https://<user>.github.io/<repo>/`).

## Enrich options

See [AUTHOR_COUNTRY.md](AUTHOR_COUNTRY.md) for `./scripts/update_country_analytics.sh` flags (`AUTHOR_ENRICH_FULL`, offline mode, etc.).
