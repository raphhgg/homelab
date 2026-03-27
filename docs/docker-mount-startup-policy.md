# Docker Startup Policy for NFS-backed Mounts

Date: 2026-03-25

## Decision

Keep Docker startup gated on required mount points.

- `docker.service` must wait for `/mnt/data` and `/mnt/downloads`.
- If `/mnt/data` (TrueNAS NFS) is unavailable, Docker does not start.
- This is intentional to fail closed and avoid containers writing to local fallback paths.

## Why this policy

- Many services bind data from `/mnt/data`.
- If NFS is missing at startup, bind paths can resolve to local filesystem paths.
- That can silently create data drift/corruption that is painful to recover.
- A global Docker gate has larger blast radius, but it is safer for data integrity in this homelab.

## Current systemd configuration

Docker drop-in:

Path: `/etc/systemd/system/docker.service.d/override.conf`

```ini
[Unit]
RequiresMountsFor=/mnt/data /mnt/downloads
```

Mount retry hardening:

Paths:

- `/etc/systemd/system/mnt-data.mount.d/override.conf`
- `/etc/systemd/system/mnt-data.automount.d/override.conf`

```ini
[Unit]
StartLimitIntervalSec=0
```

This prevents `mount-start-limit-hit` from permanently blocking recovery after temporary NFS outages.

## Container-level guardrails

Use long bind syntax with:

```yaml
bind:
  create_host_path: false
```

This is still recommended, but it is not enough on its own:

- It prevents auto-creating missing source paths.
- It does not guarantee that a path is backed by NFS.
- If a local path already exists, containers can still start and write locally.

## Monitoring and alerting (Zabbix)

The following checks/triggers are in place on host `debian-vm`:

Items:

- `mount.data.nfs`
- `dns.upstream.ok`
- `dns.upstream.ms`

Triggers:

- `/mnt/data NFS mount missing on debian-vm` (High)
- `DNS upstream 10.10.2.101 unreachable from debian-vm` (Warning)
- `DNS upstream latency high on debian-vm (>500ms avg 5m)` (Warning)

Routing:

- These trigger names are compatible with `TG: Infrastructure alerts` filtering and are intended to notify via Telegram.

## Runbook (if Docker is down after reboot)

```bash
sudo systemctl reset-failed mnt-data.mount mnt-data.automount docker.service
sudo systemctl restart mnt-data.automount
sudo mount /mnt/data
sudo systemctl start docker
sudo systemctl --no-pager --full status mnt-data.mount mnt-data.automount docker
```

If mount still fails:

```bash
sudo journalctl -u mnt-data.mount -u mnt-data.automount -b --no-pager -n 200
```

## Validation period

Current choice is to keep this policy and observe behavior for a period of normal operation/reboots before considering a per-stack systemd split.
