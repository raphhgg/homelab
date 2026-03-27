#!/usr/bin/env bash
set -euo pipefail

if ! command -v zabbix_agent2 >/dev/null 2>&1; then
  echo "zabbix_agent2 not found. Install Zabbix Agent 2 first." >&2
  exit 1
fi

if ! command -v qm >/dev/null 2>&1; then
  echo "qm not found. Run this on a Proxmox node." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3
fi

install -d -m 755 /usr/local/bin

rm -f /etc/sudoers.d/zabbix-qm-guest-exec

cat >/usr/local/bin/zabbix-truenas-scale.py <<'PY'
#!/usr/bin/env python3
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


VMID = os.getenv("TRUENAS_VM_ID", "202")
STORCLI64_PATH = os.getenv("TRUENAS_STORCLI64_PATH", "/mnt/Vault/monitoring/bin/storcli64")
QM_TIMEOUT = int(os.getenv("TRUENAS_QM_TIMEOUT", "45"))
CACHE_PATH = Path(os.getenv("TRUENAS_CACHE_PATH", "/tmp/zabbix-truenas-scale-summary.json"))
CACHE_LOCK_PATH = Path(str(CACHE_PATH) + ".lock")
CACHE_TTL_SECONDS = int(os.getenv("TRUENAS_CACHE_TTL", "180"))
TEMP_CACHE_PATH = Path(os.getenv("TRUENAS_TEMP_CACHE_PATH", "/tmp/zabbix-truenas-scale-temps.json"))
TEMP_CACHE_LOCK_PATH = Path(str(TEMP_CACHE_PATH) + ".lock")
TEMP_CACHE_TTL_SECONDS = int(os.getenv("TRUENAS_TEMP_CACHE_TTL", "60"))
DETAILS_CACHE_PATH = Path(os.getenv("TRUENAS_DETAILS_CACHE_PATH", "/tmp/zabbix-truenas-scale-details.json"))
DETAILS_CACHE_LOCK_PATH = Path(str(DETAILS_CACHE_PATH) + ".lock")
DETAILS_CACHE_TTL_SECONDS = int(os.getenv("TRUENAS_DETAILS_CACHE_TTL", "300"))
JOBS_LIMIT = int(os.getenv("TRUENAS_JOBS_LIMIT", "20"))


def run_qm_guest_exec(command):
    proc = subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/sbin/qm", "guest", "exec", VMID, "--", *command],
        text=True,
        capture_output=True,
        check=False,
        timeout=QM_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"qm guest exec failed ({proc.returncode})")

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse qm guest exec output: {exc}") from exc

    return int(payload.get("exitcode", 1)), payload.get("out-data", ""), payload.get("err-data", "")


def parse_temp(output):
    patterns = [
        r"(?:ROC|Ctrl)\s+temperature\(Degree Celsius\)\s*(?:=\s*)?(\d+)",
        r"Temperature:\s*(\d+)\s*C",
        r"Current Temp In Celsius:\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def short_error(text):
    text = (text or "").strip()
    if not text:
        return "no output"
    text = re.sub(r"\s+", " ", text)
    return text[:200]


def format_relative_date(epoch):
    if epoch is None:
        return "None"
    try:
        dt = datetime.datetime.fromtimestamp(int(epoch), tz=datetime.timezone.utc)
    except (TypeError, ValueError, OSError):
        return "None"

    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    if delta.days >= 365:
        years = delta.days // 365
        return f"{years}y ago ({dt.strftime('%Y-%m-%d')})"
    if delta.days >= 30:
        months = delta.days // 30
        return f"{months}mo ago ({dt.strftime('%Y-%m-%d')})"
    if delta.days >= 1:
        return f"{delta.days}d ago ({dt.strftime('%Y-%m-%d')})"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours}h ago ({dt.strftime('%Y-%m-%d %H:%M')})"
    minutes = max(1, delta.seconds // 60)
    return f"{minutes}m ago ({dt.strftime('%Y-%m-%d %H:%M')})"


def compact_text(value, limit=160):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit]


def probe_hba_temp():
    checks = [
        ("storcli64_dataset", [STORCLI64_PATH, "/c0", "show", "temperature"]),
        ("storcli_builtin", ["storcli", "/c0", "show", "temperature"]),
        ("sas3ircu_display", ["sas3ircu", "0", "DISPLAY"]),
    ]

    errors = []
    for method, command in checks:
        try:
            exitcode, out_data, err_data = run_qm_guest_exec(command)
        except Exception as exc:
            errors.append(f"{method}: {short_error(str(exc))}")
            continue

        combined = f"{out_data}\n{err_data}"
        temp = parse_temp(combined)
        if temp is not None:
            return {
                "ok": True,
                "temp": int(temp),
                "method": method,
                "error": "",
                "exitcode": exitcode,
            }

        errors.append(f"{method}: {short_error(combined)}")

    return {
        "ok": False,
        "temp": -1,
        "method": "none",
        "error": "; ".join(errors)[:500],
        "exitcode": 1,
    }


def parse_ts(value):
    if value is None:
        return None

    if isinstance(value, dict):
        if "$date" in value:
            return parse_ts(value.get("$date"))
        return None

    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            return float(value) / 1000.0
        return float(value)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return parse_ts(int(raw))
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.timestamp()
        except ValueError:
            return None

    return None


def call_midclt(method):
    exitcode, out_data, err_data = run_qm_guest_exec(["midclt", "call", method])
    if exitcode != 0:
        raise RuntimeError(err_data.strip() or f"midclt {method} failed")

    data = out_data.strip()
    if not data:
        return None

    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON from midclt {method}: {exc}") from exc


def get_monitored_disks():
    disks = call_midclt("disk.query") or []
    monitored = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue

        name = str(disk.get("name") or disk.get("devname") or "").strip()
        if not name:
            continue

        model = str(disk.get("model") or "")
        if "QEMU" in model.upper():
            continue

        if not disk.get("zfs_guid"):
            continue

        monitored.append(
            {
                "name": name,
                "serial": str(disk.get("serial") or ""),
                "model": model,
                "size_bytes": int(disk.get("size") or 0),
                "bus": str(disk.get("bus") or ""),
                "identifier": str(disk.get("identifier") or ""),
            }
        )

    monitored.sort(key=lambda item: item["name"])
    return monitored


def get_pool_disk_map(pools):
    mapping = {}

    def _walk(vdev, pool_name):
        if not isinstance(vdev, dict):
            return
        disk = str(vdev.get("disk") or "").strip()
        if disk:
            mapping[disk] = pool_name
        for child in vdev.get("children", []) or []:
            _walk(child, pool_name)

    for pool in pools or []:
        if not isinstance(pool, dict):
            continue
        pool_name = str(pool.get("name") or "")
        topology = pool.get("topology", {})
        if not isinstance(topology, dict):
            continue
        for group_name in ("data", "log", "cache", "spare", "special", "dedup"):
            for vdev in topology.get(group_name, []) or []:
                _walk(vdev, pool_name)

    return mapping


def _load_json_cache(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_json_cache(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=True))
    tmp.replace(path)


