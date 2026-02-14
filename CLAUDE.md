# CLAUDE.md

Instructions for AI agents working with this homelab Docker Compose repository on a Synology NAS.

## Repository Overview

Homelab infrastructure managing Docker services organized in `services/` by category. Each service has its own directory with `docker-compose.yml`, `.env.example`, and `.env`.

## Standard Values

These are the **actual values** used across all services. Use them when creating `.env` files:

| Variable               | Value                    |
|------------------------|--------------------------|
| `PUID`                 | `1026`                   |
| `PGID`                 | `100`                    |
| `TZ`                   | `Europe/Brussels`        |
| `DOCKER_APPDATA_PATH`  | `/volume2/docker/appdata`|
| `MEDIAS_PATH`          | `/volume3/data/medias`   |
| `DOWNLOAD_PATH`        | `/volume2/downloads`     |

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
- Always declare networks as `external: true`

### .env Files (CRITICAL)

**Every standard variable referenced in `docker-compose.yml` MUST be present** in both `.env.example` and `.env`. Cross-check the compose file's `${VAR}` references against the Standard Values table — missing variables will cause silent failures.

**`.env.example`** (committed to git) — **MUST use placeholder format, NEVER actual values**:
- Standard shared vars: `VARNAME=VARNAME` (e.g., `PUID=PUID`, `TZ=TZ`)
- Service-specific secrets: descriptive placeholder (e.g., `API_TOKEN=your_api_token_here`)
- `DOCKER_APPDATA_PATH`, `MEDIAS_PATH`, `DOWNLOAD_PATH` — these are **only used in volume mounts** in `docker-compose.yml`. They must be in `.env` files but are **NOT container environment variables** (never put them in the `environment:` section).

WRONG `.env.example` — uses actual values:
```
PUID=1026
TZ=Europe/Brussels
DOCKER_APPDATA_PATH=/volume2/docker/appdata
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
PUID=1026
PGID=100
TZ=Europe/Brussels
DOCKER_APPDATA_PATH=/volume2/docker/appdata
# Optional: override default (auto-generated on first run)
# API_KEY=your_api_key_here
```

### Docker Socket Proxy (CRITICAL)

**Only services that need Docker API access** (e.g., monitoring containers, managing other containers) should use the docker-socket-proxy. Most services do NOT need this — **do not add `DOCKER_HOST`, `socket_proxy` network, or docker socket mounts unless the service genuinely requires Docker API access.**

**NEVER mount `/var/run/docker.sock` directly into a service container.** When Docker API access is needed, use the docker-socket-proxy:

1. Add the `socket_proxy` network to the service
2. Set `DOCKER_HOST=tcp://172.26.0.22:2375` as environment variable
3. Add `DOCKER_HOST` to both `.env.example` and `.env` (placeholder: `DOCKER_HOST=DOCKER_HOST`, actual: `DOCKER_HOST=tcp://172.26.0.22:2375`)
4. Do NOT use container name (`docker-proxy`) — always use the IP address

Reference: `services/infrastructure/docker-socket-proxy/docker-compose.yml`

Example (from uptime-kuma):
```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:2
    container_name: uptime-kuma
    networks:
      - main
      - socket_proxy
    environment:
      - DOCKER_HOST=${DOCKER_HOST}
    # NO docker.sock volume mount!

networks:
  main:
    external: true
  socket_proxy:
    external: true
```

**Do NOT modify the docker-socket-proxy configuration** without asking the user first — it's shared infrastructure.

### Networks

- `main` — used by most services for inter-service communication
- `socket_proxy` — only for services needing Docker API access via docker-socket-proxy

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
8. **Docker API access?** → Only if the service needs it: use docker-socket-proxy pattern (see above), add `DOCKER_HOST` to env files. If not needed, do NOT add `DOCKER_HOST` or `socket_proxy` network.
9. **Add watchtower label** to all containers
10. **Do NOT create**: extra documentation files (DIRECTORY_SETUP.md, etc.), individual `.gitignore` files (root `.gitignore` handles all patterns)
11. **Ask the user** if they want me to start the container and inspect the logs to see everything is working fine or if they still need to add some info in the config/.env first.

When in doubt, **look at existing services** as templates. Good references:
- Simple service: `services/monitoring/uptime-kuma/`
- Service with Docker API access: `services/monitoring/dozzle/`
- Media service (hotio): `services/arrs/sonarr/`

## Modifying Services

- Never commit actual `.env` files (gitignored)
- Update `.env.example` when adding new environment variables
- Place services in appropriate category folders
- Each service gets its own subdirectory with `docker-compose.yml`
- Don't modify shared infrastructure (docker-socket-proxy, networks) without asking
