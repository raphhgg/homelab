# Kometa - Plex Meta Manager

Automated Plex library management for collections, metadata, overlays, and more.

## Configuration Repository

Kometa configuration is maintained in a **dedicated git repository** separate from the homelab infrastructure:

**Repository**: [github.com/raaphhh/kometa-config](https://github.com/raaphhh/kometa-config) (private)

**Location**: `/volume2/docker/appdata/kometa/config/`

This separation keeps infrastructure configuration (docker-compose) in the homelab repo while application configuration (YAML files, fonts, overlays) lives in its own versioned repository.

## Architecture

### Directory Structure

```
/volume2/docker/appdata/kometa/
├── config/                          # DEDICATED GIT REPO
│   ├── .git/                       # Git repository
│   ├── config.yml                  # Main configuration
│   ├── collections/                # Collection definitions
│   │   ├── movies/
│   │   └── tvshows/
│   ├── custom_fonts/               # Custom fonts for overlays
│   ├── custom_overlays/            # Overlay configurations
│   ├── metadata/                   # Metadata files
│   └── .gitignore                  # Ignores runtime artifacts
├── logs/                           # Runtime - NOT in git
├── overlays/                       # Runtime - NOT in git
├── assets/                         # Runtime - NOT in git
├── missing/                        # Runtime - NOT in git
├── config.cache                    # Runtime - NOT in git
└── UUID                            # Runtime - NOT in git
```

### Volume Mounts

```yaml
volumes:
  - ${DOCKER_APPDATA_PATH}/kometa/config:/config:rw  # Config from dedicated repo
  - ${DOCKER_APPDATA_PATH}/kometa:/data:rw           # Runtime data
environment:
  - KOMETA_CONFIG=/config/config.yml
```

### Runtime Files (in appdata, NOT git)

- `/data/logs/` - Log files (~16MB)
- `/data/overlays/` - Generated overlay images (~2.8GB)
- `/data/assets/` - Custom posters/artwork (~609MB)
- `/data/config.cache` - Runtime cache (~65MB)
- `/data/UUID` - Instance identifier
- `/data/missing/` - Generated reports (~1.3MB)

### Path Convention in config.yml

- **Configuration files**: `/config/collections/...`, `/config/custom_fonts/...`
- **Runtime files**: `/data/assets/...`, `/data/missing/...`, `/data/overlays/...`

### Why This Approach

- ✅ Clean separation: Infrastructure (docker-compose) vs application config (Kometa YAML)
- ✅ Focused git history: Kometa config changes tracked separately from homelab changes
- ✅ Easier maintenance: Config changes don't clutter homelab repo
- ✅ Better portability: Config repo can be cloned independently
- ✅ Standard Docker practice: Config in appdata with dedicated version control

## Managing Configuration

### Making Configuration Changes

Configuration files are in a separate git repository:

```bash
# Navigate to config directory
cd /volume2/docker/appdata/kometa/config

# Make changes to YAML files
vim collections/movies/some-collection.yml

# Commit and push
git add .
git commit -m "Update movie collections"
git push origin main
```

### Updating Docker Infrastructure

Infrastructure changes (docker-compose.yml, .env) are managed in the homelab repo:

```bash
# Navigate to homelab repo
cd /volume2/docker/compose/services/media-server/kometa

# Make changes
vim docker-compose.yml

# Commit to homelab repo
git add .
git commit -m "[kometa] update docker configuration"
git push origin main

# Apply changes
docker-compose up -d
```

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