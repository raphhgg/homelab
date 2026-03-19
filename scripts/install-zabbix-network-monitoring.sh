#!/usr/bin/env bash
set -euo pipefail

if ! command -v zabbix_agent2 >/dev/null 2>&1; then
  echo "zabbix_agent2 not found. Install Zabbix Agent 2 first." >&2
  exit 1
fi

install -d -m 755 /usr/local/bin

cat >/usr/local/bin/zabbix-network-monitoring.py <<'PY'
#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request


NETALERTX_BASE = "http://127.0.0.1:20211"
SMOKEPING_BASE = "http://127.0.0.1:8095"


def http_status_code(url: str) -> int:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(resp.status)


def service_status(url: str) -> None:
    try:
        code = http_status_code(url)
    except Exception:
        print("0")
        return
    print("1" if code in (200, 301, 302) else "0")


def netalertx_tile(metric: str) -> None:
    if metric not in {
        "connected",
        "offline",
        "down",
        "new",
        "archived",
        "favorites",
        "all",
        "all_devices",
        "my_devices",
    }:
        sys.exit(1)

    url = f"{NETALERTX_BASE}/php/server/query_json.php?file=table_devices_tiles.json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError):
        print("0")
        return

    row = data.get("data", [{}])[0]
    value = row.get(metric, 0)
    try:
        print(int(value))
    except Exception:
        print("0")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(1)

    scope = sys.argv[1]
    action = sys.argv[2]

    if scope == "netalertx" and action == "status":
        service_status(NETALERTX_BASE)
        return

    if scope == "smokeping" and action == "status":
        service_status(SMOKEPING_BASE)
        return

    if scope == "netalertx" and action == "tile" and len(sys.argv) == 4:
        netalertx_tile(sys.argv[3])
        return

    sys.exit(1)


if __name__ == "__main__":
    main()
PY

chmod 755 /usr/local/bin/zabbix-network-monitoring.py

cat >/etc/zabbix/zabbix_agent2.d/network-monitoring.conf <<'EOF'
UserParameter=netalertx.status,/usr/local/bin/zabbix-network-monitoring.py netalertx status
UserParameter=smokeping.status,/usr/local/bin/zabbix-network-monitoring.py smokeping status
UserParameter=netalertx.tile[*],/usr/local/bin/zabbix-network-monitoring.py netalertx tile "$1"
EOF

systemctl restart zabbix-agent2

echo "== Zabbix agent tests =="
sudo -u zabbix zabbix_agent2 -t netalertx.status || true
sudo -u zabbix zabbix_agent2 -t smokeping.status || true
sudo -u zabbix zabbix_agent2 -t 'netalertx.tile[all]' || true
sudo -u zabbix zabbix_agent2 -t 'netalertx.tile[new]' || true
sudo -u zabbix zabbix_agent2 -t 'netalertx.tile[down]' || true

echo
echo "Next: create Zabbix items/triggers as documented in docs/zabbix/network-monitoring-baseline.md"
