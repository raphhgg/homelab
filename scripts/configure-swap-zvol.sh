#!/usr/bin/env bash
set -euo pipefail

# Configure a ZFS zvol-backed swap on a Proxmox node.
# Usage: ssh root@pve 'bash -s' < scripts/configure-swap-zvol.sh
#
# Creates a 4 GB zvol under rpool/swap with tuning flags optimized
# for swap workloads, enables it, and persists it across reboots.

SWAP_SIZE="${1:-4G}"
ZVOL_NAME="rpool/swap"
ZVOL_DEV="/dev/zvol/${ZVOL_NAME}"

# --- Pre-flight checks -------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must run as root" >&2
  exit 1
fi

if ! command -v zfs >/dev/null 2>&1; then
  echo "ERROR: zfs not found — is this a ZFS-based Proxmox install?" >&2
  exit 1
fi

if ! zpool list rpool >/dev/null 2>&1; then
  echo "ERROR: rpool not found — adjust ZVOL_NAME if your pool has a different name" >&2
  exit 1
fi

# --- Check existing swap -----------------------------------------------------

current_swap=$(swapon --show --noheadings 2>/dev/null || true)
if [[ -n "$current_swap" ]]; then
  echo "Swap already active:"
  swapon --show
  echo
  read -rp "Continue anyway and add another swap device? [y/N] " confirm
  [[ "${confirm,,}" == "y" ]] || exit 0
fi

# --- Create zvol --------------------------------------------------------------

if zfs list "${ZVOL_NAME}" >/dev/null 2>&1; then
  echo "zvol ${ZVOL_NAME} already exists — skipping creation"
else
  echo "Creating ${SWAP_SIZE} zvol: ${ZVOL_NAME}"
  zfs create -V "${SWAP_SIZE}" \
    -b "$(getconf PAGESIZE)" \
    -o compression=zle \
    -o logbias=throughput \
    -o sync=always \
    -o primarycache=metadata \
    -o secondarycache=none \
    "${ZVOL_NAME}"
  echo "  -> zvol created"
fi

# --- Format and enable --------------------------------------------------------

if ! blkid "${ZVOL_DEV}" | grep -q swap; then
  echo "Formatting ${ZVOL_DEV} as swap"
  mkswap "${ZVOL_DEV}"
fi

if ! swapon --show --noheadings | grep -q "${ZVOL_DEV}"; then
  echo "Enabling swap on ${ZVOL_DEV}"
  swapon "${ZVOL_DEV}"
fi

# --- Persist in /etc/fstab ----------------------------------------------------

FSTAB_LINE="${ZVOL_DEV} none swap sw 0 0"
if ! grep -qF "${ZVOL_DEV}" /etc/fstab; then
  echo "Adding to /etc/fstab"
  echo "${FSTAB_LINE}" >> /etc/fstab
else
  echo "Already in /etc/fstab — skipping"
fi

# --- Set swappiness low (emergency-only) --------------------------------------

CURRENT_SWAPPINESS=$(sysctl -n vm.swappiness)
TARGET_SWAPPINESS=10

if [[ "${CURRENT_SWAPPINESS}" -ne "${TARGET_SWAPPINESS}" ]]; then
  echo "Setting vm.swappiness=${TARGET_SWAPPINESS} (was ${CURRENT_SWAPPINESS})"
  sysctl vm.swappiness=${TARGET_SWAPPINESS}
  # Proxmox doesn't ship /etc/sysctl.conf — use sysctl.d drop-in
  echo "vm.swappiness=${TARGET_SWAPPINESS}" > /etc/sysctl.d/99-swap.conf
else
  echo "vm.swappiness already ${TARGET_SWAPPINESS}"
fi

# --- Summary ------------------------------------------------------------------

echo
echo "=== Swap configured ==="
swapon --show
echo
free -h | head -3
