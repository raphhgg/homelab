#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NETALERTX_STACK_DIR="${REPO_ROOT}/services/monitoring/netalertx"
SMOKEPING_STACK_DIR="${REPO_ROOT}/services/monitoring/smokeping"
NETALERTX_ENV_FILE="${NETALERTX_STACK_DIR}/.env"

ARP_SYSCTL_FILE="/etc/sysctl.d/99-netalertx-arp.conf"

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  echo "Error: root privileges are required, and sudo is not available." >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command not found: $1" >&2
    exit 1
  fi
}

read_env_value() {
  local file="$1"
  local key="$2"
  [[ -f "${file}" ]] || return 1
  awk -F= -v wanted="${key}" '$1 == wanted {print substr($0, index($0, "=") + 1); exit}' "${file}"
}

echo "==> Checking required commands"
require_cmd docker
require_cmd curl
require_cmd /usr/sbin/sysctl

APPDATA_ROOT="${DOCKER_APPDATA_PATH:-$(read_env_value "${NETALERTX_ENV_FILE}" "DOCKER_APPDATA_PATH" || true)}"
if [[ -z "${APPDATA_ROOT}" ]]; then
  echo "Error: DOCKER_APPDATA_PATH is not set and could not be read from ${NETALERTX_ENV_FILE}" >&2
  exit 1
fi

echo "==> Ensuring appdata directories exist"
mkdir -p \
  "${APPDATA_ROOT}/netalertx/config" \
  "${APPDATA_ROOT}/netalertx/db" \
  "${APPDATA_ROOT}/smokeping/config"

echo "==> Applying persistent ARP tuning for NetAlertX"
run_as_root /bin/sh -c "cat > '${ARP_SYSCTL_FILE}' <<'EOF'
net.ipv4.conf.all.arp_ignore=1
net.ipv4.conf.all.arp_announce=2
EOF"

echo "==> Applying ARP tuning at runtime"
run_as_root /usr/sbin/sysctl -w net.ipv4.conf.all.arp_ignore=1 net.ipv4.conf.all.arp_announce=2

echo "==> Bringing up NetAlertX stack"
docker compose -f "${NETALERTX_STACK_DIR}/docker-compose.yml" --env-file "${NETALERTX_STACK_DIR}/.env" up -d

echo "==> Bringing up SmokePing stack"
docker compose -f "${SMOKEPING_STACK_DIR}/docker-compose.yml" --env-file "${SMOKEPING_STACK_DIR}/.env" up -d

echo "==> Verifying container state"
docker ps --filter name=netalertx --filter name=smokeping --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo "==> Verifying HTTP endpoints"
echo -n "NetAlertX: "
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:20211
echo -n "SmokePing: "
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8095

echo "==> Current ARP sysctl values"
/usr/sbin/sysctl net.ipv4.conf.all.arp_ignore net.ipv4.conf.all.arp_announce

echo "Done. Baseline network monitoring stack is installed and running."
