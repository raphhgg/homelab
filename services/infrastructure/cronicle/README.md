# Cronicle - Job Scheduler

Cronicle is a multi-server task scheduler with a web-based UI that manages all media server automation tasks.

## Access

- **Web UI**: http://10.10.2.2:3012
- **Container**: `cronicle`
- **Networks**: `main`, `socket_proxy`

## Overview

This Cronicle instance handles all scheduled tasks for Kometa and ImageMaid, replacing their internal scheduling mechanisms. Jobs are executed via Docker commands through the docker-socket-proxy for security.

## Scheduled Jobs

### Daily Schedule

**06:00 - Kometa - Metadata Update**
- Updates metadata for all Plex libraries
- Command: `docker exec kometa python -u kometa.py --run --metadata-only`

**07:00 - Kometa - Overlays Update**
- Applies overlays (ratings, quality, language, etc.)
- Command: `docker exec kometa python -u kometa.py --run --overlays-only`

**08:00 - Kometa - Collections Update**
- Rebuilds and updates collections
- Command: `docker exec kometa python -u kometa.py --run --collections-only`

**14:00 - Kometa - Metadata Update**
- Afternoon metadata refresh
- Command: `docker exec kometa python -u kometa.py --run --metadata-only`

**15:00 - Kometa - Overlays Update**
- Afternoon overlay refresh
- Command: `docker exec kometa python -u kometa.py --run --overlays-only`

**16:00 - Kometa - Collections Update**
- Afternoon collection refresh
- Command: `docker exec kometa python -u kometa.py --run --collections-only`

**22:00 - Kometa - Metadata Update**
- Evening metadata refresh
- Command: `docker exec kometa python -u kometa.py --run --metadata-only`

**23:00 - Kometa - Overlays Update**
- Evening overlay refresh
- Command: `docker exec kometa python -u kometa.py --run --overlays-only`

**23:00 - ImageMaid - Cleanup**
- Plex image cleanup (overlays, trash, bundles, DB)
- Command: `docker exec imagemaid python3 -u imagemaid.py --mode remove --empty-trash --clean-bundles --optimize-db --photo-transcoder`

**23:30 - Kometa - Operations**
- Mass rating updates and library maintenance
- Command: `docker exec kometa python -u kometa.py --run --operations-only`

### Weekly Schedule

**Sunday 09:00 - Kometa - Playlists Update**
- Updates Plex playlists
- Command: `docker exec kometa python -u kometa.py --run --playlists-only`

## Job Details

### Kometa Jobs

All Kometa jobs use the `-u` flag for unbuffered Python output to ensure real-time log streaming.

1. **Metadata Update** (3x daily)
   - Updates movie/show metadata from TMDB/IMDB
   - Syncs with Sonarr/Radarr tags
   - Runtime: ~30-60 minutes per run

2. **Overlays Update** (3x daily)
   - Applies poster overlays (ratings, resolution, audio, language, etc.)
   - Only updates changed items (unless `reapply_overlays: true`)
   - Runtime: ~15-30 minutes per run

3. **Collections Update** (2x daily)
   - Builds/updates genre, language, date, quality collections
   - Includes Letterboxd lists and franchises
   - Runtime: ~20-40 minutes per run

4. **Operations** (1x daily)
   - Mass updates: user ratings, critic ratings, audience ratings
   - Cleans up managed collections
   - Runtime: ~10-20 minutes per run

5. **Playlists Update** (Weekly)
   - Updates Plex playlists across libraries
   - Runtime: ~5-10 minutes per run

### ImageMaid Job

**ImageMaid - Cleanup** (1x daily at 23:00)
- Removes overlay metadata files that are no longer needed
- Empties Plex trash
- Cleans Plex bundles
- Optimizes Plex database
- Cleans PhotoTranscoder cache
- Mode: `remove` (permanent deletion)
- Runtime: ~10-30 minutes depending on cleanup size

## Configuration

### API Access

**API Key**: Available in `.env` file as `CRONICLE_API_KEY=159a3772fe5a3303bf81172da7c4c0ac`

**Important**: Claude can create/update/delete Cronicle jobs programmatically using the HTTP API.

**API Endpoints:**
- Base URL: `http://10.10.2.2:3012/api/app/`
- API Key: `159a3772fe5a3303bf81172da7c4c0ac` (passed as query parameter)

**Common Operations:**

