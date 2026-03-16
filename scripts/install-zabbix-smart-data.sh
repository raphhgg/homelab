#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y python3 smartmontools sudo

# Remove previous helper/config first so reinstalls are deterministic.
rm -f /usr/local/bin/zabbix-intel-sata-smart.py
rm -f /etc/zabbix/zabbix_agent2.d/intel-sata-smart.conf
rm -f /etc/sudoers.d/zabbix-smartctl

install -d -m 755 /usr/local/bin

cat >/usr/local/bin/zabbix-intel-sata-smart.py <<'PY'
#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from datetime import datetime, timezone


def smartctl_json(device: str):
    proc = subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/sbin/smartctl", "-a", "-j", device],
        text=True,
        capture_output=True,
        check=False,
    )
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or f"No smartctl output for {device}")
    return json.loads(proc.stdout)


def smartctl_text(device: str):
    proc = subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/sbin/smartctl", "-a", device],
        text=True,
        capture_output=True,
        check=False,
    )
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or f"No smartctl output for {device}")
    return proc.stdout


def normalize_name(value: str):
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def nested_value(data, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if isinstance(current, dict) and "value" in current:
        return current["value"]
    return current


def search_nested_key(data, wanted_key):
    wanted_key = normalize_name(wanted_key)
    if isinstance(data, dict):
        for key, value in data.items():
            if normalize_name(key) == wanted_key:
                if isinstance(value, dict) and "value" in value:
                    return value["value"]
                return value
            found = search_nested_key(value, wanted_key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = search_nested_key(value, wanted_key)
            if found is not None:
                return found
    return None


def nvme_value(data, key):
    direct = search_nested_key(data, key)
    if direct is not None:
        return direct
    return None


def ata_table(data):
    return data.get("ata_smart_attributes", {}).get("table", [])


def clean_arg(value: str):
    value = value.strip()
    for ch in '[]"\'':
        value = value.replace(ch, '')
    return value.strip()


def clean_device(value: str):
    value = clean_arg(value).rstrip(']')
    value = value.replace("/dev/", "")
    match = re.search(r"(nvme\d+(?:n\d+)?|sd[a-z]+|hd[a-z]+|vd[a-z]+|xvd[a-z]+)", value)
    if match:
        return match.group(1)
    value = re.sub(r"[^A-Za-z0-9_.-]", "", value)
    return value


def clean_metric(value: str):
    value = clean_arg(value).rstrip(']')
    value = re.sub(r"[^A-Za-z0-9_]", "", value)
    return value


def find_attr(data, *ids_or_names):
    lowered = {normalize_name(v) for v in ids_or_names if not isinstance(v, int)}
    ids = {v for v in ids_or_names if isinstance(v, int)}
    for attr in ata_table(data):
        attr_id = attr.get("id")
        name = normalize_name(attr.get("name", ""))
        if attr_id in ids or name in lowered:
            return attr
    return None


def parse_ata_attrs_from_text(text: str):
    attrs = {}
    for line in text.splitlines():
        parts = line.split(None, 9)
        if len(parts) < 10 or not parts[0].isdigit():
            continue
        attr_id = int(parts[0])
        name = normalize_name(parts[1])
        try:
            value = int(parts[3])
        except ValueError:
            continue
        raw_value = parts[9].strip()
        raw_number_match = re.search(r"(-?\d+)", raw_value.replace(",", ""))
        raw_number = int(raw_number_match.group(1)) if raw_number_match else None
        attrs[attr_id] = {
            "id": attr_id,
            "name": name,
            "value": value,
            "raw": {"value": raw_number if raw_number is not None else raw_value},
        }
    return attrs


def find_attr_in_text(text: str, *ids_or_names):
    attrs = parse_ata_attrs_from_text(text)
    lowered = {normalize_name(v) for v in ids_or_names if not isinstance(v, int)}
    ids = {v for v in ids_or_names if isinstance(v, int)}
    for attr in attrs.values():
        if attr["id"] in ids or attr["name"] in lowered:
            return attr
    return None


def require_attr(data, *ids_or_names):
    attr = find_attr(data, *ids_or_names)
    if not attr:
        joined = ", ".join(str(v) for v in ids_or_names)
        raise RuntimeError(f"SMART attribute not found ({joined})")
    return attr


def require_attr_any(data, text, *ids_or_names):
    attr = find_attr(data, *ids_or_names)
    if attr:
        return attr
    attr = find_attr_in_text(text, *ids_or_names)
    if attr:
        return attr
    joined = ", ".join(str(v) for v in ids_or_names)
    raise RuntimeError(f"SMART attribute not found ({joined})")


def require_value(*candidates):
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, str) and not candidate.strip():
            continue
        return candidate
    return None


def text_search(text: str, pattern: str):
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    return match.group(1)


def text_int(text: str, pattern: str):
    value = text_search(text, pattern)
    if value is None:
        return None
    return int(str(value).replace(",", ""))


def match_self_test_type(text: str, wanted_type: str):
    wanted = normalize_name(wanted_type)
    text = normalize_name(text)
    if wanted == "short":
        return "short" in text
    if wanted == "long":
        return "extended" in text or "long" in text
    return True


def device_name(device: str):
    return clean_device(device).replace('/dev/', '')


def wearout(device: str):
    data = smartctl_json(device)
    text = smartctl_text(device)
    attr = require_attr_any(data, text, 233, "media_wearout_indicator", "mediawearoutindicator", "ssd_life_left")
    value = require_value(attr.get("value"), attr.get("raw", {}).get("value"))
    if value is None:
        raise RuntimeError(f"No wearout value found for {device}")
    value = float(value)
    print(max(0, min(100, 100 - value)))


def metric(device: str, metric_name: str):
    data = smartctl_json(device)
    text = smartctl_text(device)
    metric_name = clean_metric(metric_name)

    if metric_name == "wear_used":
        wearout(device)
        return
    if metric_name == "wear_remaining":
        attr = require_attr_any(data, text, 233, "media_wearout_indicator", "mediawearoutindicator", "ssd_life_left")
        print(require_value(attr.get("value"), attr.get("raw", {}).get("value")))
        return
    if metric_name == "available_reserved_space":
        attr = require_attr_any(data, text, 232, 170, "available_reservd_space", "available_reserved_space")
        print(require_value(attr.get("value"), attr.get("raw", {}).get("value")))
        return
    if metric_name == "host_writes_32mib":
        print(require_attr_any(data, text, 241, 225, "host_writes_32mib").get("raw", {}).get("value"))
        return
    if metric_name == "host_reads_32mib":
        print(require_attr_any(data, text, 242, "host_reads_32mib").get("raw", {}).get("value"))
        return
    if metric_name == "nand_writes_32mib":
        print(require_attr_any(data, text, 243, "nand_writes_32mib").get("raw", {}).get("value"))
        return
    if metric_name == "workload_media_wear_raw":
        print(require_attr_any(data, text, 226, "workld_media_wear_indic").get("raw", {}).get("value"))
        return
    if metric_name == "workload_host_reads_perc":
        print(require_attr_any(data, text, 227, "workld_host_reads_perc").get("raw", {}).get("value"))
        return
    if metric_name == "workload_minutes":
        print(require_attr_any(data, text, 228, "workload_minutes").get("raw", {}).get("value"))
        return
    if metric_name == "power_on_hours":
        print(require_value(data.get("power_on_time", {}).get("hours"), text_int(text, r"Power_On_Hours.*?\s(\d+)\s*$"), text_int(text, r"Power on Hours:\s*(\d+)")))
        return
    if metric_name == "power_cycle_count":
        print(require_value(data.get("power_cycle_count"), text_int(text, r"Power_Cycle_Count.*?\s(\d+)\s*$"), text_int(text, r"Power Cycles:\s*(\d+)")))
        return
    if metric_name == "temperature":
        print(require_value(data.get("temperature", {}).get("current"), text_int(text, r"Temperature_Celsius.*?\s(\d+)\s*$"), text_int(text, r"Current Drive Temperature:\s*(\d+)")))
        return
    raise RuntimeError(f"Unknown metric {metric_name}")


def text_metric(device: str, metric_name: str):
    data = smartctl_json(device)
    metric_name = clean_metric(metric_name)
    if metric_name == "model_family":
        print(data.get("model_family", ""))
        return
    if metric_name == "model_name":
        print(data.get("model_name", ""))
        return
    if metric_name == "serial_number":
        print(data.get("serial_number", ""))
        return
    if metric_name == "firmware_version":
        print(data.get("firmware_version", ""))
        return
    raise RuntimeError(f"Unknown text metric {metric_name}")


def nvme_metric(device: str, metric_name: str):
    data = smartctl_json(device)
    text = smartctl_text(device)
    metric_name = clean_metric(metric_name)
    if metric_name == 'wear_used':
        value = require_value(
            nvme_value(data, 'percentage_used'),
            nested_value(data, 'nvme_smart_health_information_log', 'percentage_used'),
            text_int(text, r'Percentage Used:\s*(\d+)%'),
        )
        if value is None:
            raise RuntimeError(f'No NVMe percentage_used found for {device}')
        print(value)
        return
    if metric_name == 'wear_remaining':
        value = require_value(
            nvme_value(data, 'percentage_used'),
            nested_value(data, 'nvme_smart_health_information_log', 'percentage_used'),
            text_int(text, r'Percentage Used:\s*(\d+)%'),
        )
        if value is None:
            raise RuntimeError(f'No NVMe percentage_used found for {device}')
        print(max(0, min(100, 100 - float(value))))
        return
    if metric_name == 'power_on_hours':
        value = require_value(
            nested_value(data, 'power_on_time', 'hours'),
            nested_value(data, 'nvme_smart_health_information_log', 'power_on_hours'),
            text_int(text, r'Power On Hours:\s*(\d+)'),
        )
        print(value)
        return
    if metric_name == 'available_spare':
        value = require_value(
            nvme_value(data, 'available_spare'),
            nested_value(data, 'nvme_smart_health_information_log', 'available_spare'),
            text_int(text, r'Available Spare:\s*(\d+)%'),
        )
        print(value)
        return
    if metric_name == 'temperature':
        value = require_value(
            nested_value(data, 'temperature', 'current'),
            nested_value(data, 'nvme_smart_health_information_log', 'temperature'),
            text_int(text, r'Temperature:\s*(\d+)'),
            text_int(text, r'Composite Temperature:\s*(\d+)'),
        )
        print(value)
        return
    if metric_name == 'unsafe_shutdowns':
        print(require_value(nvme_value(data, 'unsafe_shutdowns'), text_int(text, r'Unsafe Shutdowns:\s*(\d+)')))
        return
    if metric_name == 'media_errors':
        print(require_value(nvme_value(data, 'media_errors'), text_int(text, r'Media and Data Integrity Errors:\s*(\d+)'), text_int(text, r'Media Errors:\s*(\d+)')))
        return
    if metric_name == 'data_units_read':
        print(require_value(nvme_value(data, 'data_units_read'), text_int(text, r'Data Units Read:\s*([\d,]+)')))
        return
    if metric_name == 'data_units_written':
        print(require_value(nvme_value(data, 'data_units_written'), text_int(text, r'Data Units Written:\s*([\d,]+)')))
        return
    raise RuntimeError(f'Unknown NVMe metric {metric_name}')


def nvme_text_metric(device: str, metric_name: str):
    data = smartctl_json(device)
    metric_name = clean_metric(metric_name)
    if metric_name == 'model_name':
        print(data.get('model_name', ''))
        return
    if metric_name == 'serial_number':
        print(data.get('serial_number', ''))
        return
    if metric_name == 'firmware_version':
        print(data.get('firmware_version', ''))
        return
    raise RuntimeError(f'Unknown NVMe text metric {metric_name}')


def last_pass_epoch(device: str, test_type: str = "any"):
    data = smartctl_json(device)
    text = smartctl_text(device)
    table = data.get("ata_smart_self_test_log", {}).get("standard", {}).get("table", [])
    now = int(datetime.now(timezone.utc).timestamp())
    power_on_hours = data.get("power_on_time", {}).get("hours")
    for entry in table:
        status = str(entry.get("status", {}).get("string", "")).lower()
        if "completed without error" not in status:
            continue
        test_desc = str(entry.get("type", {}).get("string", "")) or str(entry.get("description", ""))
        if not match_self_test_type(test_desc, test_type):
            continue
        lifetime_hours = entry.get("lifetime_hours")
        if lifetime_hours is None or power_on_hours is None:
            continue
        age_hours = max(0, float(power_on_hours) - float(lifetime_hours))
        epoch = int(now - age_hours * 3600)
        print(epoch)
        return
    if power_on_hours is None:
        power_on_hours = text_int(text, r"Power_On_Hours.*?\s(\d+)\s*$")
    for line in text.splitlines():
        if "completed without error" not in line.lower():
            continue
        if not match_self_test_type(line, test_type):
            continue
        match = re.search(r"Completed without error\s+\d+%\s+(\d+)\s+-\s*$", line, re.IGNORECASE)
        if not match or power_on_hours is None:
            continue
        lifetime_hours = float(match.group(1))
        age_hours = max(0, float(power_on_hours) - lifetime_hours)
        epoch = int(now - age_hours * 3600)
        print(epoch)
        return
    if test_type != "any":
        print(0)
        return
    raise RuntimeError(f"No successful {test_type} self-test found for {device}")


def last_pass_text(device: str, test_type: str = "any"):
    data = smartctl_json(device)
    text = smartctl_text(device)
    table = data.get("ata_smart_self_test_log", {}).get("standard", {}).get("table", [])
    for entry in table:
        status = str(entry.get("status", {}).get("string", "")).lower()
        if "completed without error" not in status:
            continue
        test_desc = str(entry.get("type", {}).get("string", "")) or str(entry.get("description", ""))
        if not match_self_test_type(test_desc, test_type):
            continue
        lifetime_hours = entry.get("lifetime_hours")
        power_on_hours = data.get("power_on_time", {}).get("hours")
        if lifetime_hours is None or power_on_hours is None:
            continue
        now = int(datetime.now(timezone.utc).timestamp())
        age_hours = max(0, float(power_on_hours) - float(lifetime_hours))
        epoch = int(now - age_hours * 3600)
        print(datetime.fromtimestamp(epoch, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"))
        return
    if test_type != "any":
        print("Never")
        return
    epoch = None
    try:
        from io import StringIO
    except Exception:
        pass
    for line in text.splitlines():
        if "completed without error" not in line.lower():
            continue
        if not match_self_test_type(line, test_type):
            continue
        power_on_hours = data.get("power_on_time", {}).get("hours")
        if power_on_hours is None:
            power_on_hours = text_int(text, r"Power_On_Hours.*?\s(\d+)\s*$")
        match = re.search(r"Completed without error\s+\d+%\s+(\d+)\s+-\s*$", line, re.IGNORECASE)
        if not match or power_on_hours is None:
            continue
        now = int(datetime.now(timezone.utc).timestamp())
        age_hours = max(0, float(power_on_hours) - float(match.group(1)))
        epoch = int(now - age_hours * 3600)
        break
    if epoch is not None:
        print(datetime.fromtimestamp(epoch, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"))
        return
    print("Never")


def format_relative_date(epoch):
    dt = datetime.fromtimestamp(epoch, timezone.utc).astimezone()
    now = datetime.now(timezone.utc).astimezone()
    delta = now - dt
    days = delta.days
    if days >= 365:
        years = days // 365
        return f"{years}y ago ({dt.strftime('%Y-%m-%d')})"
    if days >= 30:
        months = days // 30
        return f"{months}mo ago ({dt.strftime('%Y-%m-%d')})"
    if days >= 1:
        return f"{days}d ago ({dt.strftime('%Y-%m-%d')})"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours}h ago ({dt.strftime('%Y-%m-%d %H:%M')})"
    return f"just now ({dt.strftime('%Y-%m-%d %H:%M')})"


def last_pass_text_value(device: str, test_type: str = "any"):
    data = smartctl_json(device)
    text = smartctl_text(device)
    table = data.get("ata_smart_self_test_log", {}).get("standard", {}).get("table", [])
    for entry in table:
        status = str(entry.get("status", {}).get("string", "")).lower()
        if "completed without error" not in status:
            continue
        test_desc = str(entry.get("type", {}).get("string", "")) or str(entry.get("description", ""))
        if not match_self_test_type(test_desc, test_type):
            continue
        lifetime_hours = entry.get("lifetime_hours")
        power_on_hours = data.get("power_on_time", {}).get("hours")
        if lifetime_hours is None or power_on_hours is None:
            continue
        now = int(datetime.now(timezone.utc).timestamp())
        age_hours = max(0, float(power_on_hours) - float(lifetime_hours))
        epoch = int(now - age_hours * 3600)
        return format_relative_date(epoch)
    for line in text.splitlines():
        if "completed without error" not in line.lower():
            continue
        if not match_self_test_type(line, test_type):
            continue
        power_on_hours = data.get("power_on_time", {}).get("hours")
        if power_on_hours is None:
            power_on_hours = text_int(text, r"Power_On_Hours.*?\s(\d+)\s*$")
        match = re.search(r"Completed without error\s+\d+%\s+(\d+)\s+-\s*$", line, re.IGNORECASE)
        if not match or power_on_hours is None:
            continue
        now = int(datetime.now(timezone.utc).timestamp())
        age_hours = max(0, float(power_on_hours) - float(match.group(1)))
        epoch = int(now - age_hours * 3600)
        return format_relative_date(epoch)
    return "None"


def selftest_summary(device: str):
    info = smartctl_json(device)
    protocol = normalize_name(str(info.get("device", {}).get("protocol", "")) or str(info.get("device", {}).get("type", "")))
    short_value = "None"
    long_value = "None"
    if protocol == "ata":
        short_value = last_pass_text_value(device, "short")
        long_value = last_pass_text_value(device, "long")
    print(json.dumps({
        "Drive": device_name(device),
        "Short": short_value,
        "Long": long_value,
    }))


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(1)
    command, device = clean_arg(sys.argv[1]), clean_device(sys.argv[2])
    if not device.startswith("/dev/"):
        device = f"/dev/{device}"
    if command == "wearout":
        wearout(device)
        return
    if command == "metric" and len(sys.argv) == 4:
        metric(device, sys.argv[3])
        return
    if command == "text_metric" and len(sys.argv) == 4:
        text_metric(device, sys.argv[3])
        return
    if command == "nvme_metric" and len(sys.argv) == 4:
        nvme_metric(device, sys.argv[3])
        return
    if command == "nvme_text_metric" and len(sys.argv) == 4:
        nvme_text_metric(device, sys.argv[3])
        return
    if command == "last_pass_epoch":
        last_pass_epoch(device)
        return
    if command == "last_pass_epoch_type" and len(sys.argv) == 4:
        last_pass_epoch(device, sys.argv[3])
        return
    if command == "last_pass_text_type" and len(sys.argv) == 4:
        last_pass_text(device, sys.argv[3])
        return
    if command == "selftest_summary":
        selftest_summary(device)
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
PY

chmod 755 /usr/local/bin/zabbix-intel-sata-smart.py

cat >/etc/sudoers.d/zabbix-smartctl <<'EOF'
zabbix ALL=(root) NOPASSWD: /usr/sbin/smartctl
EOF

chmod 440 /etc/sudoers.d/zabbix-smartctl

cat >/etc/zabbix/zabbix_agent2.d/intel-sata-smart.conf <<'EOF'
UserParameter=smart.intel.wearout[*],/usr/local/bin/zabbix-intel-sata-smart.py wearout "$1"
UserParameter=smart.intel.last_pass_epoch[*],/usr/local/bin/zabbix-intel-sata-smart.py last_pass_epoch "$1"
UserParameter=smart.intel.last_pass_epoch_type[*],/usr/local/bin/zabbix-intel-sata-smart.py last_pass_epoch_type "$1" "$2"
UserParameter=smart.intel.last_pass_text_type[*],/usr/local/bin/zabbix-intel-sata-smart.py last_pass_text_type "$1" "$2"
UserParameter=smart.selftest.summary[*],/usr/local/bin/zabbix-intel-sata-smart.py selftest_summary "$1"
UserParameter=smart.intel.metric[*],/usr/local/bin/zabbix-intel-sata-smart.py metric "$1" "$2"
UserParameter=smart.intel.text[*],/usr/local/bin/zabbix-intel-sata-smart.py text_metric "$1" "$2"
UserParameter=smart.nvme.metric[*],/usr/local/bin/zabbix-intel-sata-smart.py nvme_metric "$1" "$2"
UserParameter=smart.nvme.text[*],/usr/local/bin/zabbix-intel-sata-smart.py nvme_text_metric "$1" "$2"
EOF

systemctl restart zabbix-agent2

echo "== SMART checks =="
sudo -u zabbix zabbix_agent2 -t smart.intel.wearout[sda] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.wearout[sdb] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch[sda] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch[sdb] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch_type[sda,short] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch_type[sda,long] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.metric[sda,wear_remaining] || true
sudo -u zabbix zabbix_agent2 -t smart.intel.metric[sda,host_writes_32mib] || true
sudo -u zabbix zabbix_agent2 -t smart.nvme.metric[nvme0,wear_used] || true
sudo -u zabbix zabbix_agent2 -t smart.nvme.metric[nvme1,wear_used] || true
