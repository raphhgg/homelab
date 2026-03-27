# qBittorrent Mount Reliability Fix (mnt + Docker)

Date: 2026-03-24

## Context

Both qBittorrent instances (`qbit-main`, `qbit-brr`) reported missing files.

Main risk identified: containers can start before `/mnt/data` (NFS) is mounted, which can make Docker bind a local fallback path instead of NAS data.

## What was found

- `/etc/fstab` has:
  - `/mnt/data` on NFS (`10.10.2.202:/mnt/Vault/data`)
  - `/mnt/downloads` on local ext4
- Runtime check showed:
  - Docker started before `/mnt/data` was fully mounted.
  - `mnt-data.automount` showed `mount-start-limit-hit` earlier in boot.
- qBittorrent config still had default save paths ending in `/complete`, which no longer matched the current intended base paths.

## Changes applied

### 1) qBittorrent default save paths updated

- `qbit-main`:
  - File: `/home/raphh/docker/appdata/qbit-main/config/qBittorrent.conf`
  - Changed:
    - `Session\DefaultSavePath=/data/medias/downloads/torrents/complete`
    - -> `Session\DefaultSavePath=/data/medias/downloads/torrents`
- `qbit-brr`:
  - File: `/home/raphh/docker/appdata/qbit-brr/config/qBittorrent.conf`
  - Changed:
    - `Session\DefaultSavePath=/downloads/torrents/complete`
    - -> `Session\DefaultSavePath=/downloads/torrents`

### 2) Docker bind mounts hardened for both qbit stacks

Files updated:

- `services/torrents/qbit-main/docker-compose.yml`
- `services/torrents/qbit-brr/docker-compose.yml`

Volume syntax was migrated from short bind form to long bind form with:

```yaml
bind:
  create_host_path: false
```

Why: if a source path is missing, the container fails to start instead of silently creating/using an empty host directory.

### 3) Safe restart sequence used

- Stopped both qbit containers first.
- Verified mount sources before restart:
  - `/mnt/data` -> NFS
  - `/mnt/downloads` -> ext4
- Recreated both services with `docker compose up -d`.
- Verified effective container bind mounts with `docker inspect`.

## Validation snapshot

- `qbit-main` mounts:
  - `/mnt/downloads/torrents -> /downloads/torrents`
  - `/mnt/data/media -> /data/medias`
  - `/mnt/data/torrents -> /data/medias/downloads/torrents`
- `qbit-brr` mounts:
  - `/mnt/data/torrents -> /downloads/torrents`
  - `/mnt/downloads/torrents/incomplete -> /downloads/torrents/incomplete`
- Both containers started successfully after changes.

## Pending (manual, requires sudo/root)

Could not be applied from this session due to sudo password requirement.

Add Docker systemd override so Docker waits for mount points:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/override.conf >/dev/null <<'EOF'
[Unit]
RequiresMountsFor=/mnt/data /mnt/downloads
After=network-online.target remote-fs.target mnt-data.mount
EOF
sudo systemctl daemon-reload
sudo systemctl reset-failed mnt-data.automount
sudo systemctl restart docker
```

## Notes for private trackers

- No bulk recheck/reannounce actions were performed as part of this work.
- If missing files remain for already-added torrents, handle only affected items individually (paused), since per-torrent stored paths may still reference old locations.
