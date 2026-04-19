# Homelab

> Docker Compose stacks for a self-hosted home server.

This repo is the source of truth for my live homelab configuration. It is useful as a working reference, but it is not a one-command starter kit for arbitrary environments.

## What This Repo Contains

Services are organized under `services/` by category:

- `arrs/`: media management applications such as Sonarr, Radarr, Prowlarr, Bazarr, and Profilarr
- `torrents/`: qBittorrent instances and related automation tools
- `media-server/`: Plex-adjacent services, request flows, metadata tools, and media utilities
- `infrastructure/`: ingress, authentication, DDNS, and supporting network services
- `monitoring/`: uptime, notifications, dashboards, and update automation
- `smart-home/`: Home Assistant, Mosquitto, Zigbee2MQTT
- `tools/`: utility services such as Open WebUI, RSSHub, Syncthing, and Vaultwarden

Some stacks are tightly coupled to my network, storage layout, and existing external services. Read each service directory before assuming it is portable as-is.

## How To Use This Repo

The normal flow for a service is:

```bash
cd services/<category>/<service-name>
cp .env.example .env
$EDITOR .env
docker compose up -d
```

Before starting a stack:

- read that service's `docker-compose.yml`
- fill in `.env` with values appropriate for your environment
- verify required networks, volumes, and external dependencies already exist
- check service-specific READMEs when present

## Common Operations

Deploy or refresh a stack:

```bash
cd services/<category>/<service-name>
docker compose up -d
```

Inspect a stack:

```bash
cd services/<category>/<service-name>
docker compose ps
docker compose logs -f
```

Pull newer images:

```bash
cd services/<category>/<service-name>
docker compose pull
docker compose up -d
```

Stop a stack:

```bash
cd services/<category>/<service-name>
docker compose down
```

## Notes

- Real secrets live in local `.env` files and must not be committed.
- Service examples in this repo are uneven in portability. Some are generic templates, some are environment-specific working configs.
- Remote access and SSO examples in this repo should be treated as patterns to adapt, not drop-in values.
