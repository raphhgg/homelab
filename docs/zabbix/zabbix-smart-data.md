# SATA and NVMe SMART metrics in Zabbix

This installs a single helper that exposes extra SMART metrics for both Intel SATA SSDs and NVMe drives on the Proxmox node host.

It covers:

- Intel SATA wear used / remaining
- Intel SATA self-test timestamp
- Intel SATA write / read / NAND counters
- NVMe wear used / remaining
- NVMe media errors / unsafe shutdowns / read-write counters

## Run on `pve`

Copy `scripts/install-intel-sata-smart.sh` to the node and run it as root.

```bash
chmod +x install-intel-sata-smart.sh
sudo ./install-intel-sata-smart.sh
```

It installs these Zabbix agent keys:

- `smart.intel.wearout[sda]`
- `smart.intel.wearout[sdb]`
- `smart.intel.last_pass_epoch[sda]`
- `smart.intel.last_pass_epoch[sdb]`
- `smart.intel.metric[sda,<metric>]`
- `smart.intel.metric[sdb,<metric>]`
- `smart.nvme.metric[nvme0,<metric>]`
- `smart.nvme.metric[nvme1,<metric>]`

## What they mean

- `smart.intel.wearout[*]` returns Intel SATA wear used percentage, derived from SMART attribute `233 Media_Wearout_Indicator`
- Intel attribute `233` is normalized remaining life (`100` = new), so the script converts it to used wear (`100 - value`) to match Proxmox-style reporting
- `51` / `52` means roughly half of the rated NAND endurance has been used
- `smart.intel.last_pass_epoch[*]` estimates the Unix timestamp of the most recent successful SMART self-test from the drive self-test log and current power-on hours

## Quick checks on the node

```bash
sudo -u zabbix zabbix_agent2 -t smart.intel.wearout[sda]
sudo -u zabbix zabbix_agent2 -t smart.intel.wearout[sdb]
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch[sda]
sudo -u zabbix zabbix_agent2 -t smart.intel.last_pass_epoch[sdb]
```

After that, these keys can be added to Zabbix items and then shown in Grafana.

Useful extra metrics:

- SATA: `wear_used`, `wear_remaining`, `available_reserved_space`, `host_writes_32mib`, `host_reads_32mib`, `nand_writes_32mib`, `workload_media_wear_raw`, `workload_host_reads_perc`, `workload_minutes`, `power_on_hours`, `power_cycle_count`, `temperature`
- NVMe: `wear_used`, `wear_remaining`, `power_on_hours`, `temperature`, `unsafe_shutdowns`, `media_errors`, `data_units_read`, `data_units_written`