def _cache_with_age(path):
    data = _load_json_cache(path)
    if data is None:
        return None
    ts = data.get("timestamp", 0)
    try:
        age = max(0, int(time.time()) - int(ts))
    except Exception:
        age = 10**9
    data["cache_age_seconds"] = age
    return data


def build_temp_cache():
    cache = {
        "timestamp": int(time.time()),
        "drives": [],
        "errors": [],
    }

    pools = call_midclt("pool.query") or []
    pool_disk_map = get_pool_disk_map(pools)
    disks = get_monitored_disks()

    try:
        temp_map = call_midclt("disk.temperatures") or {}
    except Exception as exc:
        cache["errors"].append(f"disk.temperatures: {short_error(str(exc))}")
        temp_map = {}

    for disk in disks:
        name = disk["name"]
        value = temp_map.get(name)
        temp_c = None
        if isinstance(value, (int, float)):
            temp_c = round(float(value), 2)

        cache["drives"].append(
            {
                "drive": name,
                "pool": pool_disk_map.get(name, ""),
                "model": disk["model"],
                "serial": disk["serial"],
                "size_bytes": disk["size_bytes"],
                "bus": disk["bus"],
                "temp_c": temp_c,
            }
        )

    return cache


def refresh_temp_cache_sync():
    if TEMP_CACHE_LOCK_PATH.exists():
        lock_age = int(time.time() - TEMP_CACHE_LOCK_PATH.stat().st_mtime)
        if lock_age < 90:
            cached = _cache_with_age(TEMP_CACHE_PATH)
            if cached is not None:
                return cached

    try:
        TEMP_CACHE_LOCK_PATH.write_text(str(int(time.time())))
        data = build_temp_cache()
        _write_json_cache(TEMP_CACHE_PATH, data)
        data["cache_age_seconds"] = 0
        return data
    finally:
        try:
            TEMP_CACHE_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def get_temp_cache():
    cached = _cache_with_age(TEMP_CACHE_PATH)
    if cached is None:
        return refresh_temp_cache_sync()
    if cached.get("cache_age_seconds", 10**9) <= TEMP_CACHE_TTL_SECONDS:
        return cached
    return refresh_temp_cache_sync()


def smartctl_json(device):
    exitcode, out_data, err_data = run_qm_guest_exec(["smartctl", "-j", "-a", f"/dev/{device}"])
    if exitcode != 0:
        raise RuntimeError(short_error(err_data or out_data))
    try:
        return json.loads(out_data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"smartctl parse error for {device}: {exc}") from exc


def smart_attr_raw(data, attr_name, fallback_ids=()):
    table = ((data or {}).get("ata_smart_attributes") or {}).get("table") or []
    for row in table:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if name == attr_name:
            raw = row.get("raw", {})
            if isinstance(raw, dict):
                return int(raw.get("value") or 0)
            try:
                return int(raw)
            except Exception:
                return 0

    for row in table:
        if not isinstance(row, dict):
            continue
        if int(row.get("id") or 0) in fallback_ids:
            raw = row.get("raw", {})
            if isinstance(raw, dict):
                return int(raw.get("value") or 0)
            try:
                return int(raw)
            except Exception:
                return 0

    return 0


def smart_last_pass(data, test_kind):
    table = (((data or {}).get("ata_smart_self_test_log") or {}).get("standard") or {}).get("table") or []
    if not isinstance(table, list):
        return None, "None"

    now_epoch = int((((data or {}).get("local_time") or {}).get("time_t") or time.time()))
    power_on_hours = ((data or {}).get("power_on_time") or {}).get("hours")

    for row in table:
        if not isinstance(row, dict):
            continue
        status = str(((row.get("status") or {}).get("string") or "")).lower()
        if "completed without error" not in status:
            continue

        test_label = str(((row.get("type") or {}).get("string") or "")).lower()
        if test_kind == "short" and "short" not in test_label:
            continue
        if test_kind == "long" and not ("extended" in test_label or "long" in test_label):
            continue

        lifetime = row.get("lifetime_hours")
        if lifetime is None or power_on_hours is None:
            return None, "Unknown"

        try:
            age_hours = max(0.0, float(power_on_hours) - float(lifetime))
            epoch = int(now_epoch - age_hours * 3600)
            return epoch, format_relative_date(epoch)
        except Exception:
            return None, "Unknown"

    return None, "None"


def schedule_to_text(schedule):
    if not isinstance(schedule, dict):
        return ""
    minute = schedule.get("minute", "*")
    hour = schedule.get("hour", "*")
    dom = schedule.get("dom", "*")
    month = schedule.get("month", "*")
    dow = schedule.get("dow", "*")
    begin = schedule.get("begin")
    end = schedule.get("end")
    cron = f"{minute} {hour} {dom} {month} {dow}"
    if begin and end:
        return f"{cron} ({begin}-{end})"
    return cron


def dataset_display_name(dataset_name):
    if not isinstance(dataset_name, str):
        return ""
    if "/" in dataset_name:
        return dataset_name.split("/", 1)[1]
    return dataset_name


def _vdev_size_bytes(vdev):
    if not isinstance(vdev, dict):
        return 0

    stats = vdev.get("stats", {})
    if isinstance(stats, dict):
        for key in ("size", "asize", "psize"):
            value = to_float(stats.get(key))
            if value and value > 0:
                return int(value)

    children = vdev.get("children", []) or []
    total = 0
    for child in children:
        if not isinstance(child, dict):
            continue
        child_stats = child.get("stats", {})
        if isinstance(child_stats, dict):
            for key in ("size", "asize", "psize"):
                value = to_float(child_stats.get(key))
                if value and value > 0:
                    total += int(value)
                    break

    return total


def describe_data_topology(topology):
    if not isinstance(topology, dict):
        return ""

    data_vdevs = topology.get("data", []) or []
    if not isinstance(data_vdevs, list) or not data_vdevs:
        return ""

    groups = {}
    for vdev in data_vdevs:
        if not isinstance(vdev, dict):
            continue

        vtype = str(vdev.get("type") or "DISK").upper()
        children = vdev.get("children", []) or []
        width = len(children) if isinstance(children, list) and children else 1
        vdev_size = _vdev_size_bytes(vdev)
        size_tib = round((vdev_size / max(width, 1)) / (1024 ** 4), 2) if vdev_size > 0 else None

        key = (vtype, width, size_tib)
        groups[key] = groups.get(key, 0) + 1

    if not groups:
        return ""

    parts = []
    for (vtype, width, size_tib), count in groups.items():
        label = f"{count} x {vtype}"
        if width > 1:
            label += f" | {width} wide"
        if size_tib is not None and size_tib > 0:
            label += f" | {size_tib:.2f} TiB"
        parts.append(label)

    return " + ".join(parts)


def get_pool_usable_tib_map():
    usable = {}

    try:
        datasets = call_midclt("pool.dataset.query") or []
    except Exception:
        return usable

    for row in datasets:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name") or "")
        if not name or "/" in name:
            continue

        used = to_float(((row.get("used") or {}).get("parsed"))) or 0.0
        available = to_float(((row.get("available") or {}).get("parsed"))) or 0.0
        total = used + available
        if total <= 0:
            continue

        usable[name] = round(total / (1024 ** 4), 2)

    return usable


