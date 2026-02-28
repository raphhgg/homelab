#!/usr/bin/env bash
set -euo pipefail
DB_DIR="/home/raphh/docker/appdata/plex/config/Plug-in Support/Databases"
LIB_ACTIVE="${DB_DIR}/com.plexapp.plugins.library.db"
BLOB_ACTIVE="${DB_DIR}/com.plexapp.plugins.library.blobs.db"
# Pick latest dated backup (exclude -wal/-shm)
LIB_BAK="$(ls -1 "${DB_DIR}"/com.plexapp.plugins.library.db-20* | grep -Ev -- '-(wal|shm)$' | sort | tail -n 1)"
BLOB_BAK="$(ls -1 "${DB_DIR}"/com.plexapp.plugins.library.blobs.db-20* | grep -Ev -- '-(wal|shm)$' | sort | tail -n 1)"
if [[ -z "${LIB_BAK}" || -z "${BLOB_BAK}" ]]; then
  echo "No valid dated backup files found in ${DB_DIR}"
  exit 1
fi
TS="$(date +%Y%m%d-%H%M%S)"
SAFETY_DIR="${DB_DIR}/recovery-backup-${TS}"
echo "Using library backup: ${LIB_BAK}"
echo "Using blobs backup:   ${BLOB_BAK}"
echo "Safety backup dir:    ${SAFETY_DIR}"
echo
echo "[1/5] Stopping Plex..."
docker stop plex >/dev/null || true
echo "[2/5] Saving current DB state..."
mkdir -p "${SAFETY_DIR}"
cp -a "${LIB_ACTIVE}" "${SAFETY_DIR}/" 2>/dev/null || true
cp -a "${LIB_ACTIVE}-wal" "${SAFETY_DIR}/" 2>/dev/null || true
cp -a "${LIB_ACTIVE}-shm" "${SAFETY_DIR}/" 2>/dev/null || true
cp -a "${BLOB_ACTIVE}" "${SAFETY_DIR}/" 2>/dev/null || true
cp -a "${BLOB_ACTIVE}-wal" "${SAFETY_DIR}/" 2>/dev/null || true
cp -a "${BLOB_ACTIVE}-shm" "${SAFETY_DIR}/" 2>/dev/null || true
echo "[3/5] Restoring latest backups..."
cp -f "${LIB_BAK}" "${LIB_ACTIVE}"
cp -f "${BLOB_BAK}" "${BLOB_ACTIVE}"
echo "[4/5] Clearing WAL/SHM..."
rm -f "${LIB_ACTIVE}-wal" "${LIB_ACTIVE}-shm" "${BLOB_ACTIVE}-wal" "${BLOB_ACTIVE}-shm"
echo "[5/5] Starting Plex..."
docker start plex >/dev/null
echo
echo "Done. Tail logs now with:"
echo "docker logs -f --tail 200 plex"
