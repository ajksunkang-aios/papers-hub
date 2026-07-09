# Cumulative views by world region

The site shows a bar at the top of each page with total page views and a breakdown by region:

**China · America · Europe · Asia-Pacific · Oceania · Africa & Middle East · Others**

GitHub Pages is static, so counting requires a small backend API. The frontend module is `website/views.js`.

## Local development

1. Sync zone config (keeps worker JSON aligned with `core/view_zones.json`):

   ```bash
   python3 scripts/sync_view_zones.py
   ```

2. Start the dev API (persists to `data/view-stats.json`):

   ```bash
   python3 scripts/views_api_dev.py
   ```

3. Serve the site and open `http://127.0.0.1:8765/`:

   ```bash
   ./scripts/serve_site.sh
   ```

   On localhost the widget defaults to `http://127.0.0.1:8788` automatically. The dev API accepts optional JSON `{ "country": "CN" }` on `/hit`; production uses Cloudflare `CF-IPCountry`.

## Production (Cloudflare Worker)

1. Create a KV namespace and deploy `workers/view-stats/`:

   ```bash
   cd workers/view-stats
   npx wrangler kv namespace create VIEW_STATS
   # paste the id into wrangler.toml
   python3 ../../scripts/sync_view_zones.py
   npx wrangler deploy
   ```

2. Set the worker URL via GitHub Actions secret (recommended):

   - Repo **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `VIEWS_API_URL`
   - Value: `https://your-worker.example.workers.dev`

   The Deploy Pages workflow injects this into `website/data/hub.json` on each build.

   Or set it in `hubs/os-kernel/hub.json`:

   ```json
   "views_api_url": "https://your-worker.example.workers.dev"
   ```

3. Redeploy Pages after the worker is live.

Alternatively, add a meta tag to each HTML page:

```html
<meta name="papers-hub-views-api" content="https://your-worker.example.workers.dev" />
```

## API

| Method | Path    | Description                                      |
|--------|---------|--------------------------------------------------|
| GET    | `/stats` | Returns `{ total, zones, zone_labels, zone_order, updated_at }` |
| POST   | `/hit`   | Records one view; Worker uses Cloudflare geo headers; dev accepts optional JSON `{ "country" }` |

Each browser session records at most one successful hit (`sessionStorage`, with in-memory fallback).

Zone mappings live in `core/view_zones.json` and are copied to `workers/view-stats/zones.json` by `scripts/sync_view_zones.py`.

Run tests:

```bash
python3 -m unittest tests/test_view_stats.py
python3 scripts/sync_view_zones.py --check
```
