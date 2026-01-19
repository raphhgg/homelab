# Lettarrboxd

Automatically sync movies from your Letterboxd watchlist to Radarr.

## Overview

Lettarrboxd monitors Letterboxd lists (watchlists, custom lists) and automatically adds new movies to Radarr. It tracks previously synced movies to avoid duplicate API calls and checks for updates at configurable intervals.

## Configuration

### Required Environment Variables

- `LETTERBOXD_URL`: Your Letterboxd list URL (e.g., `https://letterboxd.com/username/watchlist/`)
  - Must be a **public** list (private lists cannot be scraped)
  - Supports watchlists and custom lists
- `RADARR_API_URL`: Your Radarr instance URL (e.g., `http://radarr:7878`)
- `RADARR_API_KEY`: API key from Radarr (Settings → General → Security → API Key)
- `RADARR_QUALITY_PROFILE`: Quality profile name in Radarr (e.g., `HD-1080p`, `Ultra-HD`)

### Optional Environment Variables

- `RADARR_ROOT_FOLDER_ID`: Specific root folder ID in Radarr (default: 1)
  - Find in Radarr: Settings → Media Management → Root Folders
- `CHECK_INTERVAL_MINUTES`: How often to check for updates (default: 10, minimum: 10)
- `RADARR_MINIMUM_AVAILABILITY`: When movie becomes available (default: `released`)
  - Options: `announced`, `inCinemas`, `released`, `preDB`
- `RADARR_ADD_UNMONITORED`: Add movies as unmonitored (default: `false`)
- `RADARR_TAGS`: Comma-separated tags to add to movies in Radarr
- `DRY_RUN`: Test mode - scrapes list but doesn't add to Radarr (default: `false`)

## Setup

1. Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cd services/media-server/lettarrboxd
   cp .env.example .env
   nano .env  # or vim, code, etc.
   ```

2. **Get your Letterboxd list URL:**
   - Go to your Letterboxd watchlist or custom list
   - Copy the full URL (e.g., `https://letterboxd.com/username/watchlist/`)
   - **Important**: The list must be public!

3. **Get your Radarr API key:**
   - Open Radarr web UI
   - Go to Settings → General → Security
   - Copy the API Key

4. **Find your Radarr Quality Profile name:**
   - Open Radarr web UI
   - Go to Settings → Profiles
   - Copy the exact name of your desired quality profile

5. **Find your Radarr Root Folder ID (optional):**
   - Open Radarr web UI
   - Go to Settings → Media Management → Root Folders
   - The ID is shown in the UI or can be found via API: `GET /api/v3/rootfolder`

6. Deploy the service:
   ```bash
   docker-compose up -d
   ```

7. Check logs to verify it's working:
   ```bash
   docker-compose logs -f
   ```

## Usage

Once running, Lettarrboxd will:
1. Check your Letterboxd list every `CHECK_INTERVAL_MINUTES` minutes (default: 10)
2. Identify new movies not yet in Radarr
3. Automatically add them with your configured quality profile and settings
4. Track synced movies to avoid duplicates

### Dry Run Mode

To test without adding movies to Radarr:
```bash
# Set in .env
DRY_RUN=true
```

This will scrape the list and log what would be added, but won't make any API calls to Radarr.

## Monitoring

View real-time logs:
```bash
docker-compose logs -f lettarrboxd
```

Check data directory (tracks synced movies):
```bash
ls -lh /volume2/docker/appdata/lettarrboxd/
```

## Troubleshooting

### Movies not being added

1. **Check logs**: `docker-compose logs -f lettarrboxd`
2. **Verify Letterboxd list is public**:
   - Private lists cannot be scraped
   - Go to list settings and make it public
3. **Verify Radarr connectivity**:
   ```bash
   docker exec lettarrboxd curl http://radarr:7878/api/v3/system/status -H "X-Api-Key: YOUR_API_KEY"
   ```
4. **Check quality profile name**: Must match exactly (case-sensitive)
5. **Enable dry run mode** to test scraping: `DRY_RUN=true`

### Container keeps restarting

1. Check environment variables are set correctly
2. Verify Radarr API key is valid
3. Check logs: `docker-compose logs lettarrboxd`

## Architecture

- **Language**: TypeScript/Node.js
- **Storage**: `/data` volume stores state (previously synced movies)
- **Network**: Uses `main` network to communicate with Radarr
- **Update Strategy**: Watchtower enabled for automatic updates

## Links

- **GitHub**: https://github.com/ryanpag3/lettarrboxd
- **Docker Hub**: https://hub.docker.com/r/ryanpage/lettarrboxd
- **Radarr**: http://radarr:7878
