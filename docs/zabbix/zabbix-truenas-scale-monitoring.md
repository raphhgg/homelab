# TrueNAS SCALE monitoring (HBA temp + tasks) with Zabbix

This runbook adds TrueNAS SCALE observability to Zabbix using a Proxmox-side collector.

It covers:

- HBA controller temperature export (with standalone `storcli64` fallback)
- TrueNAS software task health (`midclt` jobs/scrub/snapshots/replication/cloudsync/rsync)
- ZFS pool health/capacity/error aggregation
- Drive temperature aggregation (`sensors` drivetemp)
- Trigger design and Telegram routing hints

## Why this approach

- TrueNAS SCALE is an appliance OS, so we avoid persistent package customization on the host.
- We query TrueNAS from Proxmox using `qm guest exec`, then expose results via `zabbix_agent2` user parameters.
- HBA temp uses best-effort command probing:
  - `storcli /c0 show temperature`
  - `/mnt/Vault/monitoring/bin/storcli64 /c0 show temperature`
  - `sas3ircu 0 DISPLAY` (last-resort parse)

## 1) Prepare standalone `storcli64` in TrueNAS (recommended)

On `truenas-vm` shell:

```bash
install -d -m 755 /mnt/Vault/monitoring/bin
# Copy your downloaded storcli64 binary there
chmod 755 /mnt/Vault/monitoring/bin/storcli64
```

Notes:

- Path is on pool storage, so it survives OS updates/reboots.
- Default collector path is `/mnt/Vault/monitoring/bin/storcli64`.

## 2) Install collector on Proxmox node (`pve`)

Copy and run:

```bash
sudo ./scripts/install-zabbix-truenas-scale-monitoring.sh
```

The installer creates:

- `/usr/local/bin/zabbix-truenas-scale.py`
- `/etc/zabbix/zabbix_agent2.d/truenas-scale.conf`
- `/etc/sudoers.d/zabbix-qm-guest-exec` (allows `zabbix` to execute `qm guest exec` via sudo)

Collector behavior:

- Expensive TrueNAS summary calls are cached in `/tmp/zabbix-truenas-scale-summary.json`.
- `truenas.summary.json` and `truenas.summary.metric[*]` read from cache to stay under Zabbix timeout limits.

Defaults:

- `TRUENAS_VM_ID=202`
- `TRUENAS_STORCLI64_PATH=/mnt/Vault/monitoring/bin/storcli64`

Override per command if needed:

```bash
TRUENAS_VM_ID=202 TRUENAS_STORCLI64_PATH=/mnt/Vault/monitoring/bin/storcli64 \
  /usr/local/bin/zabbix-truenas-scale.py summary_json
```

## 3) Exposed Zabbix keys (on host `pve`)

- `truenas.hba.temp` (numeric, `-1` when unavailable)
- `truenas.hba.telemetry` (`1`/`0`)
- `truenas.hba.method` (text)
- `truenas.hba.error` (text)
- `truenas.summary.json` (JSON payload)
- `truenas.summary.metric[<name>]` (single metric from summary)
- `truenas.drive.temp[<drive>]` (per-drive temperature, e.g. `sdb`)
- `truenas.smart.selftest.summary[<drive>]` (JSON row for Short/Long test recency)
- `truenas.smart.health.summary[<drive>]` (JSON row for SMART health attributes)
- `truenas.pool.summary[<pool>]` (JSON row for pool status/capacity/errors)
- `truenas.task.summary[<type>,<id>]` (JSON row for task schedule/state)
- `truenas.job.summary[<index>]` (JSON row for recent jobs, `0` = most recent)
- `truenas.drives.json`, `truenas.pools.json`, `truenas.tasks.json`, `truenas.jobs.json` (detailed observability payloads)

Suggested `truenas.summary.metric` names:

- `jobs_failed_24h`
- `jobs_total_24h`
- `jobs_success_24h`
- `jobs_total_7d`
- `jobs_success_7d`
- `jobs_failed_7d`
- `jobs_running`
- `alerts_active`
- `alerts_critical`
- `pool_count`
- `pool_unhealthy_count`
- `pool_usage_pct_max`
- `pool_usage_pct_avg`
- `pool_allocated_bytes_total`
- `pool_free_bytes_total`
- `pool_read_errors_total`
- `pool_write_errors_total`
- `pool_checksum_errors_total`
- `drive_temp_count`
- `drive_temp_max_c`
- `drive_temp_avg_c`
- `drive_temp_over_45_count`
- `drive_temp_over_50_count`
- `drives_monitored_count`
- `drives_smart_failed_count`
- `drives_reallocated_total`
- `drives_pending_total`
- `drives_offline_uncorrectable_total`
- `drives_without_short_test_count`
- `drives_without_long_test_count`
- `scrub_tasks_enabled`
- `scrub_running`
- `resilver_running`
- `snapshot_tasks_failed`
- `replication_tasks_failed`
- `cloudsync_tasks_failed`
- `rsync_tasks_failed`
- `error_count`

## 4) Zabbix item setup

Create items on existing Proxmox node host (`pve`):

### Direct items

- `TrueNAS HBA temperature` -> key `truenas.hba.temp` (Numeric float, units `C`)
- `TrueNAS HBA telemetry` -> key `truenas.hba.telemetry` (Numeric unsigned)
- `TrueNAS HBA method` -> key `truenas.hba.method` (Text)
- `TrueNAS HBA error` -> key `truenas.hba.error` (Text)
- `TrueNAS summary JSON` -> key `truenas.summary.json` (Text)