```bash
# List all scheduled jobs
curl -s "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac"

# Get job status
curl -s "http://10.10.2.2:3012/api/app/get_job_status/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac&id=JOB_ID"

# Trigger job manually
curl -s -X POST "http://10.10.2.2:3012/api/app/run_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID"}'

# Create new event (job)
curl -s -X POST "http://10.10.2.2:3012/api/app/create_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{
    "title": "Job Title",
    "enabled": 1,
    "category": "CATEGORY_ID",
    "plugin": "shellplug",
    "target": "allgrp",
    "params": {
      "script": "#!/bin/bash\necho \"Job script here\"",
      "annotate": 1
    },
    "timing": {
      "hours": [3],
      "minutes": [0]
    },
    "timezone": "Europe/Brussels",
    "notes": "Job description"
  }'

# Update existing event
curl -s -X POST "http://10.10.2.2:3012/api/app/update_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID", ...}'

# Delete event
curl -s -X POST "http://10.10.2.2:3012/api/app/delete_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"EVENT_ID"}'
```

### Job Categories

Cronicle jobs are organized by categories. Current categories:
- **Media Server** (`cmgm06foc04`) - Kometa, ImageMaid, Plex-related jobs
- **Monitoring** (`cmgumlb1w1e`) - Watchtower, monitoring, health check jobs

**When Claude adds a Cronicle job:**

1. **For existing services in known categories**: Add the job to the appropriate category:
   - **Media Server jobs**: Kometa, ImageMaid, Plex, Jellyfin operations → Use `cmgm06foc04`
   - **Monitoring jobs**: Watchtower, Beszel checks, Uptime Kuma tasks → Use `cmgumlb1w1e`

2. **For services that don't fit existing categories**: Ask the user:
   - "This job is for [SERVICE_NAME] which doesn't fit existing categories (Media Server, Monitoring). Should I:
     - Add it to one of the existing categories? Which one?
     - Create a new category? If so, what should it be called?"

3. **If user requests a new category**:
   - Ask the user to create it via Cronicle web UI (Admin > Categories)
   - Reason: The `create_category` API requires admin authentication which Claude doesn't have
   - Once created, ask the user for the new category ID (format: `cmXXXXXXXXX`)
   - Update the categories list above with the new category

4. **Category naming convention**:
   - Use clear, descriptive names (e.g., "Media Server", "Infrastructure", "Monitoring")
   - Categories help organize jobs in the Cronicle UI
   - Choose colors that make categories visually distinct

### Job Timing Format

Cronicle uses a timing object for scheduling (similar to cron but JSON format):

```json
{
  "timing": {
    "years": [2025],           // Optional: specific years
    "months": [1, 6, 12],      // Optional: specific months (1-12)
    "days": [1, 15],           // Optional: specific days of month (1-31)
    "weekdays": [0, 6],        // Optional: specific weekdays (0=Sunday, 6=Saturday)
    "hours": [3],              // Hours (0-23)
    "minutes": [0, 30]         // Minutes (0-59)
  },
  "timezone": "Europe/Brussels"
}
```

**Examples:**
- Daily at 3 AM: `{"hours": [3], "minutes": [0]}`
- Every 6 hours: `{"hours": [0, 6, 12, 18], "minutes": [0]}`
- Three times a day: `{"hours": [5, 13, 21], "minutes": [0]}`
- Weekly on Sunday at 2 AM: `{"weekdays": [0], "hours": [2], "minutes": [0]}`

### Shell Plugin Parameters

Most jobs use the Shell Plugin (`"plugin": "shellplug"`) with these parameters:

```json
{
  "params": {
    "script": "#!/bin/bash\nYOUR_SCRIPT_HERE",
    "annotate": 1,           // Add timestamps to log output
    "json": 0,               // Parse JSON in output (usually 0)
    "lang": "shell",         // Syntax highlighting
    "theme": "default"       // Editor theme
  }
}
```

**Script guidelines:**
- Always include shebang: `#!/bin/bash`
- Use `docker exec` for running commands in containers
- Add `-u` flag for unbuffered output: `python3 -u script.py`
- Return proper exit codes (0 = success, non-zero = failure)

### Common Job Patterns

**Docker exec pattern:**
```bash
#!/bin/bash
docker exec CONTAINER_NAME command --flags
```

**Docker run pattern (for one-off containers):**
```bash
#!/bin/bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=tcp://docker-proxy:2375 \
  --network socket_proxy \
  IMAGE_NAME \
  --flags
```

**API call pattern:**
```bash
#!/bin/bash
TOKEN="${ENV_VARIABLE}"
curl -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  "http://service:port/api/endpoint"
```

### Example: Adding a Watchtower Daily Check Job

When Claude is asked to add a Watchtower daily check job:

