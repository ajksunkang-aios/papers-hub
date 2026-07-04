# First-author country analytics

Standalone page: `website/country-analytics.html`  
Data: `website/data/country-analytics.json`

## Build

```bash
# Online build (dblp person pages + OpenAlex fallback)
./scripts/update_country_analytics.sh

# Local fast build (affiliation keyword rules only; no HTTP)
AUTHOR_COUNTRY_OFFLINE=1 ./scripts/update_country_analytics.sh
```

GitHub Actions runs the **online** pipeline inside [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) via `scripts/daily_update.sh` (dblp parse → author enrich → country analytics → Pages deploy).

## Resolution sources

1. dblp person-page affiliations (author search + profile HTML)
2. Institution/country keyword rules (`hubs/os-kernel/author_country_policy.json`)
3. OpenAlex institutions (`country_code`) via DOI / arXiv / title

Unknown papers are grouped under `XX`. Placeholder `Unknown affiliation` rows are **not** treated as complete; CI re-fetches real affiliations online.

## Configuration

Edit `hubs/os-kernel/author_country_policy.json`:

- `country_labels` — display names
- `region_groups` — APAC / Europe / Americas filters on the analytics page
- `institution_hints` — `[substring, ISO]` pairs for offline matching

## Tests

```bash
python3 -m unittest tests/test_author_country.py tests/test_dblp_affiliations.py
```
