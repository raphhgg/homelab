# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a homelab infrastructure repository that manages Docker-based services on a Synology NAS using docker-compose. The repository contains 34+ services organized into categories.

## Repository Structure

### Service Organization

Services are organized in the `services/` directory with the following categories:

- **media-download/**: Download and acquisition services
  - `_arrs/`: Media management (Sonarr, Radarr, Prowlarr, Bazarr, etc.)
  - `_torrents/`: Torrent-related services (qBittorrent, qbit_manage, cross-seed, autobrr, unpackerr)
  - Other: Jellyseerr, SABnzbd, TheLounge

- **media-server/**: Media streaming and management
  - Plex and related services: Plex, Kometa, ImageMaid, Plex-Auto-Languages, Plex-Trakt-Sync
  - Other: Tautulli, Trailarr

- **infrastructure/**: Core infrastructure services
  - Cronicle (job scheduler)
  - GitHub Actions runner (self-hosted)
  - Cloudflare DDNS
  - Docker Socket Proxy

- **monitoring/**: Monitoring and management tools (Apprise, Beszel, Dozzle, Uptime-kuma, Watchtower)

- **syncthing/**: File synchronization

- **smart-home/**: Smart home services

### Folder Naming Convention

Folders prefixed with `_` (underscore) are **parent categories** that group related services together (e.g., `_arrs`, `_torrents`). These are organizational folders, not individual services.

## Docker Compose Architecture

### Standard Service Structure

Each service directory contains:
- `docker-compose.yml`: Service definition
- `.env.example`: Template for required environment variables
- `.env`: Actual environment values (gitignored, created from `.env.example`)

### Common Environment Variables

Services use individual `.env` files in each service directory (**not** a shared root `.env`). Common variables across services:
- `PUID=1000`, `PGID=1000`: User/group permissions
- `TZ=Europe/Brussels`: Timezone
- `DOCKER_APPDATA_PATH=/volume2/docker/appdata`: Base path for application data/config
- `MEDIAS_PATH=/volume1/medias`: Base path for media files
- `DOWNLOAD_PATH=/volume1/downloads`: Base path for downloads
- `DOCKER_HOST=tcp://docker-proxy:2375`: Docker Socket Proxy endpoint (for services needing Docker API access)
- Service-specific variables (VPN credentials, API tokens, etc.)

**Note**: Each service's `.env` file is created from its `.env.example` template. Values are either filled in directly or reference the same standard values listed above.

### Network Architecture

- Most services use an external network called `main`
- Infrastructure services may use `socket_proxy` network
- Some services use `network_mode: host` (e.g., Plex)

### Volume Patterns

Services follow consistent volume mounting:
- Config: `${DOCKER_APPDATA_PATH}/<service>:/config`
- Media: `${MEDIAS_PATH}:/data/medias`
- Downloads: `${DOWNLOAD_PATH}:/downloads`

**Note**: For detailed service-specific documentation (architecture, configuration, usage), refer to the `README.md` file in each service's directory (e.g., `services/monitoring/watchtower/README.md`) or in a subcategory (e.g., `monitoring/README.md`, `infrastructure/README.md`).

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

The homelab uses a multi-layered monitoring approach with complementary tools.

**See [services/monitoring/README.md](services/monitoring/README.md) for complete monitoring stack documentation.**

## Cronicle - Job Scheduler

**Location**: `services/infrastructure/cronicle/`
**Purpose**: Schedule and automate recurring tasks (cron replacement with web UI)
**Claude Integration:** Claude can create/update/delete Cronicle jobs programmatically using the HTTP API

**See [services/infrastructure/cronicle/README.md](services/infrastructure/cronicle/README.md) for complete documentation.**

## Scripts

Utility scripts for homelab automation and maintenance.

**Location**: `scripts/`

**See [scripts/README.md](scripts/README.md) for complete documentation.**

## GitHub Actions Self-Hosted Runner

**Location**: `services/infrastructure/github-runner/`

**See [services/infrastructure/github-runner/README.md](services/infrastructure/github-runner/README.md) for complete documentation.**

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

Since the Linear MCP doesn't work in Cursor/VSCode, use the Linear GraphQL API directly via curl.

**API Key Location**: The Linear API key is stored in `/volume2/docker/compose/.secrets` (gitignored for security).

**Example Usage**:

```bash
# Read API key from file
LINEAR_KEY=$(grep LINEAR_API_KEY /volume2/docker/compose/.secrets | cut -d'=' -f2)

# Query issue details
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"query { issue(id: \"ISSUE-ID\") { id title description state { name } assignee { name } labels { nodes { name } } createdAt updatedAt } }"}' \
  | python3 -m json.tool
```

Replace `ISSUE-ID` with the actual issue identifier (e.g., `RGR-17`).

**Common Operations**:

```bash
# Update issue description
LINEAR_KEY=$(grep LINEAR_API_KEY /volume2/docker/compose/.secrets | cut -d'=' -f2)
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/linear_mutation.json \
  | python3 -m json.tool
```

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

See [services/infrastructure/cronicle/README.md#shell-plugin-permission-issues](services/infrastructure/cronicle/README.md#shell-plugin-permission-issues) for detailed troubleshooting of Cronicle permission issues on Synology NAS.