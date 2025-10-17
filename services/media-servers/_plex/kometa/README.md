# Kometa - Plex Meta Manager

Automated Plex library management for collections, metadata, overlays, and more.

## Architecture: Dual-Volume Version Control

Kometa uses a unique dual-volume setup to separate version-controlled configuration from runtime artifacts.

### Directory Structure

```
services/media-servers/_plex/kometa/
├── docker-compose.yml
└── config/                          # VERSION CONTROLLED
    ├── config.yml                   # Main configuration
    ├── collections/                 # Collection definitions
    │   ├── movies/
    │   └── tvshows/
    ├── custom_fonts/                # Custom fonts for overlays
    ├── .gitignore                   # Ignores symlinks and backups
    └── [symlinks - created at runtime, NOT tracked]
        ├── logs -> /data/logs
        ├── config.cache -> /data/config.cache
        ├── UUID -> /data/UUID
        └── overlays -> /data/overlays
```

### Volume Mounts

```yaml
volumes:
  - ./config:/config-repo:rw        # Config from git repo
  - ${DOCKER_APPDATA_PATH}/kometa:/data:rw  # Runtime data
environment:
  - KOMETA_CONFIG=/config-repo/config.yml
```

### Runtime Files (in appdata, NOT git)

- `/data/logs/` - Log files (~200MB)
- `/data/overlays/` - Generated overlay images (~3GB)
- `/data/assets/` - Custom posters/artwork (~26MB)
- `/data/config.cache` - Runtime cache (~54MB)
- `/data/UUID` - Instance identifier
- `/data/missing/` - Generated reports

### Path Convention in config.yml

- **Configuration files**: `/config-repo/collections/...`, `/config-repo/custom_fonts/...`
- **Runtime files**: `/data/assets/...`, `/data/missing/...`, `/data/overlays/...`

### Symlinks

Container entrypoint automatically creates symlinks on startup to redirect Kometa's runtime files to appdata:

```bash
ln -sf /data/logs /config-repo/logs
ln -sf /data/config.cache /config-repo/config.cache
ln -sf /data/UUID /config-repo/UUID
ln -sf /data/overlays /config-repo/overlays
```

### Why This Approach

- ✅ Only ~600KB of pure configuration in git repo
- ✅ ~3.5GB of runtime artifacts stay in appdata
- ✅ Clean separation for backups and version control
- ✅ Container fully reproducible from git repo
- ✅ Scheduled execution via Cronicle (external scheduling)

### Scheduled Execution

Kometa runs via Cronicle jobs (not built-in scheduler):
- **Daily library update**: Full collection and metadata updates
- **Overlay operations**: Periodic overlay image generation
- **Quick operations**: Ad-hoc runs for testing specific collections

See Cronicle web UI for current job schedules.

## Direct Run commands

Useful for testing

### Run Kometa immediatly

- Will run Kometa immediately rather than waiting
- Same as having `KOMETA_RUN=true` in `the docker-compose.yml`

```shell
docker exec -it kometa python3 kometa.py --run
```

### Test Collections

- Kometa will run only collections that are marked as test immediately
- Have `test: true` as first value in a collection

```shell
docker exec -it kometa python3 kometa.py --tests
```

```yml
collections:
  Detective & Crime Shows:
    test: true # Add this
    trakt_list: https://trakt.tv/users/raphh11/lists/crime-shows
    smart_label: added.desc
```

### Other commands

```shell
docker exec -it kometa python3 kometa.py --overlays-only
````

```shell
docker exec -it kometa python3 kometa.py --run-libraries "Movies" --overlays-only
````


```shell
docker exec -it kometa python3 kometa.py --run-libraries "Movies"
````