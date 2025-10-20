# Monitoring Stack

The homelab uses a multi-layered monitoring approach with complementary tools.

## Stack Architecture

```
Layer 1: Availability → Uptime Kuma (Is it alive?)
Layer 2: Performance → Beszel (How is it performing?)
Layer 3: Logs → Dozzle (What happened?)
Layer 4: Updates → Watchtower (Is it up to date?)
Layer 5: Alerting → Apprise/n8n (Notify me)
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
- For directory-level usage (docker, downloads, movies, etc.), use Cronicle-scheduled scripts
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

**Key features:**
- 90+ notification channels via Apprise
- Status pages for public/team visibility
- Uptime history and response time tracking
- Groups and tags for organization

**Automated monitor setup:**
Run `services/monitoring/uptime-kuma/setup_monitors.py` to automatically create/update monitors for all services

**Monitor Types:**
- **HTTP monitors**: For services with web UIs/APIs (Dozzle, Beszel, Uptime Kuma, Cronicle, Plex, etc.)
  - Verifies the service is responding, not just that the container is running
  - Detects frozen/crashed services even if container appears running
- **Docker monitors**: For background services without HTTP interfaces (Watchtower, Cloudflare DDNS, GitHub Actions runner)
  - Simple container status check (running/stopped)
  - No authentication or endpoint requirements
- **Port monitors**: For raw TCP/UDP port checks (Docker Socket Proxy)

**Group Monitoring Limitation:**
- Monitors are organized in groups (infrastructure, monitoring, media-server, etc.) for better organization
- **Known issue**: When a child monitor in a group goes down, the group shows status "Down - Child inaccessible"
- This creates redundant alerts (individual service alert + group alert)
- **No built-in way to disable group status** - this is a known Uptime Kuma limitation (GitHub issues #4829, #3400, #3278)
- **Workaround**: Configure notification rules to alert only on individual monitors, not on groups (if your notification system supports filtering)

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

**Purpose**: Automated Docker container update management with human-in-the-loop workflow

**Architecture**: HTTP API mode with Cronicle scheduling

**What it does:**
- Monitors Docker images for updates
- Updates containers via Cronicle-scheduled jobs
- Cleans up old images after updates
- Label-based whitelist for selective updates (34 containers enabled)

**Configuration Strategy:**

**Configuration**:

**Label-based Auto-Update**:
- Label: `com.centurylinklabs.watchtower.enable=true`
- Behavior: Automatically updates when Cronicle job runs (daily at 11 PM)
- Enabled on: All 34 production containers
- Sends Discord notification via Apprise showing what was updated

**See [watchtower/README.md](watchtower/README.md) for complete Watchtower documentation including:**
- HTTP API endpoints and usage
- Cronicle integration details
- Workflow (Phase 1 and Phase 2 with Apprise)
- Environment variables and configuration
- Common operations and troubleshooting

### Apprise - Centralized Notification Hub

**Location**: `services/monitoring/apprise/`
**Port**: 8089
**Access**: `http://ds423plus:8089` or `http://10.10.2.2:8089`

**Purpose**: Unified notification system for sending alerts to Discord, Telegram, and 90+ other platforms

**What it does:**
- Centralizes all notification channels (Discord, Telegram, email, etc.)
- Provides single API for all homelab notifications
- Supports tagging for routing notifications to specific services
- Stateful mode with YAML configuration

**Current Integrations:**
- **Watchtower**: Container update notifications via Discord (✅ Active)
- **Uptime Kuma**: Service availability alerts (planned)
- **Cronicle**: Scheduled job results (planned)
- **Beszel**: Resource threshold alerts (planned)

**Configuration:**
- Notification URLs defined in `/config/apprise.yml`
- Supports Discord webhooks and Telegram bots
- Tag-based routing (watchtower, cronicle, monitoring, critical)

**API Usage:**
```bash
# From containers (use internal port 8000)
curl -X POST http://apprise:8000/notify/apprise \
  -H "Content-Type: application/json" \
  -d '{"title":"Alert","body":"Message","tag":"monitoring"}'

# From host (use external port 8089)
curl -X POST http://localhost:8089/notify/apprise \
  -H "Content-Type: application/json" \
  -d '{"title":"Alert","body":"Message","tag":"monitoring"}'
```

**See [apprise/README.md](apprise/README.md) for complete Apprise documentation including:**
- Discord and Telegram setup guides
- YAML configuration examples
- Integration examples for Cronicle, Watchtower, Uptime Kuma
- API endpoints and usage
- Troubleshooting guide

## Resources

- **Beszel**: [Official Documentation](https://beszel.dev/)
- **Uptime Kuma**: [Official Documentation](https://github.com/louislam/uptime-kuma)
- **Dozzle**: [Official Documentation](https://dozzle.dev/)
- **Watchtower**: [Official Documentation](https://containrrr.dev/watchtower/)
- **Apprise**: [Official Documentation](https://github.com/caronc/apprise) | [API Documentation](https://github.com/caronc/apprise)
