#!/bin/bash
set -euo pipefail

rm -f /tmp/.X99-lock
pkill -f "Xvfb :99" >/dev/null 2>&1 || true

Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

sleep 1

exec python -u plex_bot.py
