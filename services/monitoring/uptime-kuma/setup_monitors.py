#!/usr/bin/env python3
"""
Uptime Kuma Monitor Setup Script

This script creates monitors in Uptime Kuma, skipping any that already exist.
Uses actual container names and proper hostnames/IPs.

Requirements:
    python3 -m venv venv
    source venv/bin/activate   
    pip install uptime-kuma-api

Usage:
    python3 setup_monitors.py           # Create new monitors only
    python3 setup_monitors.py --force   # Delete and recreate all monitors
"""

import sys
from uptime_kuma_api import UptimeKumaApi, MonitorType

# Uptime Kuma connection settings
UPTIME_KUMA_URL = "http://localhost:3001"

# Monitor configurations with actual container names and proper hostnames
MONITORS = [
    # ========================================
    # 1. INFRASTRUCTURE
    # ========================================
    {
        "name": "docker-proxy",
        "type": MonitorType.PORT,
        "hostname": "10.10.2.2",
        "port": 2375,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["infrastructure", "critical"],
        "description": "Docker Socket Proxy",
    },
    {
        "name": "cloudflare-ddns",
        "type": MonitorType.DOCKER,
        "docker_container": "cloudflare-ddns",
        "docker_host": 1,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["infrastructure", "critical"],
        "description": "Cloudflare DDNS updater",
    },
    {
        "name": "cronicle",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["infrastructure", "critical"],
        "description": "Cronicle job scheduler",
    },
    {
        "name": "github-actions-runner",
        "type": MonitorType.DOCKER,
        "docker_container": "github-actions-runner",
        "docker_host": 1,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["infrastructure", "critical"],
        "description": "GitHub Actions runner",
    },

    # ========================================
    # 2. MONITORING
    # ========================================
    {
        "name": "uptime-kuma",
        "type": MonitorType.HTTP,
        "url": "http://localhost:3001",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["monitoring", "critical"],
        "description": "Uptime Kuma self-monitoring",
    },
    {
        "name": "dozzle",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8088",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["monitoring"],
        "description": "Docker log viewer",
    },

    # ========================================
    # 3. MEDIA-SERVER (Plex Ecosystem)
    # ========================================
    {
        "name": "plex",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:32400/identity",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server", "critical"],
        "description": "Plex Media Server",
    },
    {
        "name": "tautulli",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8181",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server"],
        "description": "Plex statistics",
    },
    {
        "name": "kometa",
        "type": MonitorType.DOCKER,
        "docker_container": "kometa",
        "docker_host": 1,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server"],
        "description": "Plex metadata manager",
    },
    {
        "name": "imagemaid",
        "type": MonitorType.DOCKER,
        "docker_container": "imagemaid",
        "docker_host": 1,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server"],
        "description": "Plex image cleanup",
    },
    {
        "name": "plex-auto-languages",
        "type": MonitorType.DOCKER,
        "docker_container": "plex-auto-languages",
        "docker_host": 1,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server"],
        "description": "Plex audio/subtitle automation",
    },
    {
        "name": "autopulse",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:2875",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-server"],
        "description": "Plex automation",
    },

    # ========================================
    # 4. MEDIA-ARRS
    # ========================================
    {
        "name": "sonarr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8988/ping",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "keyword": "pong",
        "tags": ["media-arrs"],
        "description": "TV shows management",
    },
    {
        "name": "radarr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:7878/ping",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "keyword": "pong",
        "tags": ["media-arrs"],
        "description": "Movies management",
    },
    {
        "name": "prowlarr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:9696/ping",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "keyword": "pong",
        "tags": ["media-arrs"],
        "description": "Indexer manager",
    },
    {
        "name": "bazarr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:6767/api/system/status?apikey=95169c3b01a256e43d603e42026db7e8",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-arrs"],
        "description": "Subtitles management",
    },
    {
        "name": "profilarr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:6868",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-arrs"],
        "description": "Profile sync",
    },

    # ========================================
    # 5. MEDIA-DOWNLOADS
    # ========================================
    {
        "name": "qbittorrent",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8080",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Torrent client",
    },
    {
        "name": "autobrr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:7474",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Torrent automation",
    },
    {
        "name": "cross-seed",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:2468/api/status?apikey=ec0e3911a00bc8ceee40451051e7731bc1810d9721b66018",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "keyword": "OK",
        "tags": ["media-downloads"],
        "description": "Torrent cross-seeding",
    },
    {
        "name": "qbit_manage",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8081",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Torrent management",
    },
    {
        "name": "qui",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:7476",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "qBittorrent UI",
    },
    {
        "name": "unpackerr",
        "type": MonitorType.DOCKER,
        "docker_container": "unpackerr",
        "docker_host": 1,
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Archive extraction",
    },
    {
        "name": "sabnzbd",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8090/api?mode=version",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Usenet client",
    },
    {
        "name": "jellyseerr",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:5055/api/v1/status",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "Request management",
    },
    {
        "name": "thelounge",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:9001",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["media-downloads"],
        "description": "IRC client",
    },

    # ========================================
    # 6. SYNCTHING
    # ========================================
    {
        "name": "syncthing",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8384",
        "interval": 180,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["syncthing"],
        "description": "File synchronization",
    },

    # ========================================
    # 7. SMART-HOME
    # ========================================
    {
        "name": "home-assistant",
        "type": MonitorType.HTTP,
        "url": "http://10.10.2.2:8123",
        "interval": 120,
        "retryInterval": 30,
        "maxretries": 2,
        "tags": ["smart-home", "critical"],
        "description": "Smart home hub",
    },
]


