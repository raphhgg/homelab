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

- **monitoring/**: Monitoring and management tools (Beszel, Dozzle, Lazydocker, Uptime-kuma)

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

### Special Case: Kometa (Version-Controlled Configuration)

**Kometa uses a unique dual-volume setup to separate version-controlled configuration from runtime artifacts.**

**Structure:**
```
services/media-servers/_plex/kometa/
├── docker-compose.yml
└── config/                          # VERSION CONTROLLED
    ├── config.yml                   # Main configuration
    ├── collections/                 # Collection definitions
    │   ├── movies/
    │   └── tvshows/
    ├── custom_fonts/                # Custom fonts for overlays
    ├── .gitignore                   # Ignores symlinks and backups
    └── [symlinks - created at runtime, NOT tracked]
        ├── logs -> /data/logs
        ├── config.cache -> /data/config.cache
        └── UUID -> /data/UUID
```

**Volume Mounts:**
```yaml
volumes:
  - ./config:/config-repo:rw        # Config from git repo
  - ${DOCKER_APPDATA_PATH}/kometa:/data:rw  # Runtime data
environment:
  - KOMETA_CONFIG=/config-repo/config.yml
```

**Runtime Files (in appdata, NOT git):**
- `/data/logs/` - Log files (~200MB)
- `/data/overlays/` - Generated overlay images (~3GB)
- `/data/assets/` - Custom posters/artwork (~26MB)
- `/data/config.cache` - Runtime cache (~54MB)
- `/data/UUID` - Instance identifier
- `/data/missing/` - Generated reports

**Path Convention in config.yml:**
- Configuration files: `/config-repo/collections/...`, `/config-repo/custom_fonts/...`
- Runtime files: `/data/assets/...`, `/data/missing/...`, `/data/overlays/...`

**Symlinks:**
Container entrypoint automatically creates symlinks on startup to redirect Kometa's runtime files to appdata:
```bash
ln -sf /data/logs /config-repo/logs
ln -sf /data/config.cache /config-repo/config.cache
ln -sf /data/UUID /config-repo/UUID
```

**Why This Approach:**
- ✅ Only ~600KB of pure configuration in git repo
- ✅ ~3.5GB of runtime artifacts stay in appdata
- ✅ Clean separation for backups and version control
- ✅ Container fully reproducible from git repo
- ✅ Scheduled execution via Cronicle (external scheduling)

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

### Beszel - Hardware & Resource Monitoring

**Location**: `services/monitoring/beszel/`
**Port**: 8091
**Access**: `http://nas:8091`

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
**Access**: `http://nas:3001`

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

### Dozzle - Log Viewer

**Location**: `services/monitoring/dozzle/`
**Port**: 8088
**Access**: `http://nas:8088`

**Purpose**: Real-time Docker container log viewing

**Key features:**
- Live streaming logs
- SQL queries on log data
- Shell access to containers
- Multi-host support

### Monitoring Stack Architecture

```
Layer 1: Availability → Uptime Kuma (Is it alive?)
Layer 2: Performance → Beszel (How is it performing?)
Layer 3: Logs → Dozzle (What happened?)
Layer 4: Alerting → Apprise/n8n (Notify me)
```

**When to use what:**
- Service went down? → Check Uptime Kuma for uptime status
- High CPU/memory? → Check Beszel for resource usage trends
- Service behaving oddly? → Check Dozzle for error logs
- Need historical performance data? → Check Beszel charts

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