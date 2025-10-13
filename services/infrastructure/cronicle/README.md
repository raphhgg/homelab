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
- Command: `docker exec imagemaid python3 -u imagemaid.py --mode remove --overlays-only --empty-trash --clean-bundles --optimize-db --photo-transcoder`

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

API Key is stored in `.env`:
```bash
CRONICLE_API_KEY=159a3772fe5a3303bf81172da7c4c0ac
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
# Via API
curl -s "http://10.10.2.2:3012/api/app/get_schedule/v1?api_key=159a3772fe5a3303bf81172da7c4c0ac"

# Via Web UI
Open http://10.10.2.2:3012 and navigate to Schedule
```

### Run Job Manually

```bash
# Replace <event_id> with the job ID (e.g., emgm0196w02)
curl -s -X POST "http://10.10.2.2:3012/api/app/run_event/v1" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 159a3772fe5a3303bf81172da7c4c0ac" \
  -d '{"id":"<event_id>"}'
```

### View Job Logs

Logs are compressed and stored in `/volume2/docker/appdata/cronicle/data/jobs/`:

```bash
# Find recent logs
docker exec cronicle find /opt/cronicle/data/jobs -name "*.gz" -type f -mmin -60

# Read a log file
docker exec cronicle zcat /opt/cronicle/data/jobs/<path>/log.txt.gz
```

## Troubleshooting

### Shell Plugin Permissions

If jobs fail with permission errors, ensure:

1. **Temp directory has execution permissions**:
   ```bash
   docker exec cronicle ls -ld /opt/cronicle/tmp
   ```

2. **Logs directory is accessible**:
   ```bash
   chmod 755 /volume2/docker/appdata/cronicle/logs
   ```

See [main CLAUDE.md](../../../CLAUDE.md#cronicle-shell-plugin-permission-issues) for detailed troubleshooting.

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
