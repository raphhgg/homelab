#!/bin/bash
# CyberPower UPS Setup Script for Proxmox (NUT)
# Hardware: CyberPower CP1600EPFCLCD

UPSMON_PASSWORD="${UPS_MONITOR_PASSWORD:-}"

if [[ -z "${UPSMON_PASSWORD}" ]]; then
  echo "ERROR: set UPS_MONITOR_PASSWORD before running this script." >&2
  exit 1
fi

echo "Starting NUT installation and configuration..."

# 1. Install NUT packages
echo "Installing NUT packages..."
apt update && apt install nut nut-client nut-server -y

# 2. Configure the UPS Driver
echo "Configuring /etc/nut/ups.conf..."
cat << 'EOF' >> /etc/nut/ups.conf

[cyberpower]
driver = usbhid-ups
port = auto
desc = "CyberPower CP1600EPFCLCD"
EOF

# 3. Set NUT to Standalone Mode
echo "Setting NUT to standalone mode..."
sed -i 's/MODE=none/MODE=standalone/g' /etc/nut/nut.conf

# 4. Set Up Local Credentials
echo "Configuring /etc/nut/upsd.users..."
cat <<EOF >> /etc/nut/upsd.users

[upsmon]
password = ${UPSMON_PASSWORD}
upsmon master
EOF

# 5. Configure the Monitor and Shutdown Command
echo "Configuring /etc/nut/upsmon.conf..."
cat <<EOF >> /etc/nut/upsmon.conf

MONITOR cyberpower@localhost 1 upsmon ${UPSMON_PASSWORD} master
SHUTDOWNCMD "/sbin/shutdown -h now"
POWERDOWNFLAG /etc/killpower
EOF

# 6. Apply USB Autosuspend Fix (Prevents disconnects)
echo "Applying USB autosuspend fix..."
echo "options usbcore autosuspend=-1" > /etc/modprobe.d/usbcore.conf
update-initramfs -u

# 7. Reload UDEV rules to fix USB permissions
echo "Reloading UDEV rules..."
udevadm control --reload-rules && udevadm trigger

# 8. Enable and Restart Services
echo "Enabling and starting NUT services..."
systemctl enable nut-server nut-client
systemctl restart nut-server nut-client

echo "Setup complete! Please unplug the UPS USB cable for 3 seconds, plug it back in, and run 'upsc cyberpower' to verify."
