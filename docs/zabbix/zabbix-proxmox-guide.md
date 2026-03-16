# Zabbix + Proxmox Monitoring Guide

This guide documents the current setup and the repeatable process to extend it.

## Current status (single node)

- `Proxmox VE by HTTP` template is linked on host `Proxmox-API` and collecting cluster/node/VM/LXC/storage data.
- Proxmox node host (for example `pve`) has:
  - `Linux by Zabbix agent`
  - `SMART by Zabbix agent 2`
- SMART plugin works with:
  - `Plugins.Smart.Path=/usr/sbin/smartctl`
  - sudoers rule for `zabbix` to run `smartctl` without password.

## Where to look in Zabbix

- `Monitoring -> Problems`: active issues requiring action.
- `Monitoring -> Latest data`: raw values and troubleshooting.
- `Data collection -> Hosts -> Proxmox-API`: API/template-level status.
- `Data collection -> Hosts -> <node> -> Discovery rules`: SMART/Linux discovery health.

## Add a new Proxmox node later (runbook)

Run on the new Proxmox node:

```bash
apt update
apt install -y zabbix-agent2 smartmontools sudo

cp /etc/zabbix/zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf.bak.$(date +%F)
sed -i 's/^Server=.*/Server=<ZABBIX_LXC_IP>/' /etc/zabbix/zabbix_agent2.conf
sed -i 's/^ServerActive=.*/ServerActive=<ZABBIX_LXC_IP>/' /etc/zabbix/zabbix_agent2.conf
sed -i "s/^Hostname=.*/Hostname=$(hostname)/" /etc/zabbix/zabbix_agent2.conf

cat >/etc/zabbix/zabbix_agent2.d/plugins.d/smart.conf <<'EOF'
Plugins.Smart.Path=/usr/sbin/smartctl
Plugins.Smart.Timeout=30
EOF

cat >/etc/sudoers.d/zz-zabbix-smartctl <<'EOF'
Defaults:zabbix !requiretty
Defaults:zabbix !authenticate
zabbix ALL=(root) NOPASSWD: /usr/sbin/smartctl, /usr/bin/smartctl
EOF
chmod 440 /etc/sudoers.d/zz-zabbix-smartctl
visudo -c

systemctl enable --now zabbix-agent2
systemctl restart zabbix-agent2

sudo -u zabbix zabbix_agent2 -t 'smart.disk.discovery[name]'
```

In Zabbix UI create host for the new node:

- Group: `Proxmox Nodes`
- Agent interface: node management IP, port `10050`
- Link templates:
  - `Linux by Zabbix agent`
  - `SMART by Zabbix agent 2`

## Next step: check_pve integration

Install on the Zabbix LXC:

```bash
apt install -y python3 python3-requests python3-packaging git
git clone https://github.com/nbuchwitz/check_pve.git /opt/check_pve
chmod 750 /opt/check_pve/check_pve.py
mkdir -p /usr/lib/zabbix/externalscripts
```

Create token file (example):

```bash
cat >/etc/zabbix/check_pve.token <<'EOF'
zabbix-plugin@pve!zbx-plugin=<PUT_SECRET_HERE>
EOF
chown root:zabbix /etc/zabbix/check_pve.token
chmod 640 /etc/zabbix/check_pve.token
```

Create wrapper script:

```bash
cat >/usr/lib/zabbix/externalscripts/check_pve_wrapper.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
API_ENDPOINT="${1:?api endpoint required}"
MODE="${2:?mode required}"
NODE="${3:-}"
TOKEN_FILE="/etc/zabbix/check_pve.token"
API_USER="${PVE_API_USER:-zabbix-plugin@pve}"

BASE=(python3 /opt/check_pve/check_pve.py -e "$API_ENDPOINT" -u "$API_USER" -T "$TOKEN_FILE" -m "$MODE" -k)
if [[ -n "$NODE" && "$NODE" != "-" ]]; then
  "${BASE[@]}" -n "$NODE"
else
  "${BASE[@]}"
fi
EOF

chmod 750 /usr/lib/zabbix/externalscripts/check_pve_wrapper.sh
chown root:zabbix /usr/lib/zabbix/externalscripts/check_pve_wrapper.sh
systemctl restart zabbix-server
```

## Dashboard plan

Create three dashboards:

1. **Overview**
   - Current problems by severity
   - Host availability
   - Proxmox API status

2. **Cluster/Compute**
   - Node CPU and memory usage
   - VM/LXC running state
   - Node/storage utilization

3. **Hardware/Disks**
   - SMART temperatures
   - SMART wear/health indicators
   - Disk/media errors and failed checks

Use host tags/group filters so `Proxmox-API` and node hosts are visible together.
