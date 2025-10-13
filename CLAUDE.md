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

- **monitoring/**: Monitoring and management tools (Dozzle, Lazydocker, Uptime-kuma)

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

## Common Operations

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