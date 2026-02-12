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
| `DOCKER_HOST`          | `tcp://172.26.0.22:2375` |

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

### .env Files

**`.env.example`** (committed to git) uses placeholder format:
- Standard shared vars: `VARNAME=VARNAME` (e.g., `PUID=PUID`, `TZ=TZ`)
- Service-specific secrets: descriptive placeholder (e.g., `API_TOKEN=your_api_token_here`)

**`.env`** (gitignored) uses **actual values** from the Standard Values table above, plus real secrets.

### Docker Socket Proxy (CRITICAL)

**NEVER mount `/var/run/docker.sock` directly into a service container.** Always use the docker-socket-proxy:

1. Add the `socket_proxy` network to the service
2. Set `DOCKER_HOST=${DOCKER_HOST}` as environment variable (resolves to `tcp://172.26.0.22:2375`)
3. Do NOT use container name (`docker-proxy`) — always use the IP address

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

Note: `DOCKER_APPDATA_PATH` is used in volume mounts only — it is NOT a container environment variable.

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
3. **Create `docker-compose.yml`**: Follow patterns from existing services in the same category
4. **Create `.env.example`**: Use `VARNAME=VARNAME` format for standard vars
5. **Create `.env`**: Copy `.env.example` and fill with actual values from the Standard Values table
6. **Create appdata directory**: `mkdir -p /volume2/docker/appdata/<service>/<subdirs>`
7. **Docker API access?** → Use docker-socket-proxy pattern (see above), NEVER mount socket directly
8. **Add watchtower label** to all containers
9. **Do NOT create**: extra documentation files (DIRECTORY_SETUP.md, etc.), individual `.gitignore` files (root `.gitignore` handles all patterns)
10. **Ask the user** if they want to add a monitor in Uptime Kuma

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

## Scripts

Utility scripts for homelab automation and maintenance are in `scripts/`. See [scripts/README.md](scripts/README.md).

<!--
## Linear Issue Management

**Default Project:** "self-hosted"

**Linear GraphQL API IDs:**
- Team ID: `9bbf50c0-425a-4736-b5ac-fb98744a5830`
- Project ID (self-hosted): `91189c04-ae99-46dc-bf34-243cb9f95fb6`

**API Key Location**: `/volume2/docker/compose/.secrets` (gitignored)

**Usage:**
```bash
LINEAR_KEY=$(grep LINEAR_API_KEY /volume2/docker/compose/.secrets | cut -d'=' -f2)
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"query { issue(id: \"ISSUE-ID\") { id title description state { name } assignee { name } labels { nodes { name } } } }"}' \
  | python3 -m json.tool
```
-->
