# Monitoring Stack

The homelab uses a multi-layered monitoring approach with complementary tools.

## Stack Architecture

```
Layer 1: Availability → Uptime Kuma (Is it alive?)
Layer 2: Logs → Dozzle (What happened?)
Layer 3: Updates → Watchtower (Is it up to date?)
Layer 4: Alerting → Gotify + Discord (Notify me)
```

## When to use what

- Service went down? → Check Uptime Kuma for uptime status
- Service behaving oddly? → Check Dozzle for error logs
- Container updates? → Check Discord channel for Watchtower notifications (updates run daily at 3 AM)

## Services

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
- **Watchtower**: Container update notifications (via Shoutrrr)
- **Sonarr/Radarr**: Media download notifications (native support)
- **Kometa**: Media library updates (native support)

## Resources

- **Uptime Kuma**: [Official Documentation](https://github.com/louislam/uptime-kuma)
- **Dozzle**: [Official Documentation](https://dozzle.dev/)
- **Watchtower**: [Official Documentation](https://containrrr.dev/watchtower/)
- **Gotify**: [Official Documentation](https://gotify.net/docs/) | [GitHub](https://github.com/gotify/server)
