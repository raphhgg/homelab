# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a homelab infrastructure repository that manages Docker-based services on a Synology NAS using docker-compose. The repository contains 38+ services organized into categories, with automated deployment via GitHub Actions.

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
  - Other: Tautulli, Trailarr, Yamtrack

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

The repository uses GitHub Actions for automated deployment:

### Triggers
- **Automatic**: Push to `main` branch affecting `services/**`
- **Manual**: Workflow dispatch with dry-run or deploy-all options

### Workflow Process
1. **Environment Setup**: Creates `.env` from GitHub secrets
2. **Deploy Services**: Deploys changed or all services
3. **Sync to NAS**: Syncs repository to compose directory on NAS
4. **Notify**: Sends status to Discord

### Self-Hosted Runner
- Runs on Synology NAS (container: `github-actions-runner`)
- Labels: `synology,docker,self-hosted`
- Uses Docker Socket Proxy for security
- Configuration in [services/infrastructure/github-runner](services/infrastructure/github-runner)

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

### Media Download Hardlink System

Recent commits show a hardlink setup between download locations and final media storage:
- qBittorrent and SABnzbd download to temporary locations
- Services like Sonarr/Radarr use hardlinks to move files to final locations
- The `hardlink_creator.sh` script helps deduplicate existing files
- This saves disk space while maintaining seeding capability

### Theme Park Integration

Many services support Theme Park for UI theming:
- Environment variables: `TP_HOTIO=true`, `TP_THEME=<theme-name>`
- Themes: `catppuccin-mocha`, `organizr`
- Volume mount: `${DOCKER_APPDATA_PATH}/themepark/98-themepark-<service>:/etc/cont-init.d/98-themepark`

## Commit Message Guidelines

**Important**: This repository does NOT use Claude Code's default commit message format. When making commits:

- **DO NOT** include "🤖 Generated with [Claude Code](https://claude.ai/code)" lines
- **DO NOT** include "Co-Authored-By: Claude <noreply@anthropic.com>" lines
- **DO NOT** add any Claude attribution or generation markers

Use clean, standard commit messages that focus on the changes made. The commit history has been cleaned to remove previous Claude attribution lines and should remain that way.

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