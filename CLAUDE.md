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
**API Key**: `159a3772fe5a3303bf81172da7c4c0ac`

**Purpose**: Schedule and automate recurring tasks (cron replacement with web UI)

**What runs on Cronicle:**
- Kometa operations (library maintenance, collections, overlays, metadata updates)
- ImageMaid cleanup (Plex image optimization)
- Watchtower update checks (daily container update scanning)
- Other scheduled maintenance tasks

**Claude Integration:**
- Claude can create/update/delete Cronicle jobs programmatically using the HTTP API
- Job categories: Media Server (`cmgm06foc04`), Monitoring (`cmgumlb1w1e`)
- When adding jobs for new categories, Claude must ask user to create category via Web UI first

**See [services/infrastructure/cronicle/README.md](services/infrastructure/cronicle/README.md) for complete documentation including:**
- API endpoints and usage examples
- Job categories and category management
- Job timing format and examples
- Shell plugin parameters and script guidelines
- Common job patterns (docker exec, docker run, API calls)
- Troubleshooting and management

## Scripts

Utility scripts for homelab automation and maintenance.

**Location**: `scripts/`

**Available Scripts:**
- **media-download/hardlink_creator.sh**: Creates hardlinks between duplicate files to save disk space
- **media-download/organize_trailers.sh**: Organizes trailer files for Plex libraries

**See [scripts/README.md](scripts/README.md) for complete documentation including:**
- Detailed script descriptions and usage
- Requirements and dependencies
- Best practices for adding new scripts
- Common script patterns
- Integration with Cronicle for scheduling

## GitHub Actions Self-Hosted Runner

**Location**: `services/infrastructure/github-runner/`
**Container**: `github-actions-runner`

**Currently configured for**: `raaphhh/dotfiles` repository (deployment pipeline for homelab repository is not used)

**Key Details:**
- Runner name: `ds423plus-runner-dotfiles`
- Labels: `synology`, `dotfiles`, `self-hosted`
- Uses Docker Socket Proxy for secure container operations
- **Limitation**: Can only serve one repository at a time

**See [services/infrastructure/github-runner/README.md](services/infrastructure/github-runner/README.md) for complete documentation including:**
- Configuration and token generation
- Workflow usage examples
- Multi-repository setup options (multiple runners or organization-level)
- Troubleshooting and migration guide

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