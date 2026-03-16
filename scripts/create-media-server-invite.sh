#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROKER_ENV_FILE="${REPO_ROOT}/services/media-server/wizarr-invite-broker/.env"
WIZARR_ENV_FILE="${REPO_ROOT}/services/media-server/wizarr/.env"

if [[ ! -f "${BROKER_ENV_FILE}" ]]; then
  printf 'ERROR: Missing env file: %s\n' "${BROKER_ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${WIZARR_ENV_FILE}" ]]; then
  printf 'ERROR: Missing env file: %s\n' "${WIZARR_ENV_FILE}" >&2
  exit 1
fi

export BROKER_ENV_FILE
export WIZARR_ENV_FILE
export BUNDLE_NAME="${BUNDLE_NAME:-Plex + Pocket ID + Seerr + Discord}"

python3 - <<'PY'
import datetime as dt
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def parse_int_list(value: str) -> list[int]:
    result: list[int] = []
    if not value:
        return result
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        result.append(int(part))
    return result


broker_env = load_env(Path(os.environ["BROKER_ENV_FILE"]))
wizarr_env = load_env(Path(os.environ["WIZARR_ENV_FILE"]))

broker_url = broker_env.get("BROKER_PUBLIC_URL", "").rstrip("/")
broker_api_key = broker_env.get("BROKER_ADMIN_API_KEY", "")

if not broker_url or not broker_api_key:
    raise SystemExit("ERROR: Missing BROKER_PUBLIC_URL or BROKER_ADMIN_API_KEY in broker env")

appdata = wizarr_env.get("DOCKER_APPDATA_PATH", "").rstrip("/")
if not appdata:
    raise SystemExit("ERROR: Missing DOCKER_APPDATA_PATH in wizarr env")
wizarr_db = Path(f"{appdata}/wizarr/database/database.db")
if not wizarr_db.exists():
    raise SystemExit(f"ERROR: Wizarr DB not found: {wizarr_db}")

bundle_name = os.environ.get("BUNDLE_NAME", "Plex + Pocket ID + Seerr + Discord")

flow_response = requests.post(
    f"{broker_url}/api/admin/flow-invites",
    headers={"X-ADMIN-API-KEY": broker_api_key, "Content-Type": "application/json"},
    json={},
    timeout=20,
)
if flow_response.status_code != 201:
    raise SystemExit(
        f"ERROR: Flow invite creation failed ({flow_response.status_code})\n{flow_response.text}"
    )

broker_data = flow_response.json()
wizarr_invite_url = broker_data.get("wizarr_invite_url", "")
if not wizarr_invite_url:
    raise SystemExit("ERROR: Broker did not return wizarr_invite_url")

parsed_invite = urlparse(wizarr_invite_url)
path_parts = [p for p in parsed_invite.path.split("/") if p]
if len(path_parts) != 2 or path_parts[0] != "j":
    raise SystemExit(f"ERROR: Unexpected wizarr invite URL format: {wizarr_invite_url}")
invite_code = path_parts[1]

with sqlite3.connect(str(wizarr_db)) as conn:
    cur = conn.cursor()
    bundle_row = cur.execute(
        "SELECT id FROM wizard_bundle WHERE name = ?", (bundle_name,)
    ).fetchone()
    if not bundle_row:
        raise SystemExit(f"ERROR: Bundle not found: {bundle_name}")
    bundle_id = int(bundle_row[0])

    cur.execute(
        "UPDATE invitation SET wizard_bundle_id = ? WHERE code = ?",
        (bundle_id, invite_code),
    )
    if cur.rowcount != 1:
        raise SystemExit(f"ERROR: Failed to assign bundle to invitation code {invite_code}")
    conn.commit()
expires_unix = broker_data.get("expires_at")
expires_local = ""
expires_utc = ""
if isinstance(expires_unix, int):
    tz_name = broker_env.get("TZ") or wizarr_env.get("TZ") or "UTC"
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = dt.timezone.utc
    expires_local = dt.datetime.fromtimestamp(expires_unix, tz=local_tz).strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )
    expires_utc = dt.datetime.fromtimestamp(expires_unix, tz=dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

print("Invite created successfully")
print(f"- Broker URL: {broker_data.get('invite_url', '')}")
print(f"- Wizarr URL: {wizarr_invite_url}")
print(f"- Bundle: {bundle_name}")
print(f"- Token: {broker_data.get('token', '')}")
if expires_local:
    print(f"- Expires at: {expires_local}")
    print(f"- Expires at (UTC): {expires_utc}")
else:
    print(f"- Expires at (unix): {expires_unix}")
PY
