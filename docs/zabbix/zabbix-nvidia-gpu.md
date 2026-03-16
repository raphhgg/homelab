# NVIDIA GPU Monitoring for Zabbix

Monitors the RTX 3090 (passed through to `debian-vm`) via the Zabbix Agent 2 NVIDIA GPU plugin.

## Current setup

- **Plugin package**: `zabbix-agent2-plugin-nvidia-gpu` 7.4.7
- **Plugin config**: `/etc/zabbix/zabbix_agent2.d/plugins.d/nvidia.conf`
- **Template**: `NVIDIA GPU by Zabbix agent 2` linked to `debian-vm`
- **Driver**: NVIDIA 550.163.01 / CUDA 12.4

## Collected metrics

The template auto-discovers GPUs via `nvml.device.get` and creates items per device. Key items:

| Metric | Zabbix key | Units |
|--------|-----------|-------|
| Temperature | `nvml.device.temperature` | °C |
| GPU utilization | `nvml.device.utilization.gpu` | % |
| Memory utilization | `nvml.device.utilization.memory` | % |
| VRAM used | `nvml.device.memory.fb.used` | B |
| VRAM total | `nvml.device.memory.fb.total` | B |
| Power usage | `nvml.device.power.usage` | W |
| Power limit | `nvml.device.power.limit` | W |
| Fan speed | `nvml.device.fan.speed.avg` | % |
| Graphics clock | `nvml.device.graphics.frequency` | Hz |
| Memory clock | `nvml.device.memory.frequency` | Hz |
| Encoder utilization | `nvml.device.encoder.utilization` | % |
| Decoder utilization | `nvml.device.decoder.utilization` | % |
| Encoder FPS | `nvml.device.encoder.stats.fps` | fps |
| PCIe Rx rate | `nvml.device.pci.utilization.rx.rate` | bps |
| PCIe Tx rate | `nvml.device.pci.utilization.tx.rate` | bps |
| ECC errors (memory) | `nvml.device.errors.memory.corrected` / `.uncorrected` | count |

## Built-in triggers

The template includes 20 triggers covering:

- Temperature: warning + critical thresholds
- GPU/memory utilization: warning + critical thresholds
- Encoder/decoder utilization: warning + critical thresholds
- Fan speed: warning + critical thresholds
- Power usage: warning + critical thresholds
- ECC errors: corrected + uncorrected (memory and register file)
- Power limit changes

## Quick checks on debian-vm

```bash
# Verify plugin is configured
cat /etc/zabbix/zabbix_agent2.d/plugins.d/nvidia.conf

# Check GPU is visible
nvidia-smi

# Test Zabbix agent can read GPU metrics (requires root or zabbix user)
sudo -u zabbix zabbix_agent2 -t nvml.device.get
```

## Grafana dashboard

The `Debian VM` dashboard (`dashboards/debian-vm.json`) displays GPU metrics alongside system and Docker container stats. It is auto-provisioned via the existing dashboards provisioner.
