# Monitoring Scripts

Utility scripts for homelab monitoring automation.

## Watchtower Update and Notify

**Script**: `watchtower_run_and_notify.sh`
**Purpose**: Automated container updates with Discord notifications
**Used by**: Cronicle job "Watchtower - Daily Container Update Check" (ID: emgumobon1f)

### What it does

1. Runs Watchtower to check for container updates
2. Parses Watchtower logs to extract updated containers
3. Fetches version information from container labels
4. Generates changelog URLs for each container
5. Sends formatted Discord notification via Apprise

### Features

- **BusyBox compatible**: Uses only POSIX-compliant commands (no GNU-specific flags)
- **Version parsing**: Extracts version from container labels, handles edge cases
- **Changelog mapping**: Maps container images to GitHub releases or documentation
- **Clean version display**:
  - Handles containers using `:latest` tags (autopulse, github-runner)
  - Shows creation dates when version labels aren't meaningful
  - Removes common prefixes (v, autopulse-v, runner-v, ubuntu-)
- **Discord formatting**: Rich embeds with titles, versions, and clickable changelog links

### Supported Container Images

The script has built-in changelog mappings for:

- **hotio containers**: Sonarr, Radarr, Bazarr, Prowlarr, Readarr, Plex, qBittorrent, SABnzbd, Tautulli
- **linuxserver containers**: All LSIO images via `docker-{app}/releases`
- **autobrr containers**: autobrr, qui
- **Other**: Home Assistant, Beszel, Watchtower, Plex-Auto-Languages, autopulse, Calibre-web-automated

### Usage

The script can be run standalone or via Cronicle:

```bash
# Standalone - runs Watchtower and sends notification
./watchtower_run_and_notify.sh

# With existing log file
./watchtower_run_and_notify.sh /tmp/watchtower-update-20251020-030000.log
```

### Environment Variables

- `APPRISE_URL`: Apprise notification endpoint (default: `http://localhost:8089/notify/watchtower`)
  - From containers: Use `http://apprise:8000/notify/watchtower` (internal port)
  - From host: Use `http://localhost:8089/notify/watchtower` (external port)

### Cronicle Integration

This script is embedded inline in the Cronicle job configuration. The job:

1. Sets `APPRISE_URL=http://apprise:8000/notify/watchtower` (internal container network)
2. Runs `docker exec watchtower /watchtower --run-once --label-enable --cleanup --debug`
3. Saves output to `/tmp/watchtower-update-$(date).log`
4. Executes the notification script inline
5. Script parses the log and sends Discord notification

**Note**: The script file in `scripts/monitoring/` is the source of truth. The Cronicle job contains an inline copy that should be manually updated when the script changes.

### Version Parsing Examples

```bash
# Normal versioned containers (e.g., Sonarr)
sonarr → 4.0.11.2245

# Containers using "main" branch (e.g., autopulse)
autopulse → latest (2025-10-19)

# Containers with Ubuntu version labels (e.g., github-runner)
github-runner → latest

# Containers with v prefix (e.g., Radarr v5.14.0.9383)
radarr → 5.14.0.9383
```

### Changelog URL Mapping

The `get_changelog()` function maps container images to their release pages:

```bash
# hotio containers → GitHub upstream releases
ghcr.io/hotio/sonarr → https://github.com/Sonarr/Sonarr/releases

# linuxserver containers → LSIO docker image releases
lscr.io/linuxserver/syncthing → https://github.com/linuxserver/docker-syncthing/releases

# Other hotio containers → hotio.dev documentation
ghcr.io/hotio/qbit_manage → https://hotio.dev/containers/qbit_manage/

# Custom mappings
ghcr.io/dan-online/autopulse → https://github.com/dan-online/autopulse/releases
myoung34/github-runner → https://github.com/myoung34/docker-github-actions-runner/releases
```

### Troubleshooting

**Issue**: Notification not sent
- Check Apprise is running: `docker ps | grep apprise`
- Verify Apprise URL is correct (port 8000 for containers, 8089 for host)
- Check script output for errors
- Test Apprise manually: `curl -X POST http://apprise:8000/notify/watchtower -d "title=Test" -d "body=Test"`

**Issue**: Wrong version displayed
- Check container labels: `docker inspect <container> | grep org.opencontainers.image.version`
- Verify image in `get_version()` case statement
- For `:latest` tags, check `org.opencontainers.image.created` label

**Issue**: Missing changelog link
- Check if image is in `get_changelog()` case statement
- Add new mapping if needed
- Verify GitHub release URLs are correct

### Future Improvements

- Automatic detection of new container images (no hardcoded mappings)
- Support for Docker Hub release notes
- Error notifications (when updates fail)
- Update statistics (how many containers checked vs updated)
