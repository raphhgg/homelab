# NUT UPS Monitoring in Zabbix

This adds CyberPower UPS metrics (via NUT) to the Proxmox node host in Zabbix.

## 1. Run on the Proxmox node

Copy `scripts/install-zabbix-nut-ups.sh` to the node and run it as root.

It will:
- install `/usr/local/bin/zabbix-nut-ups.py`
- register Zabbix agent user parameters (`nut.ups.discovery`, `nut.ups.value`)

Quick checks on the node:

```bash
upsc cyberpower
sudo -u zabbix zabbix_agent2 -t 'nut.ups.discovery[cyberpower]'
sudo -u zabbix zabbix_agent2 -t 'nut.ups.value[cyberpower,battery.charge]'
sudo -u zabbix zabbix_agent2 -t 'nut.ups.value[cyberpower,ups.status]'
```

## 2. Zabbix configuration on host `pve`

### Discovery rule (numeric metrics)

- Name: `NUT UPS discovery`
- Type: `Zabbix agent`
- Key: `nut.ups.discovery[cyberpower]`
- Update interval: `1h`
- LLD filter: `{#UPS_METRIC}` matches `^(battery\.charge|battery\.runtime|battery\.voltage|input\.voltage|output\.voltage|ups\.load)$`

One item prototype:

- Name: `UPS {#UPS_NAME} {#UPS_METRIC}`
- Type: `Zabbix agent`
- Key: `nut.ups.value[{#UPS_NAME},{#UPS_METRIC}]`
- Type of information: `Numeric (float)`
- Update interval: `1m`
- Preprocessing: `Discard unchanged with heartbeat = 10m`

### Standalone items (string metrics)

String metrics (`ups.status`, `ups.test.result`) use the same `nut.ups.value` key but are created as standalone items since Zabbix does not allow two item prototypes with the same key.

| Item name | Key | Type | Interval |
|-----------|-----|------|----------|
| `UPS cyberpower ups.status` | `nut.ups.value[cyberpower,ups.status]` | Character | 30s |
| `UPS cyberpower ups.test.result` | `nut.ups.value[cyberpower,ups.test.result]` | Character | 5m |

## 3. Triggers

### Trigger prototypes (on the discovery rule)

| Trigger name | Severity | Expression |
|---|---|---|
| `UPS {#UPS_NAME} battery charge below 50%` | Warning | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])<50` |
| `UPS {#UPS_NAME} battery charge below 20%` | High | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])<20` |
| `UPS {#UPS_NAME} runtime below 10 minutes` | Warning | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])<600` |
| `UPS {#UPS_NAME} runtime below 5 minutes` | High | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])<300` |
| `UPS {#UPS_NAME} load above 80%` | Warning | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])>80` |
| `UPS {#UPS_NAME} load above 90%` | High | `last(/pve/nut.ups.value[{#UPS_NAME},{#UPS_METRIC}])>90` |
| `UPS {#UPS_NAME} input voltage out of range` | Warning | `last(...)<210 or last(...)>250` |
| `UPS cyberpower no data for 15 minutes` | High | `nodata(/pve/nut.ups.value[cyberpower,battery.charge],15m)=1` |

### Standalone triggers

| Trigger name | Severity | Expression |
|---|---|---|
| `UPS cyberpower is on battery` | High | `find(/pve/nut.ups.value[cyberpower,ups.status],,"like","OL")=0` |
| `UPS cyberpower self-test failed` | High | value is not "Done and passed", "No test initiated", or "In progress" |

## 4. Grafana mapping

The `PVE Nodes` dashboard has a UPS row prepared for these item names:

- `UPS Status` matches `UPS.*ups\.status`
- `Battery Charge` matches `UPS.*battery\.charge`
- `Battery Runtime` matches `UPS.*battery\.runtime`
- `UPS Load` matches `UPS.*ups\.load`
- `Input Voltage` matches `UPS.*input\.voltage`
- `Output Voltage` matches `UPS.*output\.voltage`
- `UPS History` matches multiple UPS metrics over time
- `UPS Power Events` state timeline matches `UPS.*ups\.status` (shows on-battery events over time)
- `Self-Test Result` matches `UPS.*ups\.test\.result`

The `Hardware Alerts` panel also counts UPS-related triggers.

Once items are collecting data in Zabbix, those panels should populate automatically.
