#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y lm-sensors python3

if command -v sensors-detect >/dev/null 2>&1; then
  sensors-detect --auto || true
fi

install -d -m 755 /usr/local/bin

cat >/usr/local/bin/zabbix-hw-sensors.py <<'PY'
#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys


def load_sensors():
    proc = subprocess.run(["sensors", "-j"], text=True, capture_output=True, check=False)
    raw = proc.stdout.strip()
    if not raw:
        raise RuntimeError(proc.stderr.strip() or "No sensor output")
    return json.loads(raw)


def sensor_kind(feature_name, sub_name):
    name = f"{feature_name} {sub_name}".lower()
    if sub_name.endswith("_input") and (feature_name.lower().startswith("fan") or "fan" in name):
        return "fan"
    if sub_name.endswith("_input") and (
        feature_name.lower().startswith("temp")
        or "temp" in name
        or "package id" in name
        or "tdie" in name
        or "tctl" in name
        or "cpu" in name
    ):
        return "temperature"
    return None


# ASUS TUF GAMING Z790-PLUS WIFI — nct6798 fan header mapping
FAN_NAMES = {
    "fan1": "CHA1_FAN",
    "fan2": "CPU_FAN",
    "fan3": "CPU_OPT",
    "fan4": "CHA2_FAN",
    "fan5": "CHA3_FAN",
    "fan6": "CHA4_FAN",
    "fan7": "AIO_PUMP",
}


def friendly_name(feature_name):
    return FAN_NAMES.get(feature_name, feature_name)


def normalize_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    return None


def discover():
    data = load_sensors()
    found = []
    for chip, features in data.items():
        if not isinstance(features, dict):
            continue
        for feature_name, feature_values in features.items():
            if not isinstance(feature_values, dict):
                continue
            for sub_name, sub_value in feature_values.items():
                kind = sensor_kind(feature_name, sub_name)
                value = normalize_value(sub_value)
                if not kind or value is None:
                    continue
                sensor_id = hashlib.sha1(f"{chip}|{feature_name}|{sub_name}|{kind}".encode()).hexdigest()[:16]
                found.append(
                    {
                        "{#SENSOR_ID}": sensor_id,
                        "{#SENSOR_NAME}": friendly_name(feature_name),
                        "{#SENSOR_TYPE}": kind,
                        "{#SENSOR_CHIP}": chip,
                        "{#SENSOR_FIELD}": sub_name,
                    }
                )
    print(json.dumps({"data": found}, separators=(",", ":")))


def value(sensor_id):
    data = load_sensors()
    for chip, features in data.items():
        if not isinstance(features, dict):
            continue
        for feature_name, feature_values in features.items():
            if not isinstance(feature_values, dict):
                continue
            for sub_name, sub_value in feature_values.items():
                kind = sensor_kind(feature_name, sub_name)
                value = normalize_value(sub_value)
                if not kind or value is None:
                    continue
                current_id = hashlib.sha1(f"{chip}|{feature_name}|{sub_name}|{kind}".encode()).hexdigest()[:16]
                if current_id == sensor_id:
                    print(value)
                    return
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    if sys.argv[1] == "discovery":
        discover()
        return
    if sys.argv[1] == "value" and len(sys.argv) == 3:
        value(sys.argv[2])
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
PY

chmod 755 /usr/local/bin/zabbix-hw-sensors.py

cat >/etc/zabbix/zabbix_agent2.d/hw-sensors.conf <<'EOF'
UserParameter=hw.sensor.discovery,/usr/local/bin/zabbix-hw-sensors.py discovery
UserParameter=hw.sensor.value[*],/usr/local/bin/zabbix-hw-sensors.py value "$1"
EOF

systemctl restart zabbix-agent2

echo "== Discovery test =="
sudo -u zabbix zabbix_agent2 -t hw.sensor.discovery || true

echo
echo "Next: add the Zabbix discovery rule and item prototypes from docs/zabbix-proxmox-hw-sensors.md"
