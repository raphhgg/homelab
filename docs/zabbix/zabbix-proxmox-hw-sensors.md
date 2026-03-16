# Proxmox Hardware Sensors for Zabbix

This adds CPU/package temperatures and fan RPM to the Proxmox node host in Zabbix.

## 1. Run on the Proxmox node

Copy `scripts/install-proxmox-hw-sensors.sh` to the node and run it as root.

It will:
- install `lm-sensors`
- enable kernel sensor detection
- install `/usr/local/bin/zabbix-hw-sensors.py`
- register Zabbix agent user parameters

Quick checks on the node:

```bash
sensors
sudo -u zabbix zabbix_agent2 -t hw.sensor.discovery
```

If `sensors -j` prints warnings but still returns JSON, make sure you are using the latest `scripts/install-proxmox-hw-sensors.sh` from this repo. The current version tolerates non-zero `sensors` exit codes and still parses the JSON payload.

## 2. Add discovery in Zabbix on host `pve`

Create one discovery rule on the Proxmox node host:

- Name: `Hardware sensors discovery`
- Type: `Zabbix agent`
- Key: `hw.sensor.discovery`
- Update interval: `1m`

Add two item prototypes.

Temperature item prototype:

- Name: `Hardware sensor {#SENSOR_NAME} temperature`
- Type: `Zabbix agent`
- Key: `hw.sensor.value[{#SENSOR_ID}]`
- Type of information: `Numeric (float)`
- Units: `C`
- Preprocessing: optional `Discard unchanged with heartbeat = 1h`
- LLD filter: `{#SENSOR_TYPE}` matches `^temperature$`

Fan item prototype:

- Name: `Hardware sensor {#SENSOR_NAME} fan speed`
- Type: `Zabbix agent`
- Key: `hw.sensor.value[{#SENSOR_ID}]`
- Type of information: `Numeric (float)`
- Units: `rpm`
- Preprocessing: optional `Discard unchanged with heartbeat = 1h`
- LLD filter: `{#SENSOR_TYPE}` matches `^fan$`

Optional trigger prototypes:

- `Hardware sensor {#SENSOR_NAME} temperature is high` when `last()>80`
- `Hardware sensor {#SENSOR_NAME} fan speed is critically low` when `last()<300`

The fan trigger threshold depends on the hardware. Some devices may legitimately report `0` for unused headers.

## 3. Grafana mapping

The `PVE Nodes` dashboard is already prepared for these item names:

- `System Temperatures` matches `Hardware sensor .* temperature`
- `Fan RPM` matches `Hardware sensor .* fan speed`

Once discovery starts creating items in Zabbix, those two panels should populate automatically.
