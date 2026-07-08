# Papers Hub

**Papers Hub** 是面向操作系统与系统研究的自动更新论文雷达，汇聚顶会 proceedings 与 arXiv 新文，按研究方向精选呈现，帮助研究者快速发现与跟进重要工作。

[English README](README.md)

默认站点为 **OS 内核与系统** 方向（`hubs/os-kernel` → `website/`）。代码库通过 `hubs/<hub-id>/` 支持多个研究方向 hub。

## 本地运行（默认 hub）

```bash
./publish.sh
# 浏览器打开 http://127.0.0.1:8765/
```

**默认 HTTP 端口为 `8765`，不是 80。** 仅当设置 `SITE_PORT=80` 时使用 80 端口（Linux 上需要 root 权限）。

| 用途 | 命令 |
|------|------|
| 默认本地预览 | `./publish.sh` → **8765** |
| 自定义端口 | `SITE_PORT=8080 ./publish.sh` |
| 服务器上使用 80 端口 | `NO_SERVE=1 ./publish.sh`，然后 `sudo -E env SITE_PORT=80 SITE_BIND=0.0.0.0 ./scripts/serve_site.sh` |
| 仅构建、不启动服务 | `NO_SERVE=1 ./publish.sh` |

确认服务是否在监听：

```bash
ss -tlnp | grep python
curl -sI http://127.0.0.1:8765/ | head -1
```

首次构建需要 `data/dblp.xml.gz`（会自动下载）。

**年份窗口（默认）：** 已发表论文精选 `2023-2026`，arXiv 精选 `2025-2026`。可通过 `PICK_YEARS` 和 `ARXIV_PICK_YEARS` 覆盖。

**摘要 enrichment：** `publish.sh` 默认仅处理 `2025,2026` 年。全量回填：`ABSTRACT_ENRICH_YEARS=2023,2024,2025,2026 ./publish.sh`。跳过：`ABSTRACT_SKIP=1`。

## 部署

| 目标 | 文档 |
|------|------|
| **GitHub Pages**（定时构建 + 托管） | **[docs/GITHUB_PAGES.md](docs/GITHUB_PAGES.md)** — `.github/workflows/deploy-pages.yml` |
| **Linux 服务器**（cron + 自建 HTTP 服务） | **[docs/DEPLOY.md](docs/DEPLOY.md)**、**[docs/LINUX_SERVER.md](docs/LINUX_SERVER.md)** |

## 每日自动更新（上午 9:00，UTC+8）

刷新 dblp、arXiv 与精选列表（**不会**重启 HTTP 服务）。

```bash
./scripts/install_daily_schedule.sh
./scripts/daily_update.sh
```

移除 cron：执行 `crontab -e`，删除包含 `papers-hub` 的行。

## 站点功能

- **分方向精选** — 左侧为已发表论文（proceedings），右侧为近期 arXiv；**More** 进入 `area-picks.html`。
- **广播栏** — 近 7 天 arXiv 热门论文。
- **会议论文集** — 浏览与搜索 dblp 支持的 venue JSON。
- **全站搜索** — 按标题与摘要关键词检索。
- **技术地图** — 经典与扩展 OS 主题，可跳转至精选与搜索。
- **作者与国家分析** — 研究方向分布与机构归属视图。

## 多研究方向

配置位于 `hubs/<hub-id>/`。详见 **[docs/ADDING_A_HUB.md](docs/ADDING_A_HUB.md)**。

```bash
HUB=compiler ./publish.sh
```

## 仓库结构

| 路径 | 说明 |
|------|------|
| `hubs/os-kernel/` | 默认 hub 配置（venue、关键词、时间线） |
| `website/` | `os-kernel` 的静态站点输出 |
| `scripts/serve_site.sh` | 静态 HTTP 服务（`SITE_PORT`，默认 **8765**） |
| `scripts/daily_update.sh` | 每日 dblp + arXiv 刷新 |
| `scripts/install_daily_schedule.sh` | 安装上午 9:00 cron（Linux） |
| `publish.sh` | 完整构建流水线（`HUB=` 环境变量） |
