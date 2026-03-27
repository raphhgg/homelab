# Homelab

> Self-hosted home server Docker Compose infrastructure.

---

## Table Of Contents

* [Quick Start](#quick-start)
* [Services](#services)
* [Common Operations](#common-operations)
* [Monitoring](#monitoring-stack)
* [Troubleshooting](#troubleshooting)

---

## Quick Start

1. **Clone the repo:**
   ```bash
   git clone <your-repo-url>
   cd homelab
   ```
2. **Set up environment variables:**
   ```bash
   cd services/<category>/<service-name>
   cp .env.example .env
   # Edit .env with your actual values
   ```
3. **Deploy a service:**
   ```bash
   docker compose up -d
   ```

---

## Services

Services are organized in `services/` by category:

### arrs/
Media management applications: Sonarr, Radarr, Prowlarr, Bazarr, Profilarr, Calibre

### torrents/
- qBittorrent instances (qbit-main, qbit-brr, qbit-cross)
- Torrent automation (autobrr, cross-seed, qbit_manage)
- Tools (unpackerr, upload-assistant, qui, mam_seedboxapi, thelounge)

### media-server/
- Plex and related: Plex, Kometa, ImageMaid, Plex-Auto-Languages, Plex-Trakt-Sync
- Other: Tautulli, Trailarr, Jellyseerr, Stash, Lettarrboxd
- Remote access guide: [Plex via Pangolin + Pocket ID](services/media-server/plex/README.md)

### infrastructure/
- Cloudflare DDNS
- Docker Socket Proxy
- VPN gateways (gluetun, gluetun-brr, gluetun-cross)

### monitoring/
Glance, Gotify, Grafana, Uptime Kuma, Watchtower

### Other
- **home-assistant/**: Smart home automation
- **open-webui/**: AI chat interface
- **syncthing/**: File synchronization
- **rsshub/**: RSS feed generation

---

## Common Operations

### Deploying a Service
```bash
cd services/<category>/<service-name>
docker compose up -d
```

### Checking Service Status
```bash
docker compose ps
docker compose logs -f <service-name>
```

### Updating a Service
```bash
docker compose pull
docker compose up -d
```

### Stopping a Service
```bash
docker compose down
```

---

## Monitoring

The homelab uses a multi-layered monitoring approach with complementary tools.

See [services/monitoring/README.md](services/monitoring/README.md) for complete documentation.

---