def build_details_cache():
    data = {
        "timestamp": int(time.time()),
        "drives": [],
        "pools": [],
        "datasets": [],
        "tasks": [],
        "jobs": [],
        "errors": [],
    }

    pools = []
    try:
        pools = call_midclt("pool.query") or []
    except Exception as exc:
        data["errors"].append(f"pool.query: {short_error(str(exc))}")

    pool_disk_map = get_pool_disk_map(pools)

    pool_usable_tib = get_pool_usable_tib_map()

    for pool in pools:
        if not isinstance(pool, dict):
            continue
        pool_name = str(pool.get("name") or "")
        size = to_float(pool.get("size") or pool.get("size_str")) or 0.0
        allocated = to_float(pool.get("allocated") or pool.get("allocated_str")) or 0.0
        free = to_float(pool.get("free") or pool.get("free_str")) or 0.0
        used_pct = round((allocated / size) * 100.0, 2) if size > 0 else 0.0

        read_err = 0
        write_err = 0
        csum_err = 0
        topology = pool.get("topology", {})
        if isinstance(topology, dict):
            for group_name in ("data", "log", "cache", "spare", "special", "dedup"):
                for vdev in topology.get(group_name, []) or []:
                    for node in walk_vdevs(vdev):
                        stats = node.get("stats", {})
                        if isinstance(stats, dict):
                            read_err += int(stats.get("read_errors") or 0)
                            write_err += int(stats.get("write_errors") or 0)
                            csum_err += int(stats.get("checksum_errors") or 0)

        data["pools"].append(
            {
                "pool": pool_name,
                "status": str(pool.get("status") or ""),
                "healthy": bool(pool.get("healthy", False)),
                "size_bytes": int(size),
                "usable_tib": pool_usable_tib.get(pool_name, round((float(size) / (1024 ** 4)), 2) if size > 0 else 0.0),
                "allocated_bytes": int(allocated),
                "free_bytes": int(free),
                "used_pct": used_pct,
                "read_errors": read_err,
                "write_errors": write_err,
                "checksum_errors": csum_err,
                "data_topology": describe_data_topology(topology),
            }
        )

    try:
        datasets = call_midclt("pool.dataset.query") or []
    except Exception as exc:
        data["errors"].append(f"pool.dataset.query: {short_error(str(exc))}")
        datasets = []

    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue

        dataset_name = str(dataset.get("name") or "")
        if not dataset_name or "/" not in dataset_name:
            continue

        used_obj = dataset.get("used") or {}
        avail_obj = dataset.get("available") or {}
        used = to_float((used_obj.get("parsed") if isinstance(used_obj, dict) else None)) or 0.0
        available = to_float((avail_obj.get("parsed") if isinstance(avail_obj, dict) else None)) or 0.0

        data["datasets"].append(
            {
                "dataset": dataset_name,
                "name": dataset_display_name(dataset_name),
                "pool": dataset_name.split("/", 1)[0],
                "used_bytes": int(used),
                "available_bytes": int(available),
                "used_human": (used_obj.get("value") if isinstance(used_obj, dict) else "") or "",
                "available_human": (avail_obj.get("value") if isinstance(avail_obj, dict) else "") or "",
                "encryption": "Encrypted" if bool(dataset.get("encrypted", False)) else "Unencrypted",
            }
        )

    data["datasets"].sort(key=lambda row: row.get("dataset", ""))

    temp_cache = get_temp_cache()
    temp_by_drive = {row.get("drive"): row.get("temp_c") for row in temp_cache.get("drives", []) if isinstance(row, dict)}

    try:
        disks = get_monitored_disks()
    except Exception as exc:
        data["errors"].append(f"disk.query: {short_error(str(exc))}")
        disks = []

    for disk in disks:
        name = disk["name"]
        try:
            smart = smartctl_json(name)
        except Exception as exc:
            data["errors"].append(f"smartctl {name}: {short_error(str(exc))}")
            smart = {}

        short_epoch, short_text = smart_last_pass(smart, "short")
        long_epoch, long_text = smart_last_pass(smart, "long")

        health = ((smart.get("smart_status") or {}).get("passed"))
        if health is True:
            health_text = "PASSED"
        elif health is False:
            health_text = "FAILED"
        else:
            health_text = "UNKNOWN"

        drive_entry = {
            "drive": name,
            "pool": pool_disk_map.get(name, ""),
            "model": disk["model"],
            "serial": disk["serial"],
            "size_bytes": disk["size_bytes"],
            "bus": disk["bus"],
            "temp_c": temp_by_drive.get(name),
            "health": health_text,
            "reallocated": smart_attr_raw(smart, "Reallocated_Sector_Ct", fallback_ids=(5,)),
            "pending": smart_attr_raw(smart, "Current_Pending_Sector", fallback_ids=(197,)),
            "offline_uncorrectable": smart_attr_raw(smart, "Offline_Uncorrectable", fallback_ids=(198,)),
            "power_on_hours": int(((smart.get("power_on_time") or {}).get("hours") or 0)),
            "short_last_pass_epoch": short_epoch,
            "short_last_pass": short_text,
            "long_last_pass_epoch": long_epoch,
            "long_last_pass": long_text,
        }
        data["drives"].append(drive_entry)

    def add_task_entries(method, task_type, name_builder):
        try:
            rows = call_midclt(method) or []
        except Exception as exc:
            data["errors"].append(f"{method}: {short_error(str(exc))}")
            rows = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            enabled = bool(row.get("enabled", True))
            state_obj = row.get("state", {})
            if not isinstance(state_obj, dict):
                state_obj = {}
            state = str(state_obj.get("state") or "UNKNOWN")
            ts = parse_ts(state_obj.get("datetime"))
            data["tasks"].append(
                {
                    "task_type": task_type,
                    "task_id": str(row.get("id")),
                    "name": name_builder(row),
                    "enabled": enabled,
                    "schedule": schedule_to_text(row.get("schedule")),
                    "state": state,
                    "last_run_epoch": int(ts) if ts else None,
                    "last_run": format_relative_date(ts),
                }
            )

    add_task_entries("pool.snapshottask.query", "snapshot", lambda row: str(row.get("dataset") or row.get("id")))
    add_task_entries("replication.query", "replication", lambda row: str(row.get("name") or row.get("id")))
    add_task_entries("cloudsync.query", "cloudsync", lambda row: str(row.get("description") or row.get("path") or row.get("id")))
    add_task_entries("rsynctask.query", "rsync", lambda row: str(row.get("path") or row.get("id")))
    add_task_entries("pool.scrub.query", "scrub", lambda row: str(row.get("pool_name") or row.get("pool") or row.get("id")))

    try:
        jobs = call_midclt("core.get_jobs") or []
    except Exception as exc:
        data["errors"].append(f"core.get_jobs: {short_error(str(exc))}")
        jobs = []

    def _job_sort_key(job):
        return (
            parse_ts(job.get("time_started"))
            or parse_ts(job.get("time_finished"))
            or parse_ts(job.get("time_created"))
            or 0
        )

    for idx, job in enumerate(sorted((j for j in jobs if isinstance(j, dict)), key=_job_sort_key, reverse=True)[:JOBS_LIMIT]):
        started = parse_ts(job.get("time_started"))
        finished = parse_ts(job.get("time_finished"))
        duration = None
        if started and finished:
            duration = max(0, int(finished - started))

        data["jobs"].append(
            {
                "index": idx,
                "job_id": int(job.get("id") or 0),
                "method": str(job.get("method") or ""),
                "state": str(job.get("state") or ""),
                "started_epoch": int(started) if started else None,
                "started": format_relative_date(started),
                "finished_epoch": int(finished) if finished else None,
                "finished": format_relative_date(finished) if finished else "",
                "duration_sec": duration if duration is not None else 0,
                "error": compact_text(job.get("error") or job.get("exception") or ""),
                "result": compact_text(job.get("result") or ""),
            }
        )

    data["tasks"].sort(key=lambda row: (row.get("task_type", ""), row.get("name", "")))
    return data