```json
{
  "title": "Watchtower - Daily Update Check",
  "enabled": 1,
  "category": "cmgumlb1w1e",
  "plugin": "shellplug",
  "target": "allgrp",
  "params": {
    "script": "#!/bin/bash\n# Check for container updates\n\ndocker exec watchtower watchtower --run-once --label-enable 2>&1 | tee /tmp/watchtower-check.log\n\n# Future Phase 2: Parse output and send Apprise notifications",
    "annotate": 1,
    "lang": "shell",
    "theme": "default"
  },
  "timing": {
    "hours": [3],
    "minutes": [0]
  },
  "timezone": "Europe/Brussels",
  "notes": "Daily container update check. Auto-updates Tier 1 containers, logs updates for Tier 2 (manual approval).",
  "max_children": 1,
  "timeout": 0
}
```

### Docker Socket Access

Cronicle connects to Docker via socket proxy:
```yaml
environment:
  - DOCKER_HOST=tcp://172.26.0.22:2375
networks:
  - socket_proxy
```

### Timezone

All jobs run in `Europe/Brussels` timezone.

## Management

### View Job Status

```bash
# Via Web UI
Open http://10.10.2.2:3012 and navigate to Schedule

# Via API (see API Access section for more operations)
curl -s "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac"
```

### View Job Logs

Logs are compressed and stored in `/volume2/docker/appdata/cronicle/data/jobs/` or `/volume2/docker/appdata/cronicle/logs/jobs/`:

```bash
# Via Web UI (easiest)
Open http://10.10.2.2:3012 and click "Completed" tab

# Find recent logs (data/jobs)
docker exec cronicle find /opt/cronicle/data/jobs -name "*.gz" -type f -mmin -60

# Find recent logs (logs/jobs)
docker exec cronicle find /opt/cronicle/logs/jobs -name "*.log" -type f -mmin -60

# Read a compressed log file
docker exec cronicle zcat /opt/cronicle/data/jobs/<path>/log.txt.gz

# Read a plain log file
docker exec cronicle cat /opt/cronicle/logs/jobs/<filename>.log
```

## Troubleshooting

### Shell Plugin Permission Issues

When running Cronicle on Synology with shell scripts, you may encounter permission errors preventing job execution.

**Two common issues:**

1. **Temp directory execution restrictions** (GitHub issue [#673](https://github.com/jhuckaby/Cronicle/issues/673))
   - **Symptom:** Shell plugin crashes immediately, "Permission denied" on temp scripts
   - **Cause:** `/tmp` mounted with noexec restrictions
   - **Solution:** Set custom temp directory with execution permissions
   ```yaml
   environment:
     - TMP=/opt/cronicle/tmp
     - TMPDIR=/opt/cronicle/tmp
   volumes:
     - ${DOCKER_APPDATA_PATH}/cronicle/tmp:/opt/cronicle/tmp:rw
   ```

2. **Log directory access restrictions**
   - **Symptom:** "EACCES: permission denied" when writing to `/opt/cronicle/logs/jobs/*.log`
   - **Cause:** Parent `/opt/cronicle/logs/` directory has 700 permissions (owner-only)
   - **Solution:** Make logs directory readable by the shell plugin user
   ```bash
   chmod 755 /volume2/docker/appdata/cronicle/logs
   # Or inside container:
   docker exec cronicle chmod 755 /opt/cronicle/logs/
   ```

**Important**: Both fixes are required for Cronicle shell plugin to work properly on Synology NAS.

**Verification:**
```bash
# Check temp directory permissions
docker exec cronicle ls -ld /opt/cronicle/tmp

# Check logs directory permissions
docker exec cronicle ls -ld /opt/cronicle/logs
```

### Container Restarts

If Cronicle container restarts, all jobs remain scheduled (persisted in data volume).

### Job Failures

Check job history in Web UI:
1. Go to http://10.10.2.2:3012
2. Click "Completed" tab
3. View failed jobs and their error logs

## Related Services

- **Kometa**: [services/media-servers/_plex/kometa](../../media-servers/_plex/kometa/)
- **ImageMaid**: [services/media-servers/_plex/imagemaid](../../media-servers/_plex/imagemaid/)
- **Docker Socket Proxy**: [services/infrastructure/docker-socket-proxy](../docker-socket-proxy/)

## Notes

- Internal scheduling has been disabled in both Kometa (`KOMETA_TIMES`) and ImageMaid (`SCHEDULE`) docker-compose files
- All scheduling is now centrally managed through Cronicle
- Jobs use unbuffered output (`-u` flag) for real-time logging
- Cronicle automatically retries failed jobs based on configuration
- Job execution history is retained for analysis and debugging
