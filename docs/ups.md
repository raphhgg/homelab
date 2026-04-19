# Proxmox CyberPower UPS Setup Guide

**Hardware:** CyberPower CP1600EPFCLCD (1000W / 1600VA)  
**OS:** Proxmox VE (Debian)  
**Software:** Network UPS Tools (NUT)  

## Overview
This guide covers the installation and configuration of NUT to monitor a locally connected via USB CyberPower UPS. If the power goes out and the battery reaches a critical level, NUT will issue a graceful shutdown command to the Proxmox host.

## Prerequisites
1. Plug the Proxmox server into a **Battery + Surge** outlet on the UPS.
2. Connect the UPS to the Proxmox server via the included USB cable.
3. Verify connection by running `lsusb` in the Proxmox shell. Look for `Cyber Power System, Inc.`

## Step-by-Step Configuration

### 1. Install Packages
Install the required NUT components:
```bash
apt update && apt install nut nut-client nut-server -y
```


### 2. Configure the UPS Driver

Edit `/etc/nut/ups.conf` and append the following to define the hardware:

```ini
[cyberpower]
driver = usbhid-ups
port = auto
desc = "CyberPower CP1600EPFCLCD"

```

### 3. Enable Standalone Mode

Edit `/etc/nut/nut.conf` and change the operation mode:

```ini
MODE=standalone

```

### 4. Create Monitoring Credentials

Edit `/etc/nut/upsd.users` and add a local user so the monitor service can securely read the UPS data:

```ini
[upsmon]
password = <choose-a-strong-local-password>
upsmon master

```

### 5. Set Shutdown Rules

Edit `/etc/nut/upsmon.conf` and configure the monitor to watch the UPS and trigger a graceful shutdown when the battery is critical:

```ini
MONITOR cyberpower@localhost 1 upsmon <same-password-as-above> master
SHUTDOWNCMD "/sbin/shutdown -h now"
POWERDOWNFLAG /etc/killpower

```

### 6. Fix USB Autosuspend Bug

Debian-based systems often put USB ports to sleep, which breaks the NUT connection. Disable autosuspend by running:

```bash
echo "options usbcore autosuspend=-1" > /etc/modprobe.d/usbcore.conf
update-initramfs -u

```

*(This takes full effect after the next server reboot).*

### 7. Fix USB Permissions & Start Services

Reload the hardware rules so NUT has permission to access the USB port, then enable the services to start on boot:

```bash
udevadm control --reload-rules && udevadm trigger
systemctl enable nut-server nut-client
systemctl restart nut-server nut-client

```

> **Note:** If you get a "Could not open any HID devices" error at this stage, physically unplug the USB cable from the server, wait 3 seconds, and plug it back in.

## Verification

Run the following command to see the live output of the UPS:

```bash
upsc cyberpower

```

You should see `ups.status: OL` (On Line) and your current `ups.load` and `battery.runtime`.

```
