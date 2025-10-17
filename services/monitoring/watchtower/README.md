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

Watchtower uses labels to determine which containers to check and update:

### Tier 1: Auto-Update (Low Risk)

Add to container's `docker-compose.yml`:
```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

**Currently configured (5 containers)**: watchtower, dozzle, uptime-kuma, cloudflare-ddns, beszel-agent

### Tier 2: Manual Approval (Medium/High Risk)

Add to container's `docker-compose.yml`:
```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
  - "com.centurylinklabs.watchtower.monitor-only=true"
```

**Currently configured (29 containers)**: All *arr services, qBittorrent, Plex, Tautulli, Jellyseerr, SABnzbd, and most other services

### Tier 3: Ignored (Critical Infrastructure)

Don't add any labels. Watchtower will ignore these containers.

Examples: Docker Socket Proxy, GitHub Actions Runner, Beszel hub, Kometa

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

A single Cronicle job handles daily update checks:

**Job**: "Watchtower - Daily Update Check" (ID: emgumobon1f)
**Category**: Monitoring (cmgumlb1w1e)
**Schedule**: Daily at 3 AM Europe/Brussels timezone

```bash
#!/bin/bash
# Daily container update check

docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=tcp://docker-proxy:2375 \
  --network socket_proxy \
  containrrr/watchtower \
  --run-once \
  --label-enable \
  2>&1 | tee /tmp/watchtower-check.log

# Future Phase 2: Parse output and send Apprise notifications
```

**Note**: There is NO manual trigger job in Cronicle. Phase 2 will have Apprise call the Watchtower HTTP API directly when users approve updates via notification buttons.

## Workflow

### Current (Phase 1)
1. Cronicle runs daily check at 3 AM
2. Watchtower checks all 34 labeled containers for updates
3. **Tier 1 (auto-update)**: 5 containers update automatically
4. **Tier 2 (manual)**: 29 containers log available updates for manual review
5. User reviews logs and can manually trigger updates via HTTP API if desired

### Future (Phase 2 - With Apprise)
1. Cronicle runs daily check at 3 AM
2. **Tier 1 auto-updates** → Sends notification (audit trail only)
   - Notification format: "Container X updated: v1.0 → v1.1"
3. **Tier 2 updates available** → Sends notification with:
   - Container name, versions (old → new)
   - Changelog link (GitHub releases or Docker Hub)
   - [Approve Update] button
4. **User clicks approve** → Apprise webhook calls Watchtower HTTP API directly → Container updates
5. All updates tracked in Discord/Telegram channel for audit history

**Key difference from Phase 1**: Apprise calls Watchtower HTTP API directly (no Cronicle manual trigger job needed)

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

- **34 containers currently labeled**: 5 auto-update, 29 manual approval
- Watchtower itself has the `enable=true` label and can update itself
- Kometa is in Tier 3 (ignored) - version-controlled config could break if auto-updated
- Docker Socket Proxy, GitHub Actions Runner, Beszel hub also in Tier 3 (critical infrastructure)
- Use `--monitor-only` flag for dry-run checks without updates
- HTTP API requires authentication token for all requests
- All scheduling is managed by Cronicle (Job ID: emgumobon1f), not Watchtower's built-in scheduler
- Phase 2 will use Apprise to call HTTP API directly (no manual Cronicle jobs)

## Resources

- [Official Documentation](https://containrrr.dev/watchtower/)
- [HTTP API Documentation](https://containrrr.dev/watchtower/http-api-mode/)
- [Container Selection](https://containrrr.dev/watchtower/container-selection/)
