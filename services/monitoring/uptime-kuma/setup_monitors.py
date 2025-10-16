#!/usr/bin/env python3
"""
Uptime Kuma Monitor Setup Script

This script creates monitors in Uptime Kuma organized in groups, skipping any that already exist.
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

# Monitor groups and their monitors
MONITOR_GROUPS = {
    "infrastructure": [
        {
            "name": "docker-proxy",
            "type": MonitorType.PORT,
            "hostname": "10.10.2.2",
            "port": 2375,
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
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
            "critical": True,
            "description": "Cloudflare DDNS updater",
        },
        {
            "name": "cronicle",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
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
            "critical": True,
            "description": "GitHub Actions runner",
        },
    ],
    "monitoring": [
        {
            "name": "uptime-kuma",
            "type": MonitorType.HTTP,
            "url": "http://localhost:3001",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
            "description": "Uptime Kuma self-monitoring",
        },
        {
            "name": "dozzle",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8088",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Docker log viewer",
        },
        {
            "name": "beszel",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8091",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
            "description": "System performance monitoring",
        },
    ],
    "media-server": [
        {
            "name": "plex",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:32400/identity",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
            "description": "Plex Media Server",
        },
        {
            "name": "tautulli",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8181",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
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
            "description": "Plex audio/subtitle automation",
        },
        {
            "name": "autopulse",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:2875",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Plex automation",
        },
    ],
    "media-arrs": [
        {
            "name": "sonarr",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8988/ping",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "keyword": "pong",
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
            "description": "Indexer manager",
        },
        {
            "name": "bazarr",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:6767/api/system/status?apikey=95169c3b01a256e43d603e42026db7e8",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Subtitles management",
        },
        {
            "name": "profilarr",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:6868",
            "interval": 60,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Profile sync",
        },
    ],
    "media-downloads": [
        {
            "name": "qbittorrent",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8080",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Torrent client",
        },
        {
            "name": "autobrr",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:7474",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
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
            "description": "Torrent cross-seeding",
        },
        {
            "name": "qbit_manage",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8081",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Torrent management",
        },
        {
            "name": "qui",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:7476",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
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
            "description": "Archive extraction",
        },
        {
            "name": "sabnzbd",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8090/api?mode=version",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Usenet client",
        },
        {
            "name": "jellyseerr",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:5055/api/v1/status",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "Request management",
        },
        {
            "name": "thelounge",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:9001",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "IRC client",
        },
    ],
    "syncthing": [
        {
            "name": "syncthing",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8384",
            "interval": 180,
            "retryInterval": 30,
            "maxretries": 2,
            "description": "File synchronization",
        },
    ],
    "smart-home": [
        {
            "name": "home-assistant",
            "type": MonitorType.HTTP,
            "url": "http://10.10.2.2:8123",
            "interval": 120,
            "retryInterval": 30,
            "maxretries": 2,
            "critical": True,
            "description": "Smart home hub",
        },
    ],
}


def create_critical_tag(api):
    """Create critical tag if it doesn't exist and return tag ID."""
    existing_tags = api.get_tags()

    for tag in existing_tags:
        if tag["name"] == "critical":
            return tag["id"]

    # Create critical tag with red color
    new_tag = api.add_tag(name="critical", color="#E74C3C")
    print("  Created tag: critical")
    return new_tag["id"]


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
    """Create monitors in groups, optionally forcing recreation of all monitors."""
    # Get existing monitors
    existing_monitors = api.get_monitors()
    existing_names = {monitor["name"]: monitor for monitor in existing_monitors}

    # Create critical tag
    critical_tag_id = create_critical_tag(api)

    created_count = 0
    skipped_count = 0
    total_count = sum(len(monitors) for monitors in MONITOR_GROUPS.values())

    print("\n➕ Setting up monitor groups and monitors...")
    print("=" * 60)

    for group_name, monitors in MONITOR_GROUPS.items():
        # Create or get group
        group_id = None

        if group_name in existing_names:
            if force:
                print(f"\n📁 Recreating group: {group_name}")
                # Group will be deleted and recreated
            else:
                print(f"\n📁 Using existing group: {group_name}")
                group_id = existing_names[group_name]["id"]
                skipped_count += 1

        if group_id is None:
            print(f"\n📁 Creating group: {group_name}")
            group_result = api.add_monitor(
                type=MonitorType.GROUP,
                name=group_name
            )
            group_id = group_result["monitorID"]
            print(f"  ✅ Group created (ID: {group_id})")
            created_count += 1

        # Create monitors in the group
        for monitor_config in monitors:
            monitor_name = monitor_config["name"]

            # Check if monitor already exists (skip if not forcing)
            if not force and monitor_name in existing_names:
                print(f"  ⏭️  Skipping: {monitor_name}")
                skipped_count += 1
                continue

            print(f"  Creating: {monitor_name}")

            # Extract critical flag (before copying)
            is_critical = monitor_config.get("critical", False)

            # Create a copy and remove critical flag (not an API parameter)
            monitor_config_copy = {k: v for k, v in monitor_config.items() if k != "critical"}

            # Add parent group to the copy
            monitor_config_copy["parent"] = group_id

            # Add monitor
            try:
                monitor = api.add_monitor(**monitor_config_copy)
                monitor_id = monitor["monitorID"]

                # Add critical tag if needed
                if is_critical:
                    api.add_monitor_tag(tag_id=critical_tag_id, monitor_id=monitor_id)
                    print(f"    ✅ Created (critical)")
                else:
                    print(f"    ✅ Created")

                created_count += 1
            except Exception as e:
                print(f"    ❌ Error: {e}")

    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   - Created: {created_count}")
    if not force:
        print(f"   - Skipped: {skipped_count}")
    print(f"   - Total:   {total_count + len(MONITOR_GROUPS)}")  # monitors + groups


def main():
    # Check for --force flag
    force = "--force" in sys.argv

    print("=" * 60)
    print("Uptime Kuma - Setup Monitors with Groups")
    print("=" * 60)

    if force:
        print("\n⚠️  FORCE MODE: All existing monitors will be DELETED and recreated!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return
    else:
        print("\nThis script will create monitors that don't exist yet.")
        print("Monitors are organized in groups by category.")
        print("Only 'critical' tag will be used for important services.")
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

        # Create monitors in groups
        setup_monitors(api, force=force)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        api.disconnect()
        print("\n✅ Done!")


if __name__ == "__main__":
    main()