def refresh_details_cache_sync():
    if DETAILS_CACHE_LOCK_PATH.exists():
        lock_age = int(time.time() - DETAILS_CACHE_LOCK_PATH.stat().st_mtime)
        if lock_age < 180:
            cached = _cache_with_age(DETAILS_CACHE_PATH)
            if cached is not None:
                return cached

    try:
        DETAILS_CACHE_LOCK_PATH.write_text(str(int(time.time())))
        data = build_details_cache()
        _write_json_cache(DETAILS_CACHE_PATH, data)
        data["cache_age_seconds"] = 0
        return data
    finally:
        try:
            DETAILS_CACHE_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def _spawn_details_background_refresh():
    if DETAILS_CACHE_LOCK_PATH.exists():
        lock_age = int(time.time() - DETAILS_CACHE_LOCK_PATH.stat().st_mtime)
        if lock_age < 180:
            return

    subprocess.Popen(
        [sys.executable, __file__, "refresh_details_cache"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def get_details_cache():
    cached = _cache_with_age(DETAILS_CACHE_PATH)
    if cached is None:
        return refresh_details_cache_sync()

    if cached.get("cache_age_seconds", 10**9) <= DETAILS_CACHE_TTL_SECONDS:
        return cached

    _spawn_details_background_refresh()
    return cached


def count_failed_tasks(tasks):
    failed_states = {"FAILED", "ERROR", "ABORTED"}
    total = 0
    failed = 0

    for task in tasks or []:
        if isinstance(task, dict) and task.get("enabled") is False:
            continue
        total += 1
        state = ""
        if isinstance(task, dict):
            state_obj = task.get("state", {})
            if isinstance(state_obj, dict):
                state = str(state_obj.get("state", ""))
            elif state_obj is not None:
                state = str(state_obj)
        if state.strip().upper() in failed_states:
            failed += 1

    return total, failed


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def walk_vdevs(vdev):
    if isinstance(vdev, dict):
        yield vdev
        for child in vdev.get("children", []) or []:
            yield from walk_vdevs(child)


def summarize_pools(pools):
    stats = {
        "pool_count": 0,
        "pool_warning_count": 0,
        "pool_unhealthy_count": 0,
        "pool_degraded_count": 0,
        "pool_offline_count": 0,
        "pool_usage_pct_max": 0.0,
        "pool_usage_pct_avg": 0.0,
        "pool_size_bytes_total": 0,
        "pool_allocated_bytes_total": 0,
        "pool_free_bytes_total": 0,
        "pool_read_errors_total": 0,
        "pool_write_errors_total": 0,
        "pool_checksum_errors_total": 0,
    }

    usages = []
    degraded_statuses = {"DEGRADED", "FAULTED", "UNAVAIL", "UNAVAILABLE", "SUSPENDED", "REMOVED"}
    offline_statuses = {"OFFLINE", "UNAVAIL", "UNAVAILABLE", "FAULTED", "REMOVED", "SUSPENDED"}

    for pool in pools or []:
        if not isinstance(pool, dict):
            continue

        stats["pool_count"] += 1

        status = str(pool.get("status") or "").upper()
        healthy = bool(pool.get("healthy", False))
        warning = bool(pool.get("warning", False))
        status_code = str(pool.get("status_code") or "").upper()

        if warning:
            stats["pool_warning_count"] += 1
        if (not healthy) or status in degraded_statuses or status_code not in {"", "OK"}:
            stats["pool_unhealthy_count"] += 1
        if status in degraded_statuses:
            stats["pool_degraded_count"] += 1
        if status in offline_statuses:
            stats["pool_offline_count"] += 1

        size = to_float(pool.get("size")) or to_float(pool.get("size_str")) or 0.0
        allocated = to_float(pool.get("allocated")) or to_float(pool.get("allocated_str")) or 0.0
        free = to_float(pool.get("free")) or to_float(pool.get("free_str")) or 0.0

        stats["pool_size_bytes_total"] += int(size)
        stats["pool_allocated_bytes_total"] += int(allocated)
        stats["pool_free_bytes_total"] += int(free)

        if size > 0:
            usages.append((allocated / size) * 100.0)

        topology = pool.get("topology", {})
        if isinstance(topology, dict):
            for group_name in ("data", "log", "cache", "spare", "special", "dedup"):
                for vdev in topology.get(group_name, []) or []:
                    for node in walk_vdevs(vdev):
                        node_stats = node.get("stats", {})
                        if not isinstance(node_stats, dict):
                            continue
                        stats["pool_read_errors_total"] += int(node_stats.get("read_errors") or 0)
                        stats["pool_write_errors_total"] += int(node_stats.get("write_errors") or 0)
                        stats["pool_checksum_errors_total"] += int(node_stats.get("checksum_errors") or 0)

    if usages:
        stats["pool_usage_pct_max"] = round(max(usages), 2)
        stats["pool_usage_pct_avg"] = round(sum(usages) / len(usages), 2)

    return stats


def summarize_drive_temperatures():
    stats = {
        "drive_temp_count": 0,
        "drive_temp_max_c": 0.0,
        "drive_temp_avg_c": 0.0,
        "drive_temp_over_45_count": 0,
        "drive_temp_over_50_count": 0,
    }

    cache = get_temp_cache()
    values = []
    for row in cache.get("drives", []):
        if not isinstance(row, dict):
            continue
        value = row.get("temp_c")
        if isinstance(value, (int, float)):
            values.append(float(value))

    if not values:
        return stats

    stats["drive_temp_count"] = len(values)
    stats["drive_temp_max_c"] = round(max(values), 2)
    stats["drive_temp_avg_c"] = round(sum(values) / len(values), 2)
    stats["drive_temp_over_45_count"] = sum(1 for value in values if value >= 45.0)
    stats["drive_temp_over_50_count"] = sum(1 for value in values if value >= 50.0)
    return stats


def summarize():
    summary = {
        "timestamp": int(time.time()),
        "vmid": VMID,
        "hba_temp_c": -1,
        "hba_telemetry": 0,
        "hba_method": "none",
        "jobs_running": 0,
        "jobs_total_24h": 0,
        "jobs_success_24h": 0,
        "jobs_failed_24h": 0,
        "jobs_total_7d": 0,
        "jobs_success_7d": 0,
        "jobs_failed_7d": 0,
        "alerts_active": 0,
        "alerts_critical": 0,
        "pool_count": 0,
        "pool_warning_count": 0,
        "pool_unhealthy_count": 0,
        "pool_degraded_count": 0,
        "pool_offline_count": 0,
        "pool_usage_pct_max": 0.0,
        "pool_usage_pct_avg": 0.0,
        "pool_size_bytes_total": 0,
        "pool_allocated_bytes_total": 0,
        "pool_free_bytes_total": 0,
        "pool_read_errors_total": 0,
        "pool_write_errors_total": 0,
        "pool_checksum_errors_total": 0,
        "pool_primary_name": "",
        "pool_primary_status": "",
        "pool_primary_data_topology": "",
        "pool_primary_usable_tib": 0.0,
        "drive_temp_count": 0,
        "drive_temp_max_c": 0.0,
        "drive_temp_avg_c": 0.0,
        "drive_temp_over_45_count": 0,
        "drive_temp_over_50_count": 0,
        "drives_monitored_count": 0,
        "drives_smart_failed_count": 0,
        "drives_reallocated_total": 0,
        "drives_pending_total": 0,
        "drives_offline_uncorrectable_total": 0,
        "drives_without_short_test_count": 0,
        "drives_without_long_test_count": 0,
        "scrub_tasks_enabled": 0,
        "scrub_running": 0,
        "resilver_running": 0,
        "snapshot_tasks_total": 0,
        "snapshot_tasks_failed": 0,
        "replication_tasks_total": 0,
        "replication_tasks_failed": 0,
        "cloudsync_tasks_total": 0,
        "cloudsync_tasks_failed": 0,
        "rsync_tasks_total": 0,
        "rsync_tasks_failed": 0,
        "errors": [],
    }

    hba = probe_hba_temp()
    summary["hba_temp_c"] = hba["temp"]
    summary["hba_telemetry"] = 1 if hba["ok"] else 0
    summary["hba_method"] = hba["method"]
    if hba["error"]:
        summary["errors"].append(f"hba: {hba['error']}")

    def safe_call(method, default):
        try:
            return call_midclt(method)
        except Exception as exc:
            summary["errors"].append(f"{method}: {short_error(str(exc))}")
            return default

    jobs = safe_call("core.get_jobs", []) or []
    now = time.time()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        state = str(job.get("state", "")).upper()
        if state in {"RUNNING", "WAITING"}:
            summary["jobs_running"] += 1
        elif state == "":
            progress = job.get("progress", {})
            if isinstance(progress, dict):
                percent = progress.get("percent")
                if isinstance(percent, (int, float)) and percent < 100 and not job.get("error"):
                    summary["jobs_running"] += 1

        ts = (
            parse_ts(job.get("time_finished"))
            or parse_ts(job.get("time_ended"))
            or parse_ts(job.get("time_started"))
            or parse_ts(job.get("time_created"))
        )

        if ts is not None:
            age = now - ts
            state = str(job.get("state", "")).upper()
            has_error = bool(job.get("error") or job.get("exception"))

            if age <= 86400:
                summary["jobs_total_24h"] += 1
                if has_error or state in {"FAILED", "ERROR", "ABORTED"}:
                    summary["jobs_failed_24h"] += 1
                elif state in {"SUCCESS", "FINISHED", "DONE"}:
                    summary["jobs_success_24h"] += 1

            if age <= 604800:
                summary["jobs_total_7d"] += 1
                if has_error or state in {"FAILED", "ERROR", "ABORTED"}:
                    summary["jobs_failed_7d"] += 1
                elif state in {"SUCCESS", "FINISHED", "DONE"}:
                    summary["jobs_success_7d"] += 1

    alerts = safe_call("alert.list", []) or []
    summary["alerts_active"] = len(alerts)
    critical_levels = {"CRITICAL", "ALERT", "EMERGENCY"}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        level = str(alert.get("level", "")).upper()
        if level in critical_levels:
            summary["alerts_critical"] += 1

    scrub_tasks = safe_call("pool.scrub.query", []) or []
    summary["scrub_tasks_enabled"] = sum(1 for task in scrub_tasks if not isinstance(task, dict) or task.get("enabled", True))

    pools = safe_call("pool.query", []) or []
    summary.update(summarize_pools(pools))
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        scan = pool.get("scan", {})
        if not isinstance(scan, dict):
            continue
        state = str(scan.get("state") or "").upper()
        function = str(scan.get("function") or "").upper()
        if not state or state in {"FINISHED", "NONE", "NULL"}:
            continue
        if "RESILVER" in function:
            summary["resilver_running"] += 1
        else:
            summary["scrub_running"] += 1

    try:
        summary.update(summarize_drive_temperatures())
    except Exception as exc:
        summary["errors"].append(f"drive_temps: {short_error(str(exc))}")

    try:
        details = get_details_cache()
        pools_detail = [row for row in details.get("pools", []) if isinstance(row, dict)]
        if pools_detail:
            primary = sorted(pools_detail, key=lambda row: str(row.get("pool") or ""))[0]
            summary["pool_primary_name"] = str(primary.get("pool") or "")
            summary["pool_primary_status"] = str(primary.get("status") or "")
            summary["pool_primary_data_topology"] = str(primary.get("data_topology") or "")
            summary["pool_primary_usable_tib"] = float(primary.get("usable_tib") or 0.0)

        drives = [row for row in details.get("drives", []) if isinstance(row, dict)]
        summary["drives_monitored_count"] = len(drives)
        summary["drives_smart_failed_count"] = sum(1 for row in drives if str(row.get("health", "")).upper() == "FAILED")
        summary["drives_reallocated_total"] = sum(int(row.get("reallocated") or 0) for row in drives)
        summary["drives_pending_total"] = sum(int(row.get("pending") or 0) for row in drives)
        summary["drives_offline_uncorrectable_total"] = sum(int(row.get("offline_uncorrectable") or 0) for row in drives)
        summary["drives_without_short_test_count"] = sum(1 for row in drives if str(row.get("short_last_pass") or "None") in {"", "None", "Unknown"})
        summary["drives_without_long_test_count"] = sum(1 for row in drives if str(row.get("long_last_pass") or "None") in {"", "None", "Unknown"})
    except Exception as exc:
        summary["errors"].append(f"details_cache: {short_error(str(exc))}")

    snap_tasks = safe_call("pool.snapshottask.query", []) or []
    total, failed = count_failed_tasks(snap_tasks)
    summary["snapshot_tasks_total"] = total
    summary["snapshot_tasks_failed"] = failed

    repl_tasks = safe_call("replication.query", []) or []
    total, failed = count_failed_tasks(repl_tasks)
    summary["replication_tasks_total"] = total
    summary["replication_tasks_failed"] = failed

    cloudsync_tasks = safe_call("cloudsync.query", []) or []
    total, failed = count_failed_tasks(cloudsync_tasks)
    summary["cloudsync_tasks_total"] = total
    summary["cloudsync_tasks_failed"] = failed

    rsync_tasks = safe_call("rsynctask.query", []) or []
    total, failed = count_failed_tasks(rsync_tasks)
    summary["rsync_tasks_total"] = total
    summary["rsync_tasks_failed"] = failed

    summary["error_count"] = len(summary["errors"])
    return summary


def _load_cached_summary():
    if not CACHE_PATH.exists():
        return None

    try:
        data = json.loads(CACHE_PATH.read_text())
    except Exception:
        return None

    ts = data.get("timestamp", 0)
    try:
        age = max(0, int(time.time()) - int(ts))
    except Exception:
        age = 10**9

    data["cache_age_seconds"] = age
    return data


def _write_cached_summary(data):
    tmp_path = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, separators=(",", ":")))
    tmp_path.replace(CACHE_PATH)


