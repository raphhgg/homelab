#!/usr/bin/env bash
set -euo pipefail

command -v upsc >/dev/null || { echo "upsc not found; install nut-client first"; exit 1; }

install -d -m 755 /usr/local/bin

cat >/usr/local/bin/zabbix-nut-ups.py <<'PY'
#!/usr/bin/env python3
import json
import subprocess
import sys


def discover(ups_name):
    proc = subprocess.run(
        ["upsc", ups_name],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "upsc returned no data")
    found = []
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        try:
            float(raw_value)
            metric_type = "numeric"
        except ValueError:
            metric_type = "string"
        found.append({
            "{#UPS_NAME}": ups_name,
            "{#UPS_METRIC}": key,
            "{#UPS_METRIC_TYPE}": metric_type,
        })
    print(json.dumps({"data": found}, separators=(",", ":")))


def value(ups_name, metric_key):
    proc = subprocess.run(
        ["upsc", ups_name, metric_key],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        sys.exit(1)
    print(proc.stdout.strip())


def main():
    if len(sys.argv) < 3:
        sys.exit(1)
    cmd = sys.argv[1]
    ups_name = sys.argv[2]
    if cmd == "discovery":
        discover(ups_name)
    elif cmd == "value" and len(sys.argv) == 4:
        value(ups_name, sys.argv[3])
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
PY

chmod 755 /usr/local/bin/zabbix-nut-ups.py

cat >/etc/zabbix/zabbix_agent2.d/nut-ups.conf <<'EOF'
UserParameter=nut.ups.discovery[*],/usr/local/bin/zabbix-nut-ups.py discovery "$1"
UserParameter=nut.ups.value[*],/usr/local/bin/zabbix-nut-ups.py value "$1" "$2"
EOF

systemctl restart zabbix-agent2

echo "== Discovery test =="
sudo -u zabbix zabbix_agent2 -t 'nut.ups.discovery[cyberpower]' || true

echo
echo "== Value test (battery.charge) =="
sudo -u zabbix zabbix_agent2 -t 'nut.ups.value[cyberpower,battery.charge]' || true

echo
echo "Next: configure Zabbix discovery rules per docs/zabbix/zabbix-nut-ups.md"
