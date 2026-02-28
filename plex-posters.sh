#!/usr/bin/env bash
set -euo pipefail
# Adjust if your mount path differs
SRC="/mnt/synology_nfs/docker/appdata/plex/config"
DST="/home/raphh/docker/appdata/plex/config"
TS="$(date +%Y%m%d-%H%M%S)"
BK="${DST}/restore-uploads-backup-${TS}"
echo "Source:      ${SRC}"
echo "Destination: ${DST}"
test -d "${SRC}/Metadata" || { echo "Missing source Metadata: ${SRC}/Metadata"; exit 1; }
test -d "${DST}/Metadata" || { echo "Missing destination Metadata: ${DST}/Metadata"; exit 1; }
echo "[1/5] Stop Plex"
docker stop plex >/dev/null || true
echo "[2/5] Backup current Metadata + Media"
mkdir -p "${BK}"
cp -a "${DST}/Metadata" "${BK}/"
cp -a "${DST}/Media" "${BK}/" 2>/dev/null || true
echo "[3/5] Restore Uploads (custom posters/backgrounds) from Synology backup"
rsync -aHAX --numeric-ids \
  --include='*/' \
  --include='Uploads/***' \
  --exclude='*' \
  "${SRC}/Metadata/" "${DST}/Metadata/"
echo "[4/5] Ensure ownership for Plex user/group"
chown -R 1000:100 "${DST}/Metadata"
echo "[5/5] Start Plex"
docker start plex >/dev/null
echo "Done. Watch logs:"
echo "docker logs -f --tail 200 plex"