def create_tags(api, tag_names):
    """Create tags if they don't exist and return tag IDs."""
    existing_tags = api.get_tags()
    tag_map = {tag["name"]: tag for tag in existing_tags}

    # Tag colors mapping
    tag_colors = {
        "infrastructure": "#FF6B6B",
        "monitoring": "#4ECDC4",
        "media-server": "#9B59B6",
        "media-arrs": "#3498DB",
        "media-downloads": "#F39C12",
        "syncthing": "#1ABC9C",
        "smart-home": "#E74C3C",
        "critical": "#E74C3C",
    }

    tag_ids = []
    for tag_name in tag_names:
        if tag_name in tag_map:
            tag_ids.append(tag_map[tag_name]["id"])
        else:
            color = tag_colors.get(tag_name, "#5CDD8B")
            new_tag = api.add_tag(name=tag_name, color=color)
            tag_ids.append(new_tag["id"])
            print(f"  Created tag: {tag_name}")

    return tag_ids


def delete_all_monitors(api):
    """Delete all existing monitors."""
    monitors = api.get_monitors()
    print(f"\n🗑️  Deleting {len(monitors)} existing monitor(s)...")

    for monitor in monitors:
        try:
            api.delete_monitor(monitor["id"])
            print(f"  ✅ Deleted: {monitor['name']}")
        except Exception as e:
            print(f"  ❌ Error deleting {monitor['name']}: {e}")


def setup_monitors(api, force=False):
    """Create monitors, optionally forcing recreation of all monitors."""
    # Get existing monitors
    existing_monitors = api.get_monitors()
    existing_names = {monitor["name"] for monitor in existing_monitors}

    created_count = 0
    skipped_count = 0

    print("\n➕ Setting up monitors...")
    print("=" * 60)

    for monitor_config in MONITORS:
        monitor_name = monitor_config["name"]

        # Check if monitor already exists (skip if not forcing)
        if not force and monitor_name in existing_names:
            print(f"⏭️  Skipping (already exists): {monitor_name}")
            skipped_count += 1
            continue

        print(f"Creating: {monitor_name}")

        # Get tag IDs
        tag_ids = []
        if "tags" in monitor_config:
            tag_ids = create_tags(api, monitor_config["tags"])
            # Create a copy without tags for API call
            monitor_config_copy = {k: v for k, v in monitor_config.items() if k != "tags"}
        else:
            monitor_config_copy = monitor_config.copy()

        # Add monitor
        try:
            monitor = api.add_monitor(**monitor_config_copy)
            monitor_id = monitor["monitorID"]

            # Add tags
            for tag_id in tag_ids:
                api.add_monitor_tag(tag_id=tag_id, monitor_id=monitor_id)

            print(f"  ✅ Created successfully")
            created_count += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   - Created: {created_count}")
    if not force:
        print(f"   - Skipped: {skipped_count}")
    print(f"   - Total:   {len(MONITORS)}")


def main():
    # Check for --force flag
    force = "--force" in sys.argv

    print("=" * 60)
    print("Uptime Kuma - Setup Monitors")
    print("=" * 60)

    if force:
        print("\n⚠️  FORCE MODE: All existing monitors will be DELETED and recreated!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return
    else:
        print("\nThis script will create monitors that don't exist yet.")
        print("Existing monitors will be skipped (not modified).")
        print("\nTip: Use --force to delete and recreate all monitors.\n")

    # Get credentials
    print(f"Connecting to Uptime Kuma at {UPTIME_KUMA_URL}")
    username = input("Username: ")
    password = input("Password: ")

    # Connect
    print("\n🔗 Connecting...")
    api = UptimeKumaApi(UPTIME_KUMA_URL)

    try:
        api.login(username, password)
        print("✅ Connected")

        # Delete all monitors if force mode
        if force:
            delete_all_monitors(api)

        # Create monitors
        setup_monitors(api, force=force)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        api.disconnect()
        print("\n✅ Done!")


if __name__ == "__main__":
    main()
