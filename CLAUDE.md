# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a homelab infrastructure repository that manages Docker-based services on a Synology NAS using docker-compose. The repository contains 38+ services organized into categories.

## Repository Structure

### Service Organization

Services are organized in the `services/` directory with the following categories:

- **media-download/**: Download and acquisition services
  - `_arrs/`: Media management (Sonarr, Radarr, Prowlarr, Bazarr, etc.)
  - `_torrents/`: Torrent-related services (qBittorrent, qbit_manage, cross-seed, autobrr, unpackerr)
  - Other: Jellyseerr, SABnzbd, TheLounge

- **media-servers/**: Media streaming and management
  - `_plex/`: Plex and related services (Plex, Kometa, Autoscan, ImageMaid, Plex-Auto-Languages, Plex-Trakt-Sync)
  - `_jellyfin/`: Jellyfin and Jellyplex-Watched
  - Other: Tautulli, Trailarr

  - Note: The `jellyfin` stack is not really used at the moment. Same for Trailarr.

- **infrastructure/**: Core infrastructure services
  - GitHub Actions runner (self-hosted)
  - Cloudflare DDNS
  - Docker Socket Proxy
  - Ofelia (cron scheduler)

- **monitoring/**: Monitoring and management tools (Beszel, Dozzle, Uptime-kuma, Watchtower)

- **syncthing/**: File synchronization

- **smart-home/**: Smart home services

### Folder Naming Convention

Folders prefixed with `_` (underscore) are **parent categories** that group related services together (e.g., `_arrs`, `_torrents`, `_plex`, `_jellyfin`). These are organizational folders, not individual services.

## Docker Compose Architecture

### Standard Service Structure

Each service directory contains:
- `docker-compose.yml`: Service definition
- `.env.example`: Template for required environment variables (references root `.env`)
- `.env`: Local overrides (gitignored)

### Common Environment Variables

Services use a shared `.env` file at the repository root with common variables:
- `PUID`, `PGID`, `UMASK`: User/group permissions
- `TZ`: Timezone
- `DOCKER_APPDATA_PATH`: Base path for application data/config
- `MEDIAS_PATH`: Base path for media files
- `DOWNLOAD_PATH`: Base path for downloads
- Service-specific variables (VPN credentials, API tokens, etc.)

### Network Architecture

- Most services use an external network called `main`
- Infrastructure services may use `socket_proxy` network
- Some services use `network_mode: host` (e.g., Plex)

### Volume Patterns

Services follow consistent volume mounting:
- Config: `${DOCKER_APPDATA_PATH}/<service>:/config`
- Media: `${MEDIAS_PATH}:/data/medias`
- Downloads: `${DOWNLOAD_PATH}:/downloads`

**Note**: For detailed service-specific documentation (architecture, configuration, usage), refer to the `README.md` file in each service's directory (e.g., `services/monitoring/watchtower/README.md`).

## Common Operations

### Adding a New Service

When adding a new service to the repository:
1. Create the service directory structure with `docker-compose.yml` and `.env.example`
2. **Note on `.gitignore`**: Do NOT create individual `.gitignore` files in service folders. The root `.gitignore` handles all necessary patterns (`.env`, logs, data directories, etc.). Only create a service-specific `.gitignore` if there are unique patterns not covered by the root file.
3. **IMPORTANT**: After adding the service, ask the user if they want to add a monitor for it in Uptime Kuma
4. If yes, add the monitor configuration to `services/monitoring/uptime-kuma/setup_monitors.py` in the appropriate category section
5. Monitor should use the container name (lowercase) and proper endpoint (IP-based for HTTP monitors)

### Deploying a Service

```bash
cd services/<category>/<service-name>
docker-compose up -d
```

### Checking Service Status

```bash
docker-compose ps
docker-compose logs -f <service-name>
```

### Updating a Service

```bash
docker-compose pull
docker-compose up -d
```

### Stopping a Service

```bash
docker-compose down
```

## Monitoring Stack

The homelab uses a multi-layered monitoring approach with complementary tools:

**Stack Architecture:**
```
Layer 1: Availability → Uptime Kuma (Is it alive?)
Layer 2: Performance → Beszel (How is it performing?)
Layer 3: Logs → Dozzle (What happened?)
Layer 4: Updates → Watchtower (Is it up to date?)
Layer 5: Alerting → Apprise/n8n (Notify me)
```

**Services:**
- **Beszel** (port 8091): Hardware & resource monitoring (CPU, RAM, disk, containers)
- **Uptime Kuma** (port 3001): Service availability monitoring (HTTP/Docker/Port checks)
- **Dozzle** (port 8088): Real-time log viewer with SQL queries
- **Watchtower** (port 8082): Container update automation with HTTP API

**See [services/monitoring/README.md](services/monitoring/README.md) for complete monitoring stack documentation.**

## Cronicle - Job Scheduler

**Location**: `services/infrastructure/cronicle/`
**Port**: 3012
**Access**: `http://nas:3012`
**API Key**: Available in `.env` file as `CRONICLE_API_KEY=159a3772fe5a3303bf81172da7c4c0ac`

**Purpose**: Schedule and automate recurring tasks (cron replacement with web UI)

**What runs on Cronicle:**
- Kometa operations (library maintenance, collections, overlays, metadata updates)
- ImageMaid cleanup (Plex image optimization)
- Watchtower update checks (daily container update scanning)
- Other scheduled maintenance tasks

### Managing Cronicle Jobs via API

**Important**: Claude can create/update/delete Cronicle jobs programmatically using the HTTP API.

**API Endpoints:**
- Base URL: `http://10.10.2.2:3012/api/app/`
- API Key: `159a3772fe5a3303bf81172da7c4c0ac` (passed as query parameter)

**Common Operations:**

```bash
# List all scheduled jobs
curl -s "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac"

# Get job status
curl -s "http://10.10.2.2:3012/api/app/get_job_status/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac&id=JOB_ID"

# Trigger job manually
curl -s -X POST "http://10.10.2.2:3012/api/app/run_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID"}'

# Create new event (job)
curl -s -X POST "http://10.10.2.2:3012/api/app/create_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{
    "title": "Job Title",
    "enabled": 1,
    "category": "CATEGORY_ID",
    "plugin": "shellplug",
    "target": "allgrp",
    "params": {
      "script": "#!/bin/bash\necho \"Job script here\"",
      "annotate": 1
    },
    "timing": {
      "hours": [3],
      "minutes": [0]
    },
    "timezone": "Europe/Brussels",
    "notes": "Job description"
  }'

# Update existing event
curl -s -X POST "http://10.10.2.2:3012/api/app/update_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID", ...}'

# Delete event
curl -s -X POST "http://10.10.2.2:3012/api/app/delete_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID"}'
```

### Job Categories

Cronicle jobs are organized by categories. Current categories:
- **Media Server** (`cmgm06foc04`) - Kometa, ImageMaid, Plex-related jobs
- **Monitoring** (`cmgumlb1w1e`) - Watchtower, monitoring, health check jobs

**When Claude adds a Cronicle job:**

1. **For existing services in known categories**: Add the job to the appropriate category:
   - **Media Server jobs**: Kometa, ImageMaid, Plex, Jellyfin operations → Use `cmgm06foc04`
   - **Monitoring jobs**: Watchtower, Beszel checks, Uptime Kuma tasks → Use `cmgumlb1w1e`

2. **For services that don't fit existing categories**: Ask the user:
   - "This job is for [SERVICE_NAME] which doesn't fit existing categories (Media Server, Monitoring). Should I:
     - Add it to one of the existing categories? Which one?
     - Create a new category? If so, what should it be called?"

3. **If user requests a new category**:
   - Ask the user to create it via Cronicle web UI (Admin > Categories)
   - Reason: The `create_category` API requires admin authentication which Claude doesn't have
   - Once created, ask the user for the new category ID (format: `cmXXXXXXXXX`)
   - Update this section in CLAUDE.md with the new category

4. **Category naming convention**:
   - Use clear, descriptive names (e.g., "Media Server", "Infrastructure", "Monitoring")
   - Categories help organize jobs in the Cronicle UI
   - Choose colors that make categories visually distinct

### Job Timing Format

Cronicle uses a timing object for scheduling (similar to cron but JSON format):

```json
{
  "timing": {
    "years": [2025],           // Optional: specific years
    "months": [1, 6, 12],      // Optional: specific months (1-12)
    "days": [1, 15],           // Optional: specific days of month (1-31)
    "weekdays": [0, 6],        // Optional: specific weekdays (0=Sunday, 6=Saturday)
    "hours": [3],              // Hours (0-23)
    "minutes": [0, 30]         // Minutes (0-59)
  },
  "timezone": "Europe/Brussels"
}
```

**Examples:**
- Daily at 3 AM: `{"hours": [3], "minutes": [0]}`
- Every 6 hours: `{"hours": [0, 6, 12, 18], "minutes": [0]}`
- Three times a day: `{"hours": [5, 13, 21], "minutes": [0]}`
- Weekly on Sunday at 2 AM: `{"weekdays": [0], "hours": [2], "minutes": [0]}`

### Shell Plugin Parameters

Most jobs use the Shell Plugin (`"plugin": "shellplug"`) with these parameters:

```json
{
  "params": {
    "script": "#!/bin/bash\nYOUR_SCRIPT_HERE",
    "annotate": 1,           // Add timestamps to log output
    "json": 0,               // Parse JSON in output (usually 0)
    "lang": "shell",         // Syntax highlighting
    "theme": "default"       // Editor theme
  }
}
```

**Script guidelines:**
- Always include shebang: `#!/bin/bash`
- Use `docker exec` for running commands in containers
- Add `-u` flag for unbuffered output: `python3 -u script.py`
- Return proper exit codes (0 = success, non-zero = failure)

### Common Job Patterns

**Docker exec pattern:**
```bash
#!/bin/bash
docker exec CONTAINER_NAME command --flags
```

**Docker run pattern (for one-off containers):**
```bash
#!/bin/bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=tcp://docker-proxy:2375 \
  --network socket_proxy \
  IMAGE_NAME \
  --flags
```

**API call pattern:**
```bash
#!/bin/bash
TOKEN="${ENV_VARIABLE}"
curl -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  "http://service:port/api/endpoint"
```

### Example: Adding a Watchtower Daily Check Job

When Claude is asked to add a Watchtower daily check job:

```json
{
  "title": "Watchtower - Daily Update Check",
  "enabled": 1,
  "category": "cmgumlb1w1e",
  "plugin": "shellplug",
  "target": "allgrp",
  "params": {
    "script": "#!/bin/bash\n# Check for container updates\n\ndocker run --rm \\\n  -v /var/run/docker.sock:/var/run/docker.sock \\\n  -e DOCKER_HOST=tcp://docker-proxy:2375 \\\n  --network socket_proxy \\\n  containrrr/watchtower \\\n  --run-once \\\n  --label-enable \\\n  2>&1 | tee /tmp/watchtower-check.log\n\n# Future Phase 2: Parse output and send Apprise notifications",
    "annotate": 1,
    "lang": "shell",
    "theme": "default"
  },
  "timing": {
    "hours": [3],
    "minutes": [0]
  },
  "timezone": "Europe/Brussels",
  "notes": "Daily container update check. Auto-updates Tier 1 containers, logs updates for Tier 2 (manual approval).",
  "max_children": 1,
  "timeout": 0
}
```

### Troubleshooting Cronicle Jobs

**View job logs:**
- Check via Cronicle web UI: http://nas:3012
- Or via filesystem: `/volume2/docker/appdata/cronicle/logs/jobs/`

**Common issues:**
- **Permission errors**: See CLAUDE.md "Troubleshooting > Cronicle Shell Plugin Permission Issues"
- **Temp directory errors**: Ensure `TMP=/opt/cronicle/tmp` is set in docker-compose.yml
- **Log directory errors**: Ensure logs directory has 755 permissions

**Job execution notes:**
- Jobs support Python scripts with proper shebang: `#!/usr/bin/env python3`
- Jobs can accept parameters (future enhancement)
- Jobs can chain together (run job B after job A completes)
- Jobs can have webhooks for external triggers

## Scripts

Located in `scripts/media-download/`:

- **hardlink_creator.sh**: Creates hardlinks between duplicate files across folders to save disk space
  - Uses `jdupes` to find duplicates (files >100MB)
  - Keeps original files, replaces copies with hardlinks
  - Has episode detection to avoid linking different episodes with same content
  - Usage: `./hardlink_creator.sh /path/to/original /path/to/copy`

- **organize_trailers.sh**: Organizes trailer files

## Deployment Pipeline

- Note: The GitHub Actions deployment pipeline for the homelab repository is currently not used.

### Self-Hosted Runner
- Runs on Synology NAS (container: `github-actions-runner`)
- **Currently configured for**: `raaphhh/dotfiles` repository
- Labels: `synology,dotfiles,self-hosted`
- Runner name: `ds423plus-runner-dotfiles`
- Uses Docker Socket Proxy for security
- Configuration in [services/infrastructure/github-runner](services/infrastructure/github-runner)

**Note**: This runner can only serve one repository at a time. To use it with multiple personal repositories, you would need to either:
- Run multiple runner instances (one per repository)
- Create a free GitHub organization and use organization-level runners

## Development Notes

### When Modifying Services

1. **Environment Variables**:
   - Never commit actual `.env` files (gitignored)
   - Update `.env.example` when adding new variables
   - Variables should reference root `.env` values in the format: `VARNAME=VARNAME`

2. **Docker Compose Files**:
   - Use external networks (declare as `external: true`)
   - Follow volume mounting patterns for consistency
   - Use `ghcr.io/hotio/*` images where available for media services
   - Set `restart: always` for production services

3. **Service Categories**:
   - Place services in appropriate category folders
   - Use `_` prefix for grouping folders (not individual services)
   - Each service gets its own subdirectory with docker-compose.yml

### Theme Park Integration

All the services using hotio's containers support Theme Park for UI theming:
- Environment variables: `TP_HOTIO=true`, `TP_THEME=<theme-name>`
- Themes: `catppuccin-mocha`, `organizr`
- Volume mount: `${DOCKER_APPDATA_PATH}/themepark/98-themepark-<service>:/etc/cont-init.d/98-themepark`

## Git Workflow

- Main branch: `main`
- Use descriptive commit messages following the existing style (see recent commits)
- Prefix commits with scope: `[global]`, `[media-download]`, `[scripts]` nor `[service-name]` if changes affects only one single service.

## Git Configuration

This repository uses a specific SSH key configuration:
- **Remote**: `github-personal:raaphhh/homelab.git`
- **SSH Host**: `github-personal` (configured in ~/.ssh/config)
- **SSH Key**: `~/.ssh/id_ed25519_personal`

When cloning or working with this repository, ensure you're using the `github-personal` SSH host alias, not the direct `github.com` URL.

## Linear Issue Management

**Default Project:** All Linear issues for this homelab repository should be created in the **"self-hosted"** project unless otherwise specified.

When creating issues related to this repository, always use the "self-hosted" project by default.

### Linear MCP Not Working in Cursor/VSCode

**Issue:** Linear MCP server connection fails with error `SSE MCP servers are currently not supported in native builds.`

**Root Cause:**
- Linear's official MCP server uses SSE (Server-Sent Events) transport
- Claude Code's native binary (used by Cursor/VSCode extensions) does NOT support SSE MCP servers
- This is a platform limitation, not a configuration issue
- The Linear MCP configuration in `~/.claude.json` is correct but cannot be used in IDE extensions

**Verification:**
Check Claude extension logs for this error:
```
[ERROR] MCP server "linear" Connection failed: SSE MCP servers are currently not supported in native builds.
```

**Workaround - Use Linear GraphQL API:**

Since the Linear MCP doesn't work in Cursor/VSCode, use the Linear GraphQL API directly via curl:

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: lin_api_b5FUKZXuG93dR2A7PiNBGzqUMQmCIs3Gs9pcgJaw" \
  -H "Content-Type: application/json" \
  -d '{"query":"query { issue(id: \"ISSUE-ID\") { id title description state { name } assignee { name } labels { nodes { name } } createdAt updatedAt } }"}' \
  | python3 -m json.tool
```

Replace `ISSUE-ID` with the actual issue identifier (e.g., `RGR-113`).

**Note:** The Linear MCP works fine in the Claude CLI (`claude` command), but not in IDE extensions. If you need full MCP functionality, use the CLI version of Claude Code instead of the Cursor/VSCode extension.

## Troubleshooting

### Unresponsive Docker Containers on Synology

If Docker containers become completely unresponsive (commands like `docker exec`, `docker inspect`, `docker logs` hang indefinitely), this is a known issue with Synology's ContainerManager and BTRFS storage driver.

**Symptoms:**
- All Docker commands targeting a specific container timeout
- Container appears to be running but is not responsive
- Cannot stop or restart the container normally

**Solution:**
Restart the ContainerManager service to reset all containers:

```bash
sudo /var/packages/ContainerManager/scripts/start-stop-status stop
sudo /var/packages/ContainerManager/scripts/start-stop-status start
```

**Important Notes:**
- This will restart ALL Docker containers on the system
- Containers with `restart: always` will come back automatically
- This is the Synology-specific way to manage Docker (not standard `systemctl`)
- The issue is related to BTRFS and Docker's interaction with the Synology kernel

### Cronicle Shell Plugin Permission Issues

When running Cronicle on Synology with shell scripts, you may encounter permission errors preventing job execution.

**Two common issues:**

1. **Temp directory execution restrictions** (GitHub issue [#673](https://github.com/jhuckaby/Cronicle/issues/673))
   - **Symptom:** Shell plugin crashes immediately, "Permission denied" on temp scripts
   - **Cause:** `/tmp` mounted with noexec restrictions
   - **Solution:** Set custom temp directory with execution permissions
   ```yaml
   environment:
     - TMP=/opt/cronicle/tmp
     - TMPDIR=/opt/cronicle/tmp
   volumes:
     - ${DOCKER_APPDATA_PATH}/cronicle/tmp:/opt/cronicle/tmp:rw
   ```

2. **Log directory access restrictions**
   - **Symptom:** "EACCES: permission denied" when writing to `/opt/cronicle/logs/jobs/*.log`
   - **Cause:** Parent `/opt/cronicle/logs/` directory has 700 permissions (owner-only)
   - **Solution:** Make logs directory readable by the shell plugin user
   ```bash
   chmod 755 /volume2/docker/appdata/cronicle/logs
   # Or inside container:
   docker exec cronicle chmod 755 /opt/cronicle/logs/
   ```

Both fixes are required for Cronicle shell plugin to work properly on Synology NAS.