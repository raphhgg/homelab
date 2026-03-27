# Zabbix Telegram Alerting Configuration

Last updated: 2026-03-26

This document summarizes the current Telegram alerting setup in Zabbix.

## Where this is configured in Zabbix

- `Alerts -> Media types -> Telegram` (media type ID `97`)
  - Webhook script
  - Message templates (problem/recovery/update)
  - URL buttons (`Open Event`, `Host Problems`)
- `Alerts -> Actions -> Trigger actions`
  - Alert routing logic
  - Severity filtering
  - Delays and operations (problem/recovery/update)

## Telegram Action Matrix

## Channel View (What You Receive vs Silenced)

### Infrastructure (`tg-infrastructure`, topic `:3`)
- Receives:
  - General infra alerts from `Linux servers`, `Zabbix servers`, `Proxmox Nodes` (severity `>= Warning`), excluding specialized/noisy patterns.
  - Delayed performance alerts (`Load average is too high`, `Speedtest:`) via `TG: Infrastructure delayed performance` after 10 minutes.
  - Internal monitoring health for `debian-vm` not-supported items/discovery (`TG: Monitoring health`).
- Silenced in this channel:
  - `High bandwidth usage` (currently suppressed from Telegram)
  - Infrastructure update chatter (updates disabled)

### Docker (`tg-docker`, topic `:5`)
- Receives:
  - Docker/container alerts on `debian-vm` with severity `>= Warning`.
  - One problem message when a container issue starts (for example `stopped`/`unhealthy`).
  - One recovery message when that container comes back (`running again`/`healthy again`).
- Silenced in this channel:
  - Update/escalation chatter (`update_operations` disabled)

### Network (`tg-network`, topic `:6`)
- Receives:
  - Alerts from host groups `Network/UniFi`, `Network/DNS`, `Cloud/Cloudflare`, severity `>= Warning`.
  - `UniFi:` alerts from `debian-vm` via dedicated `TG: UniFi alerts` action.
- Silenced in this channel:
  - Trigger names containing `has been restarted` (explicitly excluded to reduce firmware/reboot noise).

### Hardware (`tg-hardware`, topic `:4`)
- Receives:
  - Alerts containing one of `Intel SATA`, `Nvidia`, `NVMe`, `sensor`, `SMART`, `temperature`, severity `>= Warning`.
- Silenced in this channel:
  - None explicitly (keyword route only)

### Backups (`tg-backups`, topic `:7`)
- Receives:
  - Alerts for `pbs-vm` in `Proxmox-API` scope, severity `>= Warning`.
- Silenced in this channel:
  - None explicitly (scope route only)

### UPS (`tg-ups`, topic `:8`)
- Receives:
  - Alerts containing `UPS`, severity `>= Warning`.
- Silenced in this channel:
  - None explicitly (keyword route only)

### Global silencing rules (all channels)
- Skip update messages containing `Escalation canceled:`.
- Skip orphan recoveries when no prior Telegram problem message exists for the same thread (prevents delayed-alert recovery spam).
- For P2 trigger problem/recovery messages, hide `Event ID` in body (not a silence rule, but noise reduction).

### TG: Infrastructure alerts (action `7`)
- Destination user: `tg-infrastructure` (user `5`)
- Scope:
  - Host groups: `Linux servers`, `Zabbix servers`, `Proxmox Nodes`
  - Severity `>= Warning` (`>=2`)
- Excludes (no Telegram from this action):
  - `Container`, `Docker`, `SMART`, `UPS`, `Nvidia`, `sensor`, `Intel SATA`, `TrueNAS:`
  - `Load average is too high`
  - `Speedtest:`
  - `High bandwidth usage`
- Operations:
  - Problem: immediate
  - Recovery: immediate
  - Update: disabled

### TG: Infrastructure delayed performance (action `15`)
- Destination user: `tg-infrastructure` (user `5`)
- Scope:
  - Host groups: `Linux servers`, `Zabbix servers`, `Proxmox Nodes`
  - Severity `>= Warning` (`>=2`)
  - Trigger name contains either:
    - `Load average is too high`
    - `Speedtest:`
- Operations:
  - Problem: delayed by 10 minutes (step 2, action `esc_period=10m`)
  - Recovery: enabled
  - Update: disabled

### TG: Docker alerts (action `8`)
- Destination user: `tg-docker` (user `7`)
- Scope:
  - Trigger name contains `Container` or `Docker`
  - Host `debian-vm` (`10778`)
  - Severity `>= Warning`
- Operations:
  - Problem: enabled (single immediate send, step `1` only)
  - Recovery: enabled (single immediate send)
  - Update: disabled

### TG: Network alerts (action `9`)
- Destination user: `tg-network` (user `8`)
- Scope:
  - Host groups: `Network/UniFi`, `Network/DNS`, `Cloud/Cloudflare`
  - Severity `>= Warning`
  - Excludes trigger names containing `has been restarted`
- Operations:
  - Problem + Recovery + Update enabled

