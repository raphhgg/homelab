# CLAUDE.md

Instructions for AI agents working with this homelab Docker Compose repository on a Synology NAS.

## Repository Overview

Homelab infrastructure managing Docker services organized in `services/` by category. Each service has its own directory with `docker-compose.yml`, `.env.example`, and `.env`.

## Standard Values

These are the **actual values** used across all services. Use them when creating `.env` files:

| Variable               | Value                       |
|------------------------|-----------------------------|
| `PUID`                 | `1000`                      |
| `PGID`                 | `100`                       |
| `TZ`                   | `Europe/Brussels`           |
| `DOCKER_APPDATA_PATH`  | `/home/raphh/docker/appdata`|
| `MEDIAS_PATH`          | `/mnt/data/medias`          |
| `DOWNLOAD_PATH`        | `/mnt/downloads`            |

## Service Conventions

### Directory Structure

Each service lives in `services/<category>/<service-name>/` with:
- `docker-compose.yml` — service definition
- `.env.example` — template (committed to git)
- `.env` — actual values (gitignored, created from `.env.example`)

### docker-compose.yml Patterns

- Use `docker compose` (v2 CLI), **never** `docker-compose` (v1)
- Set `restart: always` for all production services
- Use `ghcr.io/hotio/*` images where available for media services
- External shared networks use `external: true`; local per-stack networks are declared without it

### .env Files (CRITICAL)

**Every standard variable referenced in `docker-compose.yml` MUST be present** in both `.env.example` and `.env`. Cross-check the compose file's `${VAR}` references against the Standard Values table — missing variables will cause silent failures.

**`.env.example`** (committed to git) — **MUST use placeholder format, NEVER actual values**:
- Standard shared vars: `VARNAME=VARNAME` (e.g., `PUID=PUID`, `TZ=TZ`)
- Service-specific secrets: descriptive placeholder (e.g., `API_TOKEN=your_api_token_here`)
- `DOCKER_APPDATA_PATH`, `MEDIAS_PATH`, `DOWNLOAD_PATH` — these are **only used in volume mounts** in `docker-compose.yml`. They must be in `.env` files but are **NOT container environment variables** (never put them in the `environment:` section).

WRONG `.env.example` — uses actual values:
```
PUID=1000
TZ=Europe/Brussels
DOCKER_APPDATA_PATH=/home/raphh/docker/appdata
```

RIGHT `.env.example` — uses placeholders:
```
PUID=PUID
TZ=TZ
DOCKER_APPDATA_PATH=DOCKER_APPDATA_PATH
```

**`.env`** (gitignored) uses **actual values** from the Standard Values table above, plus real secrets.

**Commenting rules**: Do NOT add comments for standard variables (PUID, PGID, TZ, etc.) — they are self-explanatory. Only add comments for commented-out optional variables or service-specific secrets that need clarification.

**Full example** — a service using PUID, PGID, TZ, DOCKER_APPDATA_PATH, and an optional API key:

`.env.example`:
```
PUID=PUID
PGID=PGID
TZ=TZ
DOCKER_APPDATA_PATH=DOCKER_APPDATA_PATH
# Optional: override default (auto-generated on first run)
# API_KEY=your_api_key_here
```

`.env`:
```
PUID=1000
PGID=100
TZ=Europe/Brussels
DOCKER_APPDATA_PATH=/home/raphh/docker/appdata
# Optional: override default (auto-generated on first run)
# API_KEY=your_api_key_here
```

### Docker Socket Proxy — Dedicated Per-Service (CRITICAL)

**Only services that need Docker API access** (e.g., monitoring containers, managing other containers) should use a socket proxy. Most services do NOT need this — **do not add a socket proxy unless the service genuinely requires Docker API access.**

**NEVER mount `/var/run/docker.sock` directly into a service container.** Each service that needs Docker API access gets its own dedicated `tecnativa/docker-socket-proxy` sidecar with **minimal permissions** (principle of least privilege), connected via a **local network** isolated to that compose stack.

#### How to add a dedicated socket proxy:

1. Add a `<service>-proxy` container using `tecnativa/docker-socket-proxy` with only the permissions needed
2. Add a local `socket_net` network (NOT external) — only the proxy and the app join it
3. Hardcode `DOCKER_HOST=tcp://<service>-proxy:2375` in the app's environment (no `.env` variable needed)
4. Add `depends_on: <service>-proxy` to the app container
5. The proxy mounts `/var/run/docker.sock:/var/run/docker.sock:ro` — the app container does NOT

#### Permission reference:

| Permission     | What it allows            | Example services       |
| -------------- | ------------------------- | ---------------------- |
| `CONTAINERS=1` | Read container list/stats | All (minimum)          |
| `EVENTS=1`     | Stream container events   | Log streaming tools    |
| `IMAGES=1`     | Pull/list images          | Watchtower             |
| `POST=1`       | Create/modify resources   | Watchtower, Autopulse  |
| `DELETE=1`     | Delete containers         | Watchtower             |
| `NETWORKS=1`   | Manage networks           | Watchtower             |
| `VOLUMES=1`    | Manage volumes            | Watchtower             |
| `EXEC=1`       | Execute in containers     | Dockhand               |
| `INFO=1`       | System info               | Beszel-agent           |
| `VERSION=1`    | Docker version            | Beszel-agent           |

#### Example (from uptime-kuma — read-only, minimal):
```yaml
services:
  uptime-kuma-proxy:
    image: tecnativa/docker-socket-proxy
    container_name: uptime-kuma-proxy
    environment:
      - CONTAINERS=1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - socket_net
    restart: always
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  uptime-kuma:
    image: louislam/uptime-kuma:2
    container_name: uptime-kuma
    networks:
      - monitoring
      - socket_net
    environment:
      - DOCKER_HOST=tcp://uptime-kuma-proxy:2375
    depends_on:
      - uptime-kuma-proxy

networks:
  monitoring:
    external: true
  socket_net:
    # Local — isolated to this compose stack
```

