# Scripts

Utility scripts for homelab automation and maintenance.

## Monitoring Scripts

Located in `monitoring/`:

**See [monitoring/README.md](monitoring/README.md) for complete documentation.**

### watchtower_run_and_notify.sh

Automated container updates with Discord notifications.

**Purpose**: Runs Watchtower to check for container updates, applies them, and sends formatted Discord notifications via Apprise.

**Used by**: Cronicle job "Watchtower - Daily Container Update Check" (daily at 3 AM)

**Key features:**
- BusyBox-compatible (runs in Cronicle container)
- Parses Watchtower logs to extract updated containers
- Fetches version info and generates changelog links
- Sends rich Discord embeds via Apprise

**Note**: Script must be manually copied into Cronicle job when updated.

## Media Download Scripts

Located in `media-download/`:

### hardlink_creator.sh

Creates hardlinks between duplicate files across folders to save disk space.

**Purpose**: Identifies duplicate files and replaces copies with hardlinks to the original, saving storage space while maintaining file accessibility.

**Features:**
- Uses `jdupes` to find duplicates (files >100MB only)
- Keeps original files, replaces copies with hardlinks
- Has episode detection to avoid linking different episodes with same content
- Confirms before making changes

**Usage:**
```bash
./scripts/media-download/hardlink_creator.sh /path/to/original /path/to/copy
```

**Example:**
```bash
# Link duplicate media files between Plex library and downloads
./scripts/media-download/hardlink_creator.sh /data/medias/movies /downloads/complete
```

**Important Notes:**
- Only processes files larger than 100MB (configurable in script)
- Verifies file hashes before creating hardlinks
- Safe to run multiple times (idempotent)
- Preserves original file permissions and timestamps

**Requirements:**
- `jdupes` must be installed (`apt-get install jdupes` or `brew install jdupes`)

### organize_trailers.sh

Organizes trailer files in media libraries.

**Purpose**: Sorts and organizes trailer files for Plex media libraries.

**Usage:**
```bash
./scripts/media-download/organize_trailers.sh
```

**Note**: See script file for detailed usage and configuration options.

## Adding New Scripts

When adding new scripts to this repository:

1. **Place in appropriate category folder**:
   - `media-download/`: Scripts related to media acquisition and management
   - Create new category folders as needed (e.g., `monitoring/`, `maintenance/`)

2. **Make scripts executable**:
   ```bash
   chmod +x scripts/category/script_name.sh
   ```

3. **Include shebang and documentation**:
   ```bash
   #!/bin/bash
   # Script Name: script_name.sh
   # Purpose: Brief description
   # Usage: ./script_name.sh [arguments]
   ```

4. **Update this README** with:
   - Script name and location
   - Purpose and description
   - Usage examples
   - Requirements (dependencies, environment variables)
   - Important notes or warnings

5. **Follow best practices**:
   - Use descriptive variable names
   - Add error handling (`set -e`, `set -u`)
   - Validate inputs
   - Log important actions
   - Return proper exit codes (0 = success, non-zero = error)

## Common Script Patterns

### Docker exec pattern
```bash
#!/bin/bash
docker exec container_name command --flags
```

### Error handling
```bash
#!/bin/bash
set -e  # Exit on error
set -u  # Error on undefined variables

if [ $# -ne 2 ]; then
    echo "Usage: $0 <arg1> <arg2>"
    exit 1
fi
```

### Logging
```bash
#!/bin/bash
LOG_FILE="/tmp/script_name.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Script started"
```

## Scheduling Scripts

Scripts can be scheduled using Cronicle for automated execution. See [services/infrastructure/cronicle/README.md](../services/infrastructure/cronicle/README.md) for details on creating scheduled jobs.

**Example Cronicle job for hardlink_creator.sh:**
```json
{
  "title": "Hardlink Creator - Weekly",
  "plugin": "shellplug",
  "params": {
    "script": "#!/bin/bash\n/volume2/docker/compose/scripts/media-download/hardlink_creator.sh /data/medias/movies /downloads/complete"
  },
  "timing": {
    "weekdays": [0],
    "hours": [2],
    "minutes": [0]
  }
}
```
