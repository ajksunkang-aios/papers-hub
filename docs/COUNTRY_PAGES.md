# Country & author analytics (same GitHub Pages site)

Country and author analytics are **pages on the main papers hub**:

| Page | Data |
|------|------|
| `country-analytics.html` | `country-analytics.json` |
| `author-analytics.html` | `author-analytics.json` |

## CI schedule

| Workflow | When | What |
|----------|------|------|
| [deploy-pages.yml](../.github/workflows/deploy-pages.yml) | **Daily** 09:00 UTC+8 / manual | arXiv crawl, top picks, broadcast, search index → deploy full site. **Skips** affiliation enrich. |
| [deploy-country-pages.yml](../.github/workflows/deploy-country-pages.yml) | **Monthly** (1st, 10:00 UTC+8) / manual | OpenAlex + dblp affiliation enrich, rebuild **country + author** analytics, commit JSON, deploy. |

Both publish to the **same** GitHub Pages URL.

Daily deploy uses analytics JSON from the repo (last monthly refresh). Manual analytics run between months:

```bash
AUTHOR_ENRICH_ONLINE_DBLP=1 AUTHOR_USE_OPENALEX=1 ./scripts/update_analytics.sh
git add website/data/country-analytics.json website/data/author-analytics.json website/data/*.json
git commit -m "Update analytics data"
git push
# Then Run workflow → Deploy Pages (or wait for daily cron)
```

## Local update

```bash
./scripts/update_analytics.sh          # enrich + country + author
# or country only:
./scripts/update_country_analytics.sh
./scripts/update_author_analytics.sh
```

See [AUTHOR_COUNTRY.md](AUTHOR_COUNTRY.md) for enrich flags (`AUTHOR_ENRICH_FULL`, offline mode, etc.).