### Networks

#### External Networks (shared between compose stacks)

| Network      | Purpose                                                   | Services                                                                                                                                                                                                                                    |
| ------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `media`      | Media pipeline: arrs, media-server utils, torrent clients | sonarr, radarr, bazarr, prowlarr, profilarr, tautulli, jellyseerr, kometa, daps, imagemaid, autopulse, pulsarr, plex-auto-languages, plexboxd, lettarrboxd, tracearr, stash, qbit-main, qbit-brr, autobrr, thelounge, qui, upload-assistant |
| `monitoring` | Interconnected monitoring services                        | glance, gotify, watchtower, uptime-kuma                                                                                                                                                                                                     |
| `smart_home` | IoT and home automation                                   | mosquitto, zigbee2mqtt                                                                                                                                                                                                                      |

**Cross-network services** (join multiple external networks):
- **Glance** → `monitoring` + `media` (queries sonarr, radarr, tautulli, qbittorrent APIs)
- **Gotify** → `monitoring` + `media` (receives webhooks from media services)

**Fully isolated services** (no external network — only local or none):
- Linkwarden, Open-webui, Syncthing, Rsshub, Cloudflare-ddns

**Host-mode services** (bypass Docker networking): Plex, Home-Assistant

#### Local Networks (per compose stack, NOT external)

| Network               | Compose File                              | Containers                            |
| --------------------- | ----------------------------------------- | ------------------------------------- |
| `socket_net`          | Any service with a dedicated socket proxy | `<service>-proxy` + app               |
| `gotify_internal`     | gotify                                    | gotify + pushtify + gotify-middleware |
| `glance_internal`     | glance                                    | glance + f1-api                       |
| `linkwarden_internal` | linkwarden                                | linkwarden + postgres + meilisearch   |
| `rsshub_internal`     | rsshub                                    | rsshub + rsshub-redis                 |
| `profilarr_internal`  | profilarr-v2                              | profilarr-v2 + profilarr-parser-v2    |
| `tracearr-network`    | tracearr                                  | tracearr + timescale + redis          |

**Rule**: App containers join both the external network (for inter-service communication) and the local network (for internal services). Internal-only services (postgres, redis, sidecars) only join the local network.

#### Choosing a network for a new service

1. **Media pipeline** (arrs, media-server, torrents) → `media`
2. **Monitoring** (needs to talk to other monitoring services) → `monitoring`
3. **Smart home / IoT** → `smart_home`
4. **Standalone** (no inter-service communication needed) → no external network
5. **Needs Docker API** → add a local `socket_net` with dedicated proxy
6. **Has tightly-coupled sidecars** (DB, cache, middleware) → add a local `<service>_internal` network

### Volumes

Consistent mounting patterns:
- Config: `${DOCKER_APPDATA_PATH}/<service>:/config`
- Media: `${MEDIAS_PATH}:/data/medias`
- Downloads: `${DOWNLOAD_PATH}:/downloads`
- App data: `${DOCKER_APPDATA_PATH}/<service>/data:/app/data` (varies by service)

**Reminder**: `DOCKER_APPDATA_PATH`, `MEDIAS_PATH`, and `DOWNLOAD_PATH` are for volume mounts only — **NEVER** add them to the `environment:` section of a compose file.

### Labels

**Watchtower** — required on ALL services:
```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

## Adding a New Service

Follow this checklist:

1. **Choose category**: Place in the appropriate `services/<category>/` folder
2. **Create directory**: `services/<category>/<service-name>/`
3. **Check port availability (MANDATORY)**: Before writing the compose file, run this to list all used host ports (BusyBox-compatible):
   ```bash
   grep -rh '^\s*-\s*"*[0-9]*:[0-9]' services/*/docker-compose.yml services/*/*/docker-compose.yml 2>/dev/null | sed 's/[" ]//g' | sed 's/.*-\([0-9]*\):.*/\1/' | sort -n | uniq
   ```
   If your chosen port appears in the output, it is already taken — pick another available port close to the original. **Do NOT skip this step.**
4. **Create `docker-compose.yml`**: Follow patterns from existing services in the same category
5. **Create `.env.example`**: Use `VARNAME=VARNAME` format for standard vars. Include ALL variables referenced as `${VAR}` in the compose file.
6. **Create `.env`**: Copy `.env.example` and fill with actual values from the Standard Values table
7. **Create appdata directory**: `mkdir -p /volume2/docker/appdata/<service>/<subdirs>`
8. **Docker API access?** → Only if the service needs it: add a dedicated socket proxy sidecar with minimal permissions (see pattern above). If not needed, do NOT add a socket proxy.
9. **Add watchtower label** to all containers
10. **Do NOT create**: extra documentation files (DIRECTORY_SETUP.md, etc.), individual `.gitignore` files (root `.gitignore` handles all patterns)
11. **Ask the user** if they want me to start the container and inspect the logs to see everything is working fine or if they still need to add some info in the config/.env first.

When in doubt, **look at existing services** as templates. Good references:
- Simple service: `services/monitoring/uptime-kuma/`
- Service with Docker API access: `services/monitoring/watchtower/`
- Media service (hotio): `services/arrs/sonarr/`

## Modifying Services

- Never commit actual `.env` files (gitignored)
- Update `.env.example` when adding new environment variables
- Place services in appropriate category folders
- Each service gets its own subdirectory with `docker-compose.yml`
- Don't modify shared infrastructure (networks) without asking
