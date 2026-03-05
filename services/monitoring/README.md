# Monitoring Stack

The homelab uses a multi-layered monitoring approach with complementary tools.

## Stack Architecture

```
Layer 1: Availability → Uptime Kuma (Is it alive?)
Layer 2: Performance → Beszel (How is it performing?)
Layer 3: Logs → Dozzle (What happened?)
Layer 4: Updates → Watchtower (Is it up to date?)
Layer 5: Alerting → Gotify + Discord (Notify me)
```

## When to use what

- Service went down? → Check Uptime Kuma for uptime status
- High CPU/memory? → Check Beszel for resource usage trends
- Service behaving oddly? → Check Dozzle for error logs
- Need historical performance data? → Check Beszel charts
- Container updates? → Check Discord channel for Watchtower notifications (updates run daily at 3 AM)

## Services

### Beszel - Hardware & Resource Monitoring

**Location**: `services/monitoring/beszel/`
**Port**: 8091
**Access**: `http://ds423plus:8091` or `http://10.10.2.2:8091`

**Purpose**: System performance and resource monitoring

**What it monitors:**
- **Hardware metrics**: CPU usage, memory (RAM + swap), disk space, disk I/O, network bandwidth, temperature sensors
- **Filesystem monitoring**: Volume1 (11TB) and Volume2 (3.6TB) - main volumes only
- **Docker containers**: Per-container CPU/memory/network usage with historical data
- **Historical data**: 90-day retention (configurable) with time-series charts

**Note on filesystem monitoring:**
- Monitors volume-level usage (Volume1/Volume2 overall)
- BTRFS subvolumes show total volume usage, not individual directory size

**Architecture:**
- **Hub**: Web dashboard for viewing all metrics (PocketBase-based)
- **Agent**: Lightweight collector running on the NAS, connects via Docker Socket Proxy

**Key features:**
- Real-time and historical performance charts
- Configurable alerts (disk space, CPU, memory, temperature)
- Automatic backups (S3-compatible or local)
- Very lightweight (<50MB RAM usage)

**Configuration:**
- Agent key stored in `.env` file (generated during first setup)
- Data stored in `${DOCKER_APPDATA_PATH}/beszel/data`
- Uses Docker Socket Proxy for secure Docker API access

**Alert thresholds** (recommended):
- Disk space: 95%
- CPU sustained usage: 80%+
- Memory usage: 90%+
- Temperature: 70°C+ (if available)

**Notification Integration**:

Beszel alerts are sent directly to Gotify and Discord using Shoutrrr URLs:

1. **Setup Notification URLs** (in Beszel Hub UI at http://10.10.2.2:8091):
   - Go to **Settings** → **Notifications**
   - Add notification URLs (Shoutrrr format):
     ```
     gotify://gotify:80/MONITORING_TOKEN?priority=8
     discord://WEBHOOK_ID/WEBHOOK_TOKEN
     ```
   - Click **Test URL** to verify each connection

2. **Configure Alert Thresholds**:
   - On the main dashboard, click the **bell icon (🔔)**
   - Set thresholds for each metric (CPU, memory, disk, etc.)
   - Recommended: Disk 95%, CPU 80%, Memory 90%, Temperature 70°C
   - Enable alerts per system in the systems table

**Common operations:**
```bash
# View logs
cd services/monitoring/beszel && docker-compose logs -f

# Restart service
docker-compose restart beszel

# Check metrics collection
docker-compose logs beszel-agent
```

### Uptime Kuma - Service Availability Monitoring

**Location**: `services/monitoring/uptime-kuma/`
**Port**: 3001
**Access**: `http://ds423plus:3001` or `http://10.10.2.2:3001`

**Purpose**: Monitor if services are up/down and responding

**What it monitors:**
- HTTP/HTTPS endpoints (Plex, Sonarr, Radarr, etc.)
- TCP port availability
- Docker container status (up/down)
- Ping monitoring (network devices)
- DNS records, SSL certificates

**Monitor Types:**
- **HTTP monitors**: For services with web UIs/APIs (Dozzle, Beszel, Uptime Kuma, Plex, etc.)
  - Verifies the service is responding, not just that the container is running
  - Detects frozen/crashed services even if container appears running
- **Docker monitors**: For background services without HTTP interfaces (Watchtower, Cloudflare DDNS, GitHub Actions runner)
  - Simple container status check (running/stopped)
  - No authentication or endpoint requirements
- **Port monitors**: For raw TCP/UDP port checks (Docker Socket Proxy)

### Dozzle - Log Viewer

**Location**: `services/monitoring/dozzle/`
**Port**: 8088
**Access**: `http://ds423plus:8088` or `http://10.10.2.2:8088`

**Purpose**: Real-time Docker container log viewing

**Key features:**
- Live streaming logs
- SQL queries on log data
- Shell access to containers
- Multi-host support

### Watchtower - Container Update Automation

**Location**: `services/monitoring/watchtower/`
**Port**: 8082 (HTTP API)
**Access**: `http://ds423plus:8082` or `http://10.10.2.2:8082`

**What it does:**
- Monitors Docker images for updates
- Updates containers
- Cleans up old images after updates
- Label-based whitelist for selective updates

### Gotify - Push Notification Server

**Location**: `services/monitoring/gotify/`
**Port**: 8093
**Access**: `http://ds423plus:8093` or `http://10.10.2.2:8093`

**Purpose**: Self-hosted push notification server for mobile and desktop alerts

**What it does:**
- Provides native mobile app notifications (Android, iOS via iGotify)
- Web UI for viewing all notifications
- Simple REST API for sending messages
- Application-based organization with separate tokens

**Current Integrations:**
- **Uptime Kuma**: Service availability alerts (native Gotify support)
- **Beszel**: Resource threshold alerts (via Shoutrrr)
- **Watchtower**: Container update notifications (via Shoutrrr)
- **Sonarr/Radarr**: Media download notifications (native support)
- **Kometa**: Media library updates (native support)

## Resources

- **Beszel**: [Official Documentation](https://beszel.dev/)
- **Uptime Kuma**: [Official Documentation](https://github.com/louislam/uptime-kuma)
- **Dozzle**: [Official Documentation](https://dozzle.dev/)
- **Watchtower**: [Official Documentation](https://containrrr.dev/watchtower/)
- **Gotify**: [Official Documentation](https://gotify.net/docs/) | [GitHub](https://github.com/gotify/server)
