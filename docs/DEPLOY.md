# Deploy from scratch (Linux server)

End-to-end setup: build data once, run the website in the background, refresh dblp + arXiv every day at 9:00 AM.

Replace `/opt/papers-hub` with your path.

---

## 1. Prerequisites

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

python3 --version   # 3.9+ recommended
```

**Disk:** first dblp download is large (`data/dblp.xml.gz` ~800MB+). Plan **~5GB** free under the repo.

**Network:** needs outbound HTTPS for dblp, arXiv, and (optionally) abstract APIs. On a restricted LAN use `ABSTRACT_OFFLINE=1` / `ABSTRACT_SKIP=1` (below).

---

## 2. Get the code

```bash
sudo mkdir -p /opt
sudo chown "$USER:$USER" /opt
cd /opt
git clone <your-repo-url> papers-hub
cd papers-hub
```

Or copy the directory with `rsync` / `scp` if you do not use git on the server.

---

## 3. Python dependencies

```bash
cd /opt/papers-hub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For cron/systemd, use the venv python explicitly:

```bash
export PYTHON=/opt/papers-hub/.venv/bin/python3
```

---

## 4. First build (one time, can take a while)

**Recommended on first deploy** (faster, works on restricted networks):

```bash
cd /opt/papers-hub
source .venv/bin/activate

export ABSTRACT_SKIP=1          # skip slow abstract APIs on first run (optional)
# or: export ABSTRACT_OFFLINE=1  # use cache + local arXiv only

NO_SERVE=1 ./publish.sh
```

This will:

1. Download `data/dblp.xml.gz` (first time only)
2. Build conference JSON under `website/data/`
3. Crawl arXiv, build picks and broadcast

**Later**, backfill abstracts when the network allows:

```bash
ABSTRACT_ENRICH_YEARS=2023,2024,2025,2026 ./publish.sh
# or ABSTRACT_OFFLINE=1 for cache/local only
```

Check output exists:

```bash
ls website/data/conferences.json website/data/top-monthly.json website/data/arxiv-recent.json
```

---

## 5. Run the HTTP server (always on)

Default script port is **8765**, not 80.

### Option A � Port 8080 (no root)

```bash
SITE_PORT=8080 SITE_BIND=0.0.0.0 ./scripts/serve_site.sh
```

Open: `http://<server-ip>:8080/`

### Option B � Port 80 (needs root)

```bash
sudo -E env SITE_PORT=80 SITE_BIND=0.0.0.0 \
  /opt/papers-hub/scripts/serve_site.sh
```

### Option C � systemd user service (recommended)

Create `~/.config/systemd/user/papers-hub-web.service`:

```ini
[Unit]
Description=Papers Hub static site
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/papers-hub
Environment=PYTHON=/opt/papers-hub/.venv/bin/python3
Environment=HUB=os-kernel
Environment=SITE_PORT=8080
Environment=SITE_BIND=0.0.0.0
ExecStart=/opt/papers-hub/scripts/serve_site.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable:

```bash
mkdir -p ~/.config/systemd/user
systemctl --user daemon-reload
systemctl --user enable --now papers-hub-web.service
systemctl --user status papers-hub-web.service
sudo loginctl enable-linger "$USER"    # keep running after logout
```

For port 80, set `SITE_PORT=80` and run the service as root or put **nginx** in front (see section 7).

---

## 6. Daily 9:00 AM update (cron)

Does **not** restart the web server; only refreshes `website/data/`.

```bash
cd /opt/papers-hub
chmod +x scripts/*.sh

# If using venv, bake PYTHON into cron:
(crontab -l 2>/dev/null; echo "PYTHON=/opt/papers-hub/.venv/bin/python3") | crontab - 2>/dev/null || true

SCHEDULE_TZ=Asia/Shanghai ./scripts/install_daily_schedule.sh
```

Test once:

```bash
./scripts/daily_update.sh
tail -f logs/daily-$(date +%Y%m%d).log
```

Verify cron:

```bash
crontab -l | grep papers-hub
```

**Remove cron later:** `crontab -e` and delete the `papers-hub` lines.

---

## 7. Optional: nginx on port 80 ? app on 8080

Keeps the hub on a high port (no root) and exposes port 80 via nginx.

```nginx
server {
    listen 80;
    server_name your.domain.example;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/papers-hub /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. Firewall

```bash
# if using port 8080 directly
sudo ufw allow 8080/tcp

# if using nginx on 80
sudo ufw allow 80/tcp
```

---

## 9. Verify deployment

| Check | Command |
|-------|---------|
| Site responds | `curl -sI http://127.0.0.1:8080/ \| head -1` |
| Data present | `ls website/data/*.json \| head` |
| Web service | `systemctl --user status papers-hub-web` |
| Cron installed | `crontab -l \| grep os-kernel` |
| Daily log | `tail logs/daily-$(date +%Y%m%d).log` |

---

## 10. Common environment variables

| Variable | When |
|----------|------|
| `NO_SERVE=1` | Build only, no HTTP server |
| `SITE_PORT` / `SITE_BIND` | Web port and bind address (default **8765**, localhost) |
| `ABSTRACT_SKIP=1` | Skip abstract enrichment |
| `ABSTRACT_OFFLINE=1` | Abstracts from cache + local arXiv only |
| `ABSTRACT_ENRICH_YEARS` | Years to enrich (publish default `2025,2026`) |
| `HUB=os-kernel` | Hub id |
| `SCHEDULE_TZ=Asia/Shanghai` | Cron 9:00 AM timezone |

---

## 11. Update after `git pull`

```bash
cd /opt/papers-hub
git pull
source .venv/bin/activate
pip install -r requirements.txt
NO_SERVE=1 ./publish.sh
# web server picks up new files automatically; restart only if you changed serve scripts:
systemctl --user restart papers-hub-web
```

Daily cron handles routine arXiv/dblp refresh; full `publish.sh` is for manual rebuilds after code or config changes.