### Dependent items from summary JSON (recommended)

Master item: `truenas.summary.json`

Dependent item examples using JSONPath preprocessing:

- `TrueNAS jobs failed 24h` -> `$.jobs_failed_24h`
- `TrueNAS alerts active` -> `$.alerts_active`
- `TrueNAS alerts critical` -> `$.alerts_critical`
- `TrueNAS scrub running` -> `$.scrub_running`
- `TrueNAS resilver running` -> `$.resilver_running`
- `TrueNAS unhealthy pools` -> `$.pool_unhealthy_count`
- `TrueNAS pool usage max` -> `$.pool_usage_pct_max`
- `TrueNAS pool allocated bytes` -> `$.pool_allocated_bytes_total`
- `TrueNAS pool free bytes` -> `$.pool_free_bytes_total`
- `TrueNAS drive temp max` -> `$.drive_temp_max_c`
- `TrueNAS drive temp avg` -> `$.drive_temp_avg_c`
- `TrueNAS snapshot failures` -> `$.snapshot_tasks_failed`
- `TrueNAS replication failures` -> `$.replication_tasks_failed`
- `TrueNAS cloudsync failures` -> `$.cloudsync_tasks_failed`
- `TrueNAS rsync failures` -> `$.rsync_tasks_failed`
- `TrueNAS collector errors` -> `$.error_count`

## 5) Trigger baseline

Use these starting expressions:

- `TrueNAS HBA sensor telemetry unavailable`
  - `last(/pve/truenas.hba.telemetry)=0`
  - Severity: `Warning`

- `TrueNAS HBA sensor temperature high`
  - `min(/pve/truenas.hba.temp,10m)>85 and last(/pve/truenas.hba.telemetry)=1`
  - Severity: `Average`

- `TrueNAS HBA sensor temperature critical`
  - `min(/pve/truenas.hba.temp,5m)>92 and last(/pve/truenas.hba.telemetry)=1`
  - Severity: `High`

- `TrueNAS jobs failing`
  - `last(/pve/truenas.summary.metric[jobs_failed_24h])>0`
  - Severity: `Warning`

- `TrueNAS task failures`
  - `last(/pve/truenas.summary.metric[snapshot_tasks_failed])>0`
  - `or last(/pve/truenas.summary.metric[replication_tasks_failed])>0`
  - `or last(/pve/truenas.summary.metric[cloudsync_tasks_failed])>0`
  - `or last(/pve/truenas.summary.metric[rsync_tasks_failed])>0`
  - Severity: `Warning`

- `TrueNAS pool health degraded`
  - `last(/pve/truenas.summary.metric[pool_unhealthy_count])>0`
  - Severity: `High`

- `TrueNAS pool usage high`
  - `min(/pve/truenas.summary.metric[pool_usage_pct_max],10m)>80`
  - Severity: `Average`

- `TrueNAS drive temperature high`
  - `min(/pve/truenas.summary.metric[drive_temp_max_c],10m)>50`
  - Severity: `Average`

- `TrueNAS SMART pending sectors detected`
  - `last(/pve/truenas.summary.metric[drives_pending_total])>0`
  - Severity: `High`

- `TrueNAS SMART offline uncorrectable sectors detected`
  - `last(/pve/truenas.summary.metric[drives_offline_uncorrectable_total])>0`
  - Severity: `High`

- `TrueNAS SMART health failed`
  - `last(/pve/truenas.summary.metric[drives_smart_failed_count])>0`
  - Severity: `High`

## 6) Telegram routing alignment

To reuse current action matrix in `docs/zabbix-alerting-config.md`:

- Include `sensor` and `temperature` in HBA trigger names (covered by Hardware route and excluded from Infrastructure route).
- Use clear `TrueNAS:` prefix for task triggers so they are easy to target later.

Current action routing:

- Hardware channel: `TG: Hardware alerts` catches `TrueNAS: HBA sensor ...` triggers.
- Backup channel: `TG: TrueNAS task alerts` catches TrueNAS job/task and pool health/capacity triggers.
- Infrastructure channel explicitly excludes `TrueNAS:` to avoid duplicate notifications.

Dashboard note:

- The `TrueNAS Storage` dashboard includes dedicated tables for per-drive SMART tests, per-drive SMART health, per-pool summaries, task schedules/last run, and recent job history.

Example trigger names:

- `TrueNAS: HBA sensor temperature is high`
- `TrueNAS: HBA sensor telemetry unavailable`
- `TrueNAS: Snapshot task failures detected`

## 7) Quick verification

On `pve`:

```bash
sudo -u zabbix zabbix_agent2 -t truenas.hba.temp
sudo -u zabbix zabbix_agent2 -t truenas.hba.telemetry
sudo -u zabbix zabbix_agent2 -t truenas.hba.method
sudo -u zabbix zabbix_agent2 -t truenas.summary.json
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[jobs_failed_24h]'
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[pool_usage_pct_max]'
sudo -u zabbix zabbix_agent2 -t 'truenas.summary.metric[drive_temp_max_c]'
```

If `truenas.hba.telemetry=0`:

- verify `storcli64` exists and is executable at `/mnt/Vault/monitoring/bin/storcli64`
- inspect `truenas.hba.error` value for parse/command failure details
