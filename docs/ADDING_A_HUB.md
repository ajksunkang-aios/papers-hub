# Adding a research-area hub

This repository (**papers-hub**) is a **multi-hub paper index**: shared build tooling under `core/` and per-area configuration under `hubs/<hub-id>/`.

The live **OS Kernel** site is `hubs/os-kernel` ? `website/`. A **Compiler** example stub lives in `hubs/compiler/`.

## Layout

```
papers-hub/
??? core/                    # Shared Python (hub loader, keyword scoring)
??? data/dblp.xml.gz         # Shared dblp dump (~1 GB, all hubs)
??? hubs/
?   ??? os-kernel/
?   ?   ??? hub.json         # Branding, paths, section titles
?   ?   ??? venues.json      # dblp conference slugs
?   ?   ??? categories.json  # Top picks by area keywords
?   ?   ??? arxiv_policy.json
?   ?   ??? conference_timeline.json
?   ??? compiler/            # Example second hub
??? website/                 # os-kernel static site + data/
??? publish.sh               # HUB=os-kernel ./publish.sh
```

## Quick start (new hub)

1. **Copy the compiler stub** (or duplicate `hubs/os-kernel` and edit):

   ```bash
   cp -R hubs/compiler hubs/my-area
   ```

2. **Edit `hubs/my-area/hub.json`**
   - `id`, `title`, `lede`, `venue_order`, `pick_years`
   - `paths.site_dir` ? e.g. `hubs/my-area/site` (keep data separate from `website/`)

3. **Edit `venues.json`** ? dblp slugs for proceedings you want.

4. **Edit `categories.json`** ? research sub-areas and keyword lists.

5. **Edit `arxiv_policy.json`** ? feeds, scoring, broadcast rules.

6. **Edit `conference_timeline.json`** ? optional homepage timeline.

7. **Bootstrap the static site** (once per hub):

   ```bash
   ./scripts/bootstrap_hub_site.sh my-area
   ```

8. **Build and serve**:

   ```bash
   HUB=my-area PICK_YEARS=2024,2025,2026 ./publish.sh
   ```

## Pipeline (per hub)

```bash
export HUB=my-area
NO_SERVE=1 ./publish.sh
SITE_PORT=8080 ./scripts/serve_site.sh "$HUB"
```

See **[DEPLOY.md](DEPLOY.md)** for Linux server setup and daily cron.

## Syncing os-kernel config from Python sources

```bash
python3 scripts/export_hub_configs.py
```

## Compiler example

```bash
HUB=compiler PICK_YEARS=2025,2026 ./publish.sh
```