def refresh_cache_sync():
    if CACHE_LOCK_PATH.exists():
        lock_age = int(time.time() - CACHE_LOCK_PATH.stat().st_mtime)
        if lock_age < 120:
            cached = _load_cached_summary()
            if cached is not None:
                return cached

    try:
        CACHE_LOCK_PATH.write_text(str(int(time.time())))
        data = summarize()
        _write_cached_summary(data)
        return data
    finally:
        try:
            CACHE_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def _spawn_background_refresh():
    if CACHE_LOCK_PATH.exists():
        lock_age = int(time.time() - CACHE_LOCK_PATH.stat().st_mtime)
        if lock_age < 120:
            return

    subprocess.Popen(
        [sys.executable, __file__, "refresh_cache"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def get_summary_cached():
    cached = _load_cached_summary()
    if cached is None:
        return refresh_cache_sync()

    if cached.get("cache_age_seconds", 10**9) <= CACHE_TTL_SECONDS:
        return cached

    _spawn_background_refresh()
    return cached


def print_summary_metric(key):
    data = get_summary_cached()
    value = data.get(key)
    if isinstance(value, bool):
        print("1" if value else "0")
        return
    if value is None:
        print("")
        return
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":")))
        return
    print(value)


def print_details_slice(key):
    data = get_details_cache()
    value = data.get(key)
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    elif value is None:
        print("[]")
    else:
        print(value)


