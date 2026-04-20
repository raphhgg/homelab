# Homelab

> Docker Compose stacks for a self-hosted homelab.

This repo is the source of truth for my live Docker Compose stacks. It is meant to be a reusable reference for people running their own homelab, not a one-command starter kit for arbitrary environments.

## Repo Contract

This repository contains Docker Compose stacks only.

Infrastructure runbooks, host-level setup notes, and operational helper scripts are intentionally out of scope for this repo. Those belong in a separate companion repo so the public contract here stays focused on Docker services rather than machine provisioning.

In this workspace, that companion material now lives in a sibling `homelab-infra/` folder outside this repo.

## What This Repo Contains

Services are organized under `services/` by category:

- `arrs/`: media management applications such as Sonarr, Radarr, Prowlarr, Bazarr, and Profilarr
- `torrents/`: qBittorrent instances and related automation tools
- `media-server/`: Plex-adjacent services, request flows, metadata tools, and media utilities
- `infrastructure/`: ingress, authentication, DDNS, and supporting network services
- `monitoring/`: uptime, notifications, dashboards, and update automation
- `smart-home/`: Home Assistant, Mosquitto, Zigbee2MQTT
- `tools/`: utility services such as Open WebUI, RSSHub, Syncthing, and Vaultwarden

## Portability

Not every stack here is equally reusable. Use this repo as a working reference and adapt it to your own environment.

| Area                                  | Reuse Level          | Notes                                                                              |
| ------------------------------------- | -------------------- | ---------------------------------------------------------------------------------- |
| `tools/`, parts of `monitoring/`      | Portable             | Usually straightforward if you adapt paths, domains, and secrets                   |
| `arrs/`, `torrents/`, `media-server/` | Adapt before use     | Often tied to media paths, downloader conventions, reverse proxy, and auth choices |
| `infrastructure/`, `smart-home/`      | Environment-specific | Most sensitive to LAN topology, DNS, host networking, certificates, and hardware   |

Before copying a stack blindly, read that service directory and verify the required networks, storage paths, and external dependencies.

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

## What You Need To Adapt

Expect to change at least some of the following:

- bind-mount paths such as appdata, media libraries, and download directories
- host ports and external Docker networks
- reverse proxy, DNS, and authentication wiring
- service-specific secrets and API credentials
- hardware-specific integrations such as GPUs, Zigbee adapters, or host networking

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
- Remote access, SSO, and ingress examples in this repo should be treated as patterns to adapt, not drop-in values.
- Local-only or private service repos should live outside this repo entirely. In this workspace they now live in the sibling `compose-private/` folder.

## Contributing

Issues and pull requests are welcome, especially for portability improvements, documentation cleanup, and reusable compose patterns.
