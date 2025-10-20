# Watchtower - Container Update Automation

Automated Docker container update management with human-in-the-loop workflow.

## Overview

Watchtower monitors Docker images for updates and can automatically update containers based on a label-based whitelist system. This instance is configured to work with Cronicle for scheduled checks and uses HTTP API mode for manual approval workflows.

## Setup

### 1. Generate API Token

```bash
openssl rand -base64 32
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and set the generated token:

```bash
cp .env.example .env
# Edit .env and add:
# - WATCHTOWER_HTTP_API_TOKEN=your-generated-token
```

Also ensure the root `.env` file contains:
- `TZ`: Timezone
- `DOCKER_HOST`: Docker Socket Proxy endpoint (e.g., `tcp://docker-proxy:2375`)

### 3. Deploy Container

```bash
docker-compose up -d
```

### 4. Verify HTTP API

```bash
# Test API endpoint (should return 401 without token)
curl http://localhost:8082/v1/update

# Test with token
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8082/v1/update
```

## Container Labeling

Watchtower uses labels to determine which containers to automatically update:

### Auto-Update (All Labeled Containers)

Add to container's `docker-compose.yml`:
```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

**Currently configured: 34 containers** including watchtower, dozzle, uptime-kuma, all *arr services, qBittorrent, Plex, Tautulli, Jellyseerr, SABnzbd, and most other production services.

### Ignored (Critical Infrastructure)

Don't add any labels. Watchtower will ignore these containers.

**Examples**: Kometa (version-controlled config), Portainer, Trailarr

## Usage

### Manual Check for Updates

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=tcp://docker-proxy:2375 \
  --network socket_proxy \
  containrrr/watchtower \
  --run-once --monitor-only --label-enable
```

### Update All Labeled Containers via API

```bash
curl -X POST \
  -H "Authorization: Bearer ${WATCHTOWER_HTTP_API_TOKEN}" \
  http://localhost:8082/v1/update
```

### Update Specific Container(s) via API

```bash
curl -X POST \
  -H "Authorization: Bearer ${WATCHTOWER_HTTP_API_TOKEN}" \
  "http://localhost:8082/v1/update?images=sonarr,radarr"
```

## Cronicle Integration

A single Cronicle job handles daily updates and notifications:

**Job**: "Watchtower - Daily Container Update Check" (ID: emgumobon1f)
**Category**: Monitoring (cmgumlb1w1e)
**Schedule**: Daily at 3 AM Europe/Brussels timezone

The job runs Watchtower to check for updates, applies them automatically to labeled containers, and sends a Discord notification via Apprise with:
- List of updated containers
- Version information (old → new)
- Changelog links for each updated container
- Timestamp of the update

**Notification Script**: `scripts/monitoring/watchtower_run_and_notify.sh`
- Have to be copied manually in Cronicle job

**Key Features**:
- Automatic updates for all labeled containers
- Clean version display (handles edge cases like autopulse "main" → "latest (YYYY-MM-DD)")
- Direct links to changelog/releases for each container
- Discord notifications with rich formatting

## Workflow

### Current Implementation

1. **Cronicle triggers** daily at 3 AM Europe/Brussels timezone
2. **Watchtower runs** update check on all 34 labeled containers:
   - Checks for new images
   - Pulls new images if available
   - Stops old containers
   - Starts new containers with updated images
   - Cleans up old images
3. **If updates were applied**:
   - Script parses Watchtower logs
   - Extracts container names, versions, and images
   - Generates changelog URLs for each updated container
   - Sends Discord notification via Apprise
4. **Discord notification includes**:
   - Title: "X Containers Updated"
   - List of updated containers with:
     - Container name
     - New version number
     - Changelog link (GitHub releases or hotio.dev)
   - Watchtower logo and timestamp
5. **Audit trail**: All updates tracked in Discord channel with full history

## Monitoring

Watchtower is monitored by Uptime Kuma:
- **Monitor type**: Docker container status
- **Container name**: `watchtower`
- **Check interval**: 120 seconds
- Note: Docker monitoring is used instead of HTTP because Watchtower's API endpoints require authentication. Since Watchtower is a background service, monitoring container status is sufficient.

## Troubleshooting

### Check Watchtower logs
```bash
docker-compose logs -f watchtower
```

### Verify labeled containers
```bash
docker ps --filter "label=com.centurylinklabs.watchtower.enable=true"
```

### Test manual update check
```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=tcp://docker-proxy:2375 \
  --network socket_proxy \
  containrrr/watchtower \
  --run-once --debug --label-enable
```

## Important Notes

- **34 containers currently labeled** with `watchtower.enable=true` for automatic updates
- **No `monitor-only` labels** - all labeled containers update automatically
- Watchtower itself has the `enable=true` label and can update itself
- **Ignored containers** (no labels): Kometa, Portainer, Trailarr
  - Kometa: version-controlled config could break if auto-updated
  - Portainer: manual management UI, should be updated manually
  - Trailarr: manually managed service
- HTTP API mode enabled for potential future manual triggers
- All scheduling is managed by Cronicle (Job ID: emgumobon1f), not Watchtower's built-in scheduler
- Discord notifications sent via Apprise (tag: `watchtower`)
- Script location: `scripts/monitoring/watchtower_run_and_notify.sh` (copied into Cronicle job)

## Resources

- [Official Documentation](https://containrrr.dev/watchtower/)
- [HTTP API Documentation](https://containrrr.dev/watchtower/http-api-mode/)
- [Container Selection](https://containrrr.dev/watchtower/container-selection/)