def print_drive_temp(drive):
    drive = drive.strip()
    data = get_temp_cache()
    for row in data.get("drives", []):
        if isinstance(row, dict) and row.get("drive") == drive:
            value = row.get("temp_c")
            if isinstance(value, (int, float)):
                print(round(float(value), 2))
                return
            print(-1)
            return
    print(-1)


def print_drive_selftest_summary(drive):
    drive = drive.strip()
    data = get_details_cache()
    for row in data.get("drives", []):
        if not isinstance(row, dict):
            continue
        if row.get("drive") != drive:
            continue
        payload = {
            "Drive": drive,
            "Short": row.get("short_last_pass", "None"),
            "Long": row.get("long_last_pass", "None"),
        }
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        return

    print(json.dumps({"Drive": drive, "Short": "None", "Long": "None"}, separators=(",", ":"), ensure_ascii=True))


def print_drive_health_summary(drive):
    drive = drive.strip()
    data = get_details_cache()
    for row in data.get("drives", []):
        if not isinstance(row, dict):
            continue
        if row.get("drive") != drive:
            continue
        payload = {
            "Drive": drive,
            "Pool": row.get("pool", ""),
            "Health": row.get("health", "UNKNOWN"),
            "Temp": row.get("temp_c", -1),
            "Reallocated": row.get("reallocated", 0),
            "Pending": row.get("pending", 0),
            "OfflineUncorrectable": row.get("offline_uncorrectable", 0),
            "PowerOnHours": row.get("power_on_hours", 0),
        }
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        return

    print(json.dumps({"Drive": drive, "Health": "UNKNOWN"}, separators=(",", ":"), ensure_ascii=True))


def print_pool_summary(pool_name):
    pool_name = pool_name.strip()
    data = get_details_cache()
    for row in data.get("pools", []):
        if not isinstance(row, dict):
            continue
        if row.get("pool") != pool_name:
            continue
        payload = {
            "Pool": row.get("pool"),
            "Status": row.get("status"),
            "Healthy": "yes" if row.get("healthy") else "no",
            "DataTopology": row.get("data_topology", ""),
            "UsableCapacityTiB": row.get("usable_tib", 0),
            "SizeTiB": round((float(row.get("size_bytes", 0)) / (1024 ** 4)), 2),
            "AllocatedTiB": round((float(row.get("allocated_bytes", 0)) / (1024 ** 4)), 2),
            "FreeTiB": round((float(row.get("free_bytes", 0)) / (1024 ** 4)), 2),
            "UsedPct": row.get("used_pct", 0),
            "ReadErrors": row.get("read_errors", 0),
            "WriteErrors": row.get("write_errors", 0),
            "ChecksumErrors": row.get("checksum_errors", 0),
        }
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        return

    print(json.dumps({"Pool": pool_name, "Status": "UNKNOWN"}, separators=(",", ":"), ensure_ascii=True))


def print_dataset_summary(dataset_name):
    dataset_name = dataset_name.strip()
    data = get_details_cache()
    for row in data.get("datasets", []):
        if not isinstance(row, dict):
            continue
        if row.get("dataset") != dataset_name and row.get("name") != dataset_name:
            continue
        payload = {
            "Dataset": row.get("name", ""),
            "Path": row.get("dataset", ""),
            "Pool": row.get("pool", ""),
            "Used": row.get("used_human", ""),
            "Available": row.get("available_human", ""),
            "UsedBytes": row.get("used_bytes", 0),
            "AvailableBytes": row.get("available_bytes", 0),
            "Encryption": row.get("encryption", "Unknown"),
        }
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        return

    print(json.dumps({"Dataset": dataset_name, "State": "MISSING"}, separators=(",", ":"), ensure_ascii=True))


def print_dataset_metric(dataset_name, metric_name):
    dataset_name = dataset_name.strip()
    metric_name = metric_name.strip().lower()
    data = get_details_cache()

    for row in data.get("datasets", []):
        if not isinstance(row, dict):
            continue
        if row.get("dataset") != dataset_name and row.get("name") != dataset_name:
            continue

        if metric_name == "used_bytes":
            print(int(row.get("used_bytes") or 0))
            return
        if metric_name == "available_bytes":
            print(int(row.get("available_bytes") or 0))
            return
        if metric_name == "used_tib":
            print(round(float(row.get("used_bytes") or 0) / (1024 ** 4), 4))
            return
        if metric_name == "available_tib":
            print(round(float(row.get("available_bytes") or 0) / (1024 ** 4), 4))
            return
        if metric_name == "encrypted":
            print(1 if str(row.get("encryption") or "").lower() == "encrypted" else 0)
            return
        if metric_name == "encrypted_flag":
            print(float(1 if str(row.get("encryption") or "").lower() == "encrypted" else 0))
            return

        print(-1)
        return

    print(-1)


def state_to_code(state_text):
    state = str(state_text or "").strip().upper()
    if state in {"SUCCESS", "FINISHED", "DONE", "HEALTHY", "PASSED", "ONLINE"}:
        return 0
    if state in {"RUNNING", "WAITING", "EXECUTING", "IN_PROGRESS"}:
        return 1
    if state in {"WARNING", "DEGRADED"}:
        return 2
    if state in {"FAILED", "ERROR", "ABORTED", "FAULTED", "OFFLINE", "UNAVAIL", "UNAVAILABLE"}:
        return 3
    return -1


