# First-author country analytics

Standalone page: `website/country-analytics.html`  
Data: `website/data/country-analytics.json`

## Data source

Country analytics uses **dblp only**, and counts **every conference year** present in `website/data/conferences.json` (not just recent pick years).

1. **Papers** — all venue JSON under `website/data/` listed by `conferences.json` (`COUNTRY_YEARS=all` by default).
2. **Affiliations** — fetched from dblp **person pages** (bulk `dblp.xml` has author names only, no affiliations). Online enrich still focuses on recent `PICK_YEARS` for speed; older papers stay `XX` until affiliations are filled.
3. **Country** — inferred from affiliation text via keyword rules in `author_country_policy.json`.
4. **Unknown** — no dblp affiliation or no keyword match → country code `XX`.

OpenAlex is **optional** (`--openalex` / `AUTHOR_USE_OPENALEX=1`) and off by default.

## Build

```bash
# Online dblp affiliations + keyword rules (default)
./scripts/update_country_analytics.sh

# Fully offline (no HTTP; uses whatever is already in JSON)
AUTHOR_COUNTRY_OFFLINE=1 ./scripts/update_country_analytics.sh

# Optional OpenAlex fallback
AUTHOR_USE_OPENALEX=1 ./scripts/update_country_analytics.sh
```

GitHub Actions runs the **online** dblp pipeline in [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) via `scripts/daily_update.sh` (first-author-only). Affiliation caches are restored across runs:

| File | Role |
|------|------|
| `data/dblp-affiliation-cache-*.json` | Per-author dblp person-page result (or miss) |
| `data/author-country-cache-*.json` | Per-paper `authors_structured` |
| `data/author-paper-reload-*.json` | Compact reload index written into `website/data/*.json` |

Each run **reloads** prior results into conference JSON, then only HTTP-fetches authors still missing from the dblp cache. Opt out of online fetch with `AUTHOR_ENRICH_OFFLINE=1`. Force full re-fetch: `AUTHOR_ENRICH_FORCE=1`.

## Configuration

Edit `hubs/os-kernel/author_country_policy.json`:

- `country_labels` — display names
- `region_groups` — APAC / Europe / Americas filters on the analytics page
- `institution_hints` — `[substring, ISO]` pairs matched against affiliation text

## Tests

```bash
python3 -m unittest tests/test_author_country.py tests/test_dblp_affiliations.py
```
