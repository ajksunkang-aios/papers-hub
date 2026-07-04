# First-author country analytics

Standalone page: `website/country-analytics.html`  
Data: `website/data/country-analytics.json`

## Build

```bash
# Fast offline build (institution keywords in title/abstract/affiliations)
python3 build_country_analytics.py --hub os-kernel --offline

# Full build with OpenAlex (requires network; populates data/author-country-cache-<hub>.json)
python3 build_country_analytics.py --hub os-kernel --years 2023,2024,2025,2026
```

Daily pipeline runs the offline build by default (`AUTHOR_COUNTRY_OFFLINE=1` in CI).  
For higher coverage locally, run without `--offline` after `daily_update.sh`.

## Resolution sources

1. OpenAlex institutions (`country_code`) via DOI
2. arXiv first-author affiliations (when present in crawl output)
3. Institution keyword rules (`hubs/os-kernel/author_country_policy.json`)
4. Paper text keyword scan (low confidence fallback)

Unknown papers are grouped under `XX`.

## Configuration

Edit `hubs/os-kernel/author_country_policy.json`:

- `country_labels` — display names
- `region_groups` — APAC / Europe / Americas filters on the analytics page
- `institution_hints` — `[substring, ISO]` pairs for offline matching

## Tests

```bash
python3 -m unittest tests/test_author_country.py
```