def print_pool_metric(pool_name, metric_name):
    pool_name = pool_name.strip()
    metric_name = metric_name.strip().lower()
    data = get_details_cache()

    for row in data.get("pools", []):
        if not isinstance(row, dict):
            continue
        if row.get("pool") != pool_name:
            continue

        if metric_name == "used_pct":
            print(float(row.get("used_pct") or 0))
            return
        if metric_name == "allocated_tib":
            print(round(float(row.get("allocated_bytes") or 0) / (1024 ** 4), 4))
            return
        if metric_name == "free_tib":
            print(round(float(row.get("free_bytes") or 0) / (1024 ** 4), 4))
            return
        if metric_name == "read_errors":
            print(int(row.get("read_errors") or 0))
            return
        if metric_name == "write_errors":
            print(int(row.get("write_errors") or 0))
            return
        if metric_name == "checksum_errors":
            print(int(row.get("checksum_errors") or 0))
            return
        if metric_name == "healthy_flag":
            print(float(1 if bool(row.get("healthy")) else 0))
            return
        if metric_name == "status_code":
            print(float(state_to_code(row.get("status"))))
            return

        print(-1)
        return

    print(-1)


def print_smart_metric(drive, metric_name):
    drive = drive.strip()
    metric_name = metric_name.strip().lower()
    data = get_details_cache()

    for row in data.get("drives", []):
        if not isinstance(row, dict):
            continue
        if row.get("drive") != drive:
            continue

        if metric_name == "temp_c":
            print(float(row.get("temp_c") or -1))
            return
        if metric_name == "reallocated":
            print(int(row.get("reallocated") or 0))
            return
        if metric_name == "pending":
            print(int(row.get("pending") or 0))
            return
        if metric_name == "offline_uncorrectable":
            print(int(row.get("offline_uncorrectable") or 0))
            return
        if metric_name == "power_on_hours":
            print(int(row.get("power_on_hours") or 0))
            return
        if metric_name == "health_failed_flag":
            print(float(1 if str(row.get("health") or "").upper() == "FAILED" else 0))
            return

        print(-1)
        return

    print(-1)


def print_selftest_metric(drive, metric_name):
    drive = drive.strip()
    metric_name = metric_name.strip().lower()
    data = get_details_cache()

    for row in data.get("drives", []):
        if not isinstance(row, dict):
            continue
        if row.get("drive") != drive:
            continue

        now = time.time()

        if metric_name == "short_age_days":
            epoch = row.get("short_last_pass_epoch")
            if isinstance(epoch, (int, float)) and epoch > 0:
                print(round(max(0.0, (now - float(epoch)) / 86400.0), 3))
            else:
                print(-1)
            return

        if metric_name == "long_age_days":
            epoch = row.get("long_last_pass_epoch")
            if isinstance(epoch, (int, float)) and epoch > 0:
                print(round(max(0.0, (now - float(epoch)) / 86400.0), 3))
            else:
                print(-1)
            return

        print(-1)
        return

    print(-1)


def print_task_metric(task_type, task_id, metric_name):
    task_type = str(task_type).strip()
    task_id = str(task_id).strip()
    metric_name = metric_name.strip().lower()
    data = get_details_cache()

    for row in data.get("tasks", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("task_type")) != task_type or str(row.get("task_id")) != task_id:
            continue

        if metric_name == "enabled_flag":
            print(float(1 if bool(row.get("enabled")) else 0))
            return
        if metric_name == "state_code":
            print(float(state_to_code(row.get("state"))))
            return
        if metric_name == "last_run_age_hours":
            epoch = row.get("last_run_epoch")
            if isinstance(epoch, (int, float)) and epoch > 0:
                print(round(max(0.0, (time.time() - float(epoch)) / 3600.0), 3))
            else:
                print(-1)
            return

        print(-1)
        return

    print(-1)


def print_job_metric(index_text, metric_name):
    metric_name = metric_name.strip().lower()
    try:
        index = int(index_text)
    except ValueError:
        print(-1)
        return

    data = get_details_cache()
    jobs = [row for row in data.get("jobs", []) if isinstance(row, dict)]
    for row in jobs:
        if int(row.get("index", -1)) != index:
            continue

        if metric_name == "state_code":
            print(float(state_to_code(row.get("state"))))
            return
        if metric_name == "duration_sec":
            print(float(row.get("duration_sec") or 0))
            return
        if metric_name == "age_hours":
            epoch = row.get("started_epoch")
            if isinstance(epoch, (int, float)) and epoch > 0:
                print(round(max(0.0, (time.time() - float(epoch)) / 3600.0), 3))
            else:
                print(-1)
            return

        print(-1)
        return

    print(-1)


def print_task_summary(task_type, task_id):
    data = get_details_cache()
    for row in data.get("tasks", []):
        if not isinstance(row, dict):
            continue
        if row.get("task_type") == task_type and str(row.get("task_id")) == str(task_id):
            payload = {
                "TaskType": row.get("task_type"),
                "TaskId": row.get("task_id"),
                "Name": row.get("name"),
                "Enabled": "yes" if row.get("enabled") else "no",
                "Schedule": row.get("schedule", ""),
                "State": row.get("state", "UNKNOWN"),
                "LastRun": row.get("last_run", "None"),
            }
            print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            return

    print(json.dumps({"TaskType": task_type, "TaskId": str(task_id), "State": "MISSING"}, separators=(",", ":"), ensure_ascii=True))


