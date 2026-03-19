# Network Monitoring Baseline (NetAlertX + SmokePing)

This baseline adds LAN device discovery and link quality monitoring, then wires alerts and dashboards through Zabbix and Grafana.

## 1) Host ARP Tuning (Debian VM Docker Host)

NetAlertX discovery quality is better when ARP flux controls are enabled on the host kernel:

- `net.ipv4.conf.all.arp_ignore=1`
- `net.ipv4.conf.all.arp_announce=2`

Apply and persist with:

```bash
./scripts/install-network-monitoring-baseline.sh
```

If needed, run directly:

```bash
sudo ./scripts/install-network-monitoring-baseline.sh
```

The script also starts NetAlertX and SmokePing, verifies container status, and checks HTTP responses.

## 2) Services Added

- NetAlertX: `services/monitoring/netalertx/`
- SmokePing: `services/monitoring/smokeping/`

## 3) Zabbix Agent helper setup (Debian VM)

Install helper user-parameters on the host monitored by Zabbix agent:

```bash
sudo ./scripts/install-zabbix-network-monitoring.sh
```

This installs:

- `/usr/local/bin/zabbix-network-monitoring.py`
- `/etc/zabbix/zabbix_agent2.d/network-monitoring.conf`

Provided Zabbix keys:

- `netalertx.status` (`1` when UI/API reachable)
- `smokeping.status` (`1` when UI reachable)
- `netalertx.tile[all]`
- `netalertx.tile[connected]`
- `netalertx.tile[offline]`
- `netalertx.tile[down]`
- `netalertx.tile[new]`
- `netalertx.tile[favorites]`

## 4) Zabbix Setup

Create hosts:

- `netalertx`
- `smokeping`

Use HTTP agent items where possible.

### NetAlertX items (Type: Zabbix agent)

- `netalertx.status`
- `netalertx.tile[all]`
- `netalertx.tile[connected]`
- `netalertx.tile[offline]`
- `netalertx.tile[down]`
- `netalertx.tile[new]`

### SmokePing service item (Type: Zabbix agent)

- `smokeping.status`

### Link-quality items (Type: Simple check)

Create these on the same host (or a dedicated synthetic-check host):

- `icmpping[10.10.0.1,,,,5]` (gateway reachability)
- `icmppingloss[10.10.0.1,,,,5]` (gateway packet loss %)
- `icmppingsec[10.10.0.1,,,,5]` (gateway latency seconds)
- `icmpping[1.1.1.1,,,,5]`
- `icmppingloss[1.1.1.1,,,,5]`
- `icmppingsec[1.1.1.1,,,,5]`
- `icmpping[8.8.8.8,,,,5]`
- `icmppingloss[8.8.8.8,,,,5]`
- `icmppingsec[8.8.8.8,,,,5]`

## 5) Zabbix Triggers (starting thresholds)

### NetAlertX

- Service down: `last(/<host>/netalertx.status)=0` for 5m
- New unknown device: `last(/<host>/netalertx.tile[new])>0`
- Known device down: `last(/<host>/netalertx.tile[down])>0` for 5m

### SmokePing

- Service down: `last(/<host>/smokeping.status)=0` for 5m
- Gateway loss warning: `min(/<host>/icmppingloss[10.10.0.1,,,,5],10m)>1`
- Gateway loss high: `min(/<host>/icmppingloss[10.10.0.1,,,,5],5m)>5`
- Gateway latency high: `avg(/<host>/icmppingsec[10.10.0.1,,,,5],10m)>0.03`
- Internet latency high (Cloudflare DNS): `avg(/<host>/icmppingsec[1.1.1.1,,,,5],10m)>0.05`

## 6) Grafana Panels (Zabbix datasource)

Create a new row/group named `Network Quality & Discovery` with:

1. NetAlertX overview
   - `netalertx.tile[all]`
   - `netalertx.tile[connected]`
   - `netalertx.tile[offline]`
   - `netalertx.tile[new]`
   - `netalertx.tile[down]`
2. SmokePing quality
   - `icmppingloss` trend for gateway / `1.1.1.1` / `8.8.8.8`
   - `icmppingsec` trend for gateway / `1.1.1.1` / `8.8.8.8`
   - single stat panel: current gateway loss and latency
3. Alert context
   - Active Zabbix problems for `netalertx` and `smokeping`

## 7) Alert Routing

Recommended initial routing:

- High: critical device offline, WAN loss > 5%
- Warning: new unknown device, WAN loss > 1%
- Info: dashboard-only (trends, baseline changes)

Tune thresholds after 7-14 days of observed baseline.