### TG: Backup alerts (action `10`)
- Destination user: `tg-backups` (user `9`)
- Scope:
  - Host `pbs-vm` (`10785`), host group `Proxmox-API`, severity `>= Warning`
- Operations:
  - Problem + Recovery + Update enabled

### TG: TrueNAS task alerts (action `16`)
- Destination user: `tg-backups` (user `9`)
- Scope:
  - Host `pve` (`10777`)
  - Severity `>= Warning`
  - Trigger name contains either:
    - `TrueNAS: Jobs failing`
    - `TrueNAS: Scheduled task failures`
    - `TrueNAS: Pool health`
    - `TrueNAS: Pool usage`
    - `TrueNAS: Pool checksum/read/write errors`
- Operations:
  - Problem + Recovery enabled
  - Update disabled

### TG: Hardware alerts (action `11`)
- Destination user: `tg-hardware` (user `6`)
- Scope:
  - Trigger contains one of: `Intel SATA`, `Nvidia`, `NVMe`, `sensor`, `SMART`, `temperature`
  - Severity `>= Warning`
- Operations:
  - Problem + Recovery + Update enabled
- Includes TrueNAS hardware paths such as:
  - `TrueNAS: HBA sensor ...`
  - `TrueNAS: SMART ...`
  - `TrueNAS: Drive temperature ...`

### TG: UPS alerts (action `12`)
- Destination user: `tg-ups` (user `10`)
- Scope:
  - Trigger contains `UPS`
  - Severity `>= Warning`
- Operations:
  - Problem + Recovery + Update enabled

### TG: Monitoring health (debian-vm) (action `13`)
- Destination user: `tg-infrastructure` (user `5`)
- Event source: Internal events
- Scope:
  - Host `debian-vm` (`10778`)
  - Not supported items/discovery rules
- Operations:
  - Problem + Recovery enabled
  - Update disabled

### TG: UniFi alerts (action `14`)
- Destination user: `tg-network` (user `8`)
- Scope:
  - Trigger contains `UniFi:`
  - Host `debian-vm` (`10778`)
  - Severity `>= Warning`
- Operations:
  - Problem + Recovery enabled
  - Update disabled

## Message Formatting Rules (media type `97`)

- Prefix cleanup:
  - Removes `Network Generic Device:`
  - Removes `Linux:`
- Docker cleanup:
  - Normalizes container names (`/qbit-main` -> `qbit-main`)
  - Uses compact wording (`Docker: <container> stopped [host]`, `running again`, `unhealthy`, `healthy again`)
  - Keeps one detail line when available (`Exit code: N` or health state)
  - Removes Docker footer noise (`Resolved after`, `Event ID`, duplicate timestamp line)
  - Strips ANSI/control characters from incoming text to prevent junk sequences in Telegram
- Recovery wording:
  - Rewrites `Unavailable by ICMP ping` -> `Reachable by ICMP ping`
- Drive name normalization:
  - Uses aliases:
    - `nvme0` -> `Intel U.2 #1 (nvme0)`
    - `nvme1` -> `WD Black (nvme1)`
    - `nvme2` -> `Intel U.2 #2 (nvme2)`
    - `sde`/`sde sat` -> `Intel SSD #1 (sde)`
    - `sdf`/`sdf sat` -> `Intel SSD #2 (sdf)`
  - Collapses duplicate drive labels so only bracket alias is shown.
- Event ID visibility:
  - Hidden for P2 trigger problem/recovery messages
  - Kept for higher-severity/debug-style paths
- Update noise suppression:
  - Skips `Escalation canceled:` update chatter
  - Skips recovery notifications if no prior problem message was sent to Telegram (prevents orphan delayed recoveries)
- URL buttons:
  - `Open Event`
  - `Host Problems`

## Current noise reduction choices

- Infrastructure update messages disabled (removes duplicate ack/close messages from Grafana close flow).
- High bandwidth interface alerts removed from infrastructure Telegram route.
- Load and Speedtest moved to delayed performance route (10-minute delay before sending problem).
- PBS disk latency is two-tiered on `pbs-vm` (`sda`):
  - Warning trigger: `40-80 ms` over `30m` (severity Warning)
  - Critical trigger: `>80 ms` over `30m` (severity High)
  - Default Linux template `sda` await warning trigger is muted for this host via context macros:
    - `{$VFS.DEV.READ.AWAIT.WARN:"sda"}=999`
    - `{$VFS.DEV.WRITE.AWAIT.WARN:"sda"}=999`
- TrueNAS HBA temperature thresholds on `pve` collector:
  - Warning trigger: `>85C` over `10m`
  - Critical trigger: `>92C` over `5m`

## Quick visual checks in Zabbix

- Trigger action list: `Alerts -> Actions -> Trigger actions`
  - Sort/filter by name `TG:`
- Telegram media type and templates: `Alerts -> Media types -> Telegram`
- Problem audit: `Monitoring -> Problems`
  - Filter by host and recent 24h