def print_job_summary(index_text):
    try:
        index = int(index_text)
    except ValueError:
        print(json.dumps({"Index": index_text, "State": "INVALID"}, separators=(",", ":"), ensure_ascii=True))
        return

    data = get_details_cache()
    jobs = [row for row in data.get("jobs", []) if isinstance(row, dict)]
    for row in jobs:
        if int(row.get("index", -1)) == index:
            payload = {
                "Index": index,
                "JobId": row.get("job_id", 0),
                "Method": row.get("method", ""),
                "State": row.get("state", ""),
                "Started": row.get("started", ""),
                "Finished": row.get("finished", ""),
                "DurationSec": row.get("duration_sec", 0),
                "Error": row.get("error", ""),
                "Result": row.get("result", ""),
            }
            print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            return

    print(json.dumps({"Index": index, "State": "EMPTY"}, separators=(",", ":"), ensure_ascii=True))


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    command = sys.argv[1]
    hba = None

    if command in {"hba_temp", "hba_telemetry", "hba_method", "hba_error"}:
        hba = probe_hba_temp()

    if command == "hba_temp":
        print(hba["temp"])
        return
    if command == "hba_telemetry":
        print("1" if hba["ok"] else "0")
        return
    if command == "hba_method":
        print(hba["method"])
        return
    if command == "hba_error":
        print(hba["error"])
        return
    if command == "refresh_cache":
        data = refresh_cache_sync()
        print(json.dumps(data, separators=(",", ":")))
        return
    if command == "refresh_temp_cache":
        data = refresh_temp_cache_sync()
        print(json.dumps(data, separators=(",", ":"), ensure_ascii=True))
        return
    if command == "refresh_details_cache":
        data = refresh_details_cache_sync()
        print(json.dumps(data, separators=(",", ":"), ensure_ascii=True))
        return
    if command == "summary_json":
        print(json.dumps(get_summary_cached(), separators=(",", ":")))
        return
    if command == "summary_metric" and len(sys.argv) == 3:
        print_summary_metric(sys.argv[2])
        return
    if command == "drives_json":
        print_details_slice("drives")
        return
    if command == "pools_json":
        print_details_slice("pools")
        return
    if command == "datasets_json":
        print_details_slice("datasets")
        return
    if command == "tasks_json":
        print_details_slice("tasks")
        return
    if command == "jobs_json":
        print_details_slice("jobs")
        return
    if command == "drive_temp" and len(sys.argv) == 3:
        print_drive_temp(sys.argv[2])
        return
    if command == "smart_selftest_summary" and len(sys.argv) == 3:
        print_drive_selftest_summary(sys.argv[2])
        return
    if command == "smart_health_summary" and len(sys.argv) == 3:
        print_drive_health_summary(sys.argv[2])
        return
    if command == "pool_summary" and len(sys.argv) == 3:
        print_pool_summary(sys.argv[2])
        return
    if command == "pool_metric" and len(sys.argv) == 4:
        print_pool_metric(sys.argv[2], sys.argv[3])
        return
    if command == "dataset_summary" and len(sys.argv) == 3:
        print_dataset_summary(sys.argv[2])
        return
    if command == "dataset_metric" and len(sys.argv) == 4:
        print_dataset_metric(sys.argv[2], sys.argv[3])
        return
    if command == "smart_metric" and len(sys.argv) == 4:
        print_smart_metric(sys.argv[2], sys.argv[3])
        return
    if command == "selftest_metric" and len(sys.argv) == 4:
        print_selftest_metric(sys.argv[2], sys.argv[3])
        return
    if command == "task_summary" and len(sys.argv) == 4:
        print_task_summary(sys.argv[2], sys.argv[3])
        return
    if command == "task_metric" and len(sys.argv) == 5:
        print_task_metric(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    if command == "job_summary" and len(sys.argv) == 3:
        print_job_summary(sys.argv[2])
        return
    if command == "job_metric" and len(sys.argv) == 4:
        print_job_metric(sys.argv[2], sys.argv[3])
        return

    sys.exit(1)


if __name__ == "__main__":
    main()
PY

chmod 755 /usr/local/bin/zabbix-truenas-scale.py

cat >/etc/sudoers.d/zabbix-qm-guest-exec <<'EOF'
Defaults:zabbix !requiretty
Defaults:zabbix !authenticate
zabbix ALL=(root) NOPASSWD: /usr/sbin/qm guest exec *
EOF

chmod 440 /etc/sudoers.d/zabbix-qm-guest-exec
visudo -c >/dev/null

cat >/etc/zabbix/zabbix_agent2.d/truenas-scale.conf <<'EOF'
UserParameter=truenas.hba.temp,/usr/local/bin/zabbix-truenas-scale.py hba_temp
UserParameter=truenas.hba.telemetry,/usr/local/bin/zabbix-truenas-scale.py hba_telemetry
UserParameter=truenas.hba.method,/usr/local/bin/zabbix-truenas-scale.py hba_method
UserParameter=truenas.hba.error,/usr/local/bin/zabbix-truenas-scale.py hba_error
UserParameter=truenas.summary.json,/usr/local/bin/zabbix-truenas-scale.py summary_json
UserParameter=truenas.summary.metric[*],/usr/local/bin/zabbix-truenas-scale.py summary_metric "$1"
UserParameter=truenas.drives.json,/usr/local/bin/zabbix-truenas-scale.py drives_json
UserParameter=truenas.pools.json,/usr/local/bin/zabbix-truenas-scale.py pools_json
UserParameter=truenas.datasets.json,/usr/local/bin/zabbix-truenas-scale.py datasets_json
UserParameter=truenas.tasks.json,/usr/local/bin/zabbix-truenas-scale.py tasks_json
UserParameter=truenas.jobs.json,/usr/local/bin/zabbix-truenas-scale.py jobs_json
UserParameter=truenas.drive.temp[*],/usr/local/bin/zabbix-truenas-scale.py drive_temp "$1"
UserParameter=truenas.smart.selftest.summary[*],/usr/local/bin/zabbix-truenas-scale.py smart_selftest_summary "$1"
UserParameter=truenas.smart.health.summary[*],/usr/local/bin/zabbix-truenas-scale.py smart_health_summary "$1"
UserParameter=truenas.smart.metric[*],/usr/local/bin/zabbix-truenas-scale.py smart_metric "$1" "$2"
UserParameter=truenas.selftest.metric[*],/usr/local/bin/zabbix-truenas-scale.py selftest_metric "$1" "$2"
UserParameter=truenas.pool.summary[*],/usr/local/bin/zabbix-truenas-scale.py pool_summary "$1"
UserParameter=truenas.pool.metric[*],/usr/local/bin/zabbix-truenas-scale.py pool_metric "$1" "$2"
UserParameter=truenas.dataset.summary[*],/usr/local/bin/zabbix-truenas-scale.py dataset_summary "$1"
UserParameter=truenas.dataset.metric[*],/usr/local/bin/zabbix-truenas-scale.py dataset_metric "$1" "$2"
UserParameter=truenas.task.summary[*],/usr/local/bin/zabbix-truenas-scale.py task_summary "$1" "$2"
UserParameter=truenas.task.metric[*],/usr/local/bin/zabbix-truenas-scale.py task_metric "$1" "$2" "$3"
UserParameter=truenas.job.summary[*],/usr/local/bin/zabbix-truenas-scale.py job_summary "$1"
UserParameter=truenas.job.metric[*],/usr/local/bin/zabbix-truenas-scale.py job_metric "$1" "$2"
EOF

systemctl restart zabbix-agent2

echo "== TrueNAS SCALE checks =="
sudo -u zabbix zabbix_agent2 -t truenas.hba.temp || true
sudo -u zabbix zabbix_agent2 -t truenas.hba.telemetry || true
sudo -u zabbix zabbix_agent2 -t truenas.hba.method || true
sudo -u zabbix zabbix_agent2 -t truenas.summary.json || true
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[jobs_failed_24h]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[scrub_running]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[pool_usage_pct_max]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[drive_temp_max_c]' || true
sudo -u zabbix zabbix_agent2 -t truenas.drives.json || true
sudo -u zabbix zabbix_agent2 -t truenas.pools.json || true
sudo -u zabbix zabbix_agent2 -t truenas.datasets.json || true
sudo -u zabbix zabbix_agent2 -t 'truenas.drive.temp[sdb]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.smart.selftest.summary[sdb]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.selftest.metric[sdb,short_age_days]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.smart.metric[sdb,pending]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.pool.summary[Vault]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.pool.metric[Vault,used_pct]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.dataset.summary[Vault/data]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.dataset.metric[Vault/data,used_bytes]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.dataset.metric[Vault/data,used_tib]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.task.metric[snapshot,1,state_code]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.job.metric[0,state_code]' || true
sudo -u zabbix zabbix_agent2 -t 'truenas.job.summary[0]' || true

echo
echo "Next: configure Zabbix items/triggers from docs/zabbix/zabbix-truenas-scale-monitoring.md"
