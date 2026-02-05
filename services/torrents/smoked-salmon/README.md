# Smoked Salmon

A simple tool to take the work out of uploading on Gazelle-based trackers (RED/OPS/DIC). It generates spectrals, gathers metadata, allows re-tagging/renaming files, and automates the upload process.

## Features

- **Interactive Uploading** - Supports multiple trackers (RED / OPS / DIC)
- **Log Checking** - Validates log scores, checksum integrity, and log-to-FLAC matching
- **Upconvert Detection** - Checks 24-bit FLAC files for potential upconverts
- **MQA Detection** - Checks files for common MQA markers
- **Duplicate Upload Detection** - Prevents redundant uploads
- **Spectral Analysis** - Generates, compresses, and verifies spectrals (web interface at http://nas-ip:55110/spectrals)
- **Metadata Retrieval** - Fetches metadata from: Bandcamp, Beatport, **Deezer**, Discogs, iTunes, JunoDownload, MusicBrainz, Qobuz, Tidal
- **File Management** - Retags and renames files to standard formats
- **Multi-Format Upload** - Automatically transcodes and uploads multiple formats (FLAC 16-bit, MP3 320, V0)
- **Torrent Client Integration** - Can inject torrents into qBittorrent, Transmission, Deluge, ruTorrent
- **Request Filling** - Scans for matching requests on trackers

## Initial Setup

### 1. Create Config Directory

```bash
mkdir -p /volume2/docker/appdata/smoked-salmon/{config,data,torrents}
```

### 2. Deploy the Container

```bash
cd services/torrents/smoked-salmon
docker-compose up -d
```

### 3. Generate Default Configuration

Connect to the container and generate the default config:

```bash
docker exec -it smoked-salmon /bin/sh
.venv/bin/salmon
```

This will prompt you to create a default config file. Follow the instructions.

### 4. Configure smoked-salmon

Copy the default config:

```bash
docker exec smoked-salmon cp /root/.config/smoked-salmon/config.default.toml /root/.config/smoked-salmon/config.toml
```

Edit the config file on your host:

```bash
nano /volume2/docker/appdata/smoked-salmon/config/config.toml
```

**Required Configuration:**

```toml
# API Keys
[RED]
api_key = "YOUR_RED_API_KEY"
session_cookie = "YOUR_RED_SESSION_COOKIE"

[OPS]
api_key = "YOUR_OPS_API_KEY"
session_cookie = "YOUR_OPS_SESSION_COOKIE"

# Torrent client (optional but recommended)
[qBittorrent]
host = "http://qbit-main:8080"  # Or your qBittorrent host
username = "admin"
password = "your_password"

# Paths (already set by Docker volumes)
[Paths]
dottorrents_dir = "/app/.torrents"
```

See the [Configuration Wiki](https://github.com/smokin-salmon/smoked-salmon/wiki/Configuration) for all options.

### 5. Initialize Database

```bash
docker exec smoked-salmon .venv/bin/salmon migrate
```

### 6. Verify Configuration

Check tracker connections:

```bash
docker exec smoked-salmon .venv/bin/salmon checkconf
```

Check dependencies:

```bash
docker exec smoked-salmon .venv/bin/salmon health
```

## Usage

### Upload an Album

**Basic upload (interactive mode):**

```bash
docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Artist - Album" -s WEB
```

**Common options:**

```bash
# Upload with specific source
docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Album" -s WEB

# Skip spectral generation
docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Album" -s WEB --no-spectrograms

# Auto-fill requests
docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Album" -s WEB --fill-requests

# Upload to specific tracker
docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Album" -s WEB --tracker OPS
```

**Get full help:**

```bash
docker exec smoked-salmon .venv/bin/salmon up --help
```

### Supported Sources

- `WEB` - For Deezer, Qobuz, Tidal, etc.
- `CD` - For CD rips
- `Vinyl` - For vinyl rips
- `DVD` - For DVD audio
- `Blu-ray` - For Blu-ray audio
- `SACD` - For SACD rips
- `WEB-DL` - Direct web downloads

### Typical Workflow for Deemix Downloads

1. **Download FLAC from Deemix** to `/volume2/downloads/music/content/deemix/Artist - Album`

2. **Upload with smoked-salmon:**
   ```bash
   docker exec -it smoked-salmon .venv/bin/salmon up "/app/.music/deemix/Artist - Album" -s WEB
   ```

3. **Follow the interactive prompts:**
   - Choose metadata source (Deezer, MusicBrainz, etc.)
   - Verify/edit metadata
   - Select formats to transcode (FLAC 16, MP3 320, V0)
   - Select tracker (OPS, RED, etc.)
   - Review and confirm upload

4. **Generated files:**
   - Transcoded files: `/volume2/downloads/music/uploaded/`
   - .torrent files: `/volume2/docker/appdata/smoked-salmon/torrents/`

## Web Interface

Access the spectral viewer at:

```
http://YOUR_NAS_IP:55110/spectrals
```

This displays generated spectrograms for quality verification.

## Directory Structure

- `/app/.music` - Source FLAC files (read-only, mounted from `${DOWNLOAD_PATH}/music/content`)
- `/app/.uploaded` - Transcoded output files (`${DOWNLOAD_PATH}/music/uploaded`)
- `/app/.torrents` - Generated .torrent files
- `/root/.config/smoked-salmon/` - Configuration files
- `/root/.local/share/smoked-salmon/` - Database

## Volume Paths

- **Music source**: `${DOWNLOAD_PATH}/music/content` → `/app/.music`
- **Config**: `${DOCKER_APPDATA_PATH}/smoked-salmon/config` → `/root/.config/smoked-salmon`
- **Database**: `${DOCKER_APPDATA_PATH}/smoked-salmon/data` → `/root/.local/share/smoked-salmon`
- **Torrents**: `${DOCKER_APPDATA_PATH}/smoked-salmon/torrents` → `/app/.torrents`
- **Uploads**: `${DOWNLOAD_PATH}/music/uploaded` → `/app/.uploaded`

## Troubleshooting

### Permission Issues

If you encounter permission errors, ensure the container user matches your file ownership:

```bash
chown -R 1026:100 /volume2/docker/appdata/smoked-salmon
chown -R 1026:100 /volume2/downloads/music/uploaded
```

### Config File Not Found

If salmon can't find the config:

```bash
# Check if config exists
docker exec smoked-salmon ls -la /root/.config/smoked-salmon/

# Copy default config if needed
docker exec smoked-salmon cp /root/.config/smoked-salmon/config.default.toml /root/.config/smoked-salmon/config.toml
```

### Database Migration Errors

If migration fails, remove the database and recreate:

```bash
docker exec smoked-salmon rm /root/.local/share/smoked-salmon/smoked.db
docker exec smoked-salmon .venv/bin/salmon migrate
```

## Updating

Pull the latest image and recreate:

```bash
cd services/torrents/smoked-salmon
docker-compose pull
docker-compose up -d
```

## Links

- **GitHub**: https://github.com/smokin-salmon/smoked-salmon
- **Wiki**: https://github.com/smokin-salmon/smoked-salmon/wiki
- **Docker Image**: ghcr.io/smokin-salmon/smoked-salmon:latest

## Notes

- The web interface (spectral viewer) runs on port 55110
- Smoked-salmon is designed for interactive use - most commands require user input
- For Deezer downloads, always use `-s WEB` as the source
- The tool can automatically fetch metadata from Deezer API if configured
