# Homelab

> Self-hosted home server infrastructure on Synology NAS. Docker Compose stacks for 34+ services covering media, monitoring, automation, and more.

---

## Table Of Contents

* [Quick Start](#quick-start)
* [Services](#services)
* [Common Operations](#common-operations)
* [Theme Park Integration](#theme-park-integration)
* [Monitoring Stack](#monitoring-stack)
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

### infrastructure/
- Cloudflare DDNS
- Docker Socket Proxy
- VPN gateways (gluetun, gluetun-brr, gluetun-cross)

### monitoring/
Apprise, Beszel, Dozzle, Glance, Gotify, Netronome, Scrutiny, Speedtest Tracker, Uptime Kuma, Watchtower, Dockhand

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

## Theme Park Integration

Services using hotio's containers support Theme Park for UI theming:

- Environment variables: `TP_HOTIO=true`, `TP_THEME=<theme-name>`
- Themes: `catppuccin-mocha`, `organizr`
- Volume mount: `${DOCKER_APPDATA_PATH}/themepark/98-themepark-<service>:/etc/cont-init.d/98-themepark`

---

## Monitoring Stack

The homelab uses a multi-layered monitoring approach with complementary tools.

See [services/monitoring/README.md](services/monitoring/README.md) for complete documentation.

---

## Troubleshooting

### Unresponsive Docker Containers on Synology

If Docker containers become completely unresponsive (commands like `docker exec`, `docker inspect`, `docker logs` hang indefinitely), this is a known issue with Synology's ContainerManager and BTRFS storage driver.

**Symptoms:**
- All Docker commands targeting a specific container timeout
- Container appears to be running but is not responsive
- Cannot stop or restart the container normally

**Solution:**
Restart the ContainerManager service:

```bash
sudo /var/packages/ContainerManager/scripts/start-stop-status stop
sudo /var/packages/ContainerManager/scripts/start-stop-status start
```

**Notes:**
- This will restart ALL Docker containers on the system
- Containers with `restart: always` will come back automatically
- This is the Synology-specific way to manage Docker (not standard `systemctl`)
