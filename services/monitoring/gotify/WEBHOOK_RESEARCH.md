# Webhook Payload Research

Research on what each homelab service sends via webhooks, for building a notification formatting middleware.

## Services With Raw Webhook Support

### Sonarr (Webhook notification type)

**Event types:** `Grab`, `Download` (import), `Rename`, `SeriesAdd`, `SeriesDelete`, `EpisodeFileDelete`, `Health`, `HealthRestored`, `ApplicationUpdate`, `ManualInteractionRequired`

**Base payload** (all events):
```json
{
  "eventType": "Grab|Download|...",
  "instanceName": "Sonarr",
  "applicationUrl": "http://10.10.2.2:8988"
}
```

**Grab payload:**
```json
{
  "series": {
    "id": 1,
    "title": "Breaking Bad",
    "titleSlug": "breaking-bad",
    "path": "/data/medias/tv/Breaking Bad",
    "tvdbId": 81189,
    "tvMazeId": 169,
    "tmdbId": 1396,
    "imdbId": "tt0903747",
    "type": "Standard",
    "year": 2008,
    "genres": ["Crime", "Drama", "Thriller"],
    "images": [
      {"coverType": "Banner", "url": "...", "remoteUrl": "https://artworks.thetvdb.com/..."},
      {"coverType": "Poster", "url": "...", "remoteUrl": "https://artworks.thetvdb.com/..."},
      {"coverType": "Fanart", "url": "...", "remoteUrl": "https://artworks.thetvdb.com/..."}
    ],
    "tags": [],
    "originalLanguage": {"id": 1, "name": "English"}
  },
  "episodes": [
    {
      "id": 1,
      "episodeNumber": 16,
      "seasonNumber": 5,
      "title": "Felina",
      "overview": "Episode synopsis text...",
      "airDate": "2013-09-29",
      "airDateUtc": "2013-09-30T01:00:00Z",
      "seriesId": 1,
      "tvdbId": 4639461,
      "finaleType": "series"
    }
  ],
  "release": {
    "quality": "Bluray-1080p",
    "qualityVersion": 1,
    "releaseGroup": "NTb",
    "releaseTitle": "Breaking.Bad.S05E16.1080p.BluRay.x264-NTb",
    "indexer": "Aither",
    "size": 4831838208,
    "customFormatScore": 150,
    "customFormats": ["Bluray Tier 01", "x264"],
    "languages": [{"id": 1, "name": "English"}],
    "indexerFlags": []
  },
  "downloadClient": "qBittorrent",
  "downloadClientType": "qBittorrent",
  "downloadId": "..."
}
```

**Import (Download) payload:**
Same as Grab but with `episodeFile` (file info, media info) and `isUpgrade` boolean.

**Health payload:**
```json
{
  "level": "Warning|Error",
  "message": "Description of the health issue",
  "type": "HealthCheckType",
  "wikiUrl": "https://wiki.servarr.com/..."
}
```

---

### Radarr (Webhook notification type)

**Event types:** `Grab`, `Download`, `Rename`, `MovieAdded`, `MovieDelete`, `MovieFileDelete`, `Health`, `HealthRestored`, `ApplicationUpdate`, `ManualInteractionRequired`

**Grab payload:**
```json
{
  "movie": {
    "id": 1,
    "title": "The Chaser",
    "year": 2008,
    "filePath": "/data/medias/movies/The Chaser (2008)/...",
    "releaseDate": "2008-06-13",
    "folderPath": "/data/medias/movies/The Chaser (2008)",
    "tmdbId": 17009,
    "imdbId": "tt1190539",
    "overview": "A disgraced former detective turned pimp...",
    "genres": ["Crime", "Drama", "Thriller"],
    "images": [
      {"coverType": "Poster", "url": "...", "remoteUrl": "https://image.tmdb.org/t/p/..."},
      {"coverType": "Fanart", "url": "...", "remoteUrl": "https://image.tmdb.org/t/p/..."}
    ],
    "tags": [],
    "originalLanguage": {"id": 1, "name": "English"}
  },
  "remoteMovie": {
    "tmdbId": 17009,
    "imdbId": "tt1190539",
    "title": "The Chaser",
    "year": 2008
  },
  "release": {
    "quality": "WEBDL-1080p",
    "qualityVersion": 1,
    "releaseGroup": "GPRS",
    "releaseTitle": "The.Chaser.2008.KOREAN.1080p.AMZN.WEB-DL.DD+5.1.H.264-GPRS",
    "indexer": "Aither",
    "size": 9663676416,
    "customFormatScore": 100,
    "customFormats": ["AMZN", "WEB Tier 02"],
    "languages": [{"id": 1, "name": "Korean"}],
    "indexerFlags": []
  },
  "downloadClient": "qBittorrent",
  "downloadClientType": "qBittorrent",
  "downloadId": "..."
}
```

**Import (Download) payload:**
Same as Grab but with `movieFile` (file info, media info) and `isUpgrade` boolean.

---

### Autobrr (Webhook notification type)

**Event types:** `release.new`, `action.approved`, `action.rejected`, `action.error`, `irc.disconnected`, `irc.reconnected`, `app.update_available`, `test`

**Payload structure:**
```json
{
  "event": "action.approved",
  "id": "uuid",
  "timestamp": "2026-02-07T...",
  "version": "1.0",
  "data": {
    "release": {
      "protocol": "torrent",
      "implementation": "irc",
      "name": "The.Chaser.2008.KOREAN.1080p.AMZN.WEB-DL.DD+5.1.H.264-GPRS",
      "title": "The Chaser",
      "sub_title": "",
      "year": 2008,
      "season": 0,
      "episode": 0,
      "resolution": "1080p",
      "source": "WEB-DL",
      "codec": ["H.264"],
      "audio": ["DD+ 5.1"],
      "audio_channels": "5.1",
      "group": "GPRS",
      "size": 9663676416,
      "category": "Movies",
      "origin": "Internal",
      "uploader": "username",
      "freeleech": true,
      "freeleech_percent": 100,
      "seeders": 42,
      "leechers": 5,
      "meta_imdb": "tt1190539",
      "info_url": "https://...",
      "download_url": "https://...",
      "dynamic_range": ["SDR"],
      "language": ["Korean"],
      "tags": [],
      "proper": false,
      "repack": false
    },
    "indexer": {
      "name": "Aither",
      "identifier": "aither",
      "identifier_external": "aither"
    },
    "filter": {
      "name": "radarr",
      "id": 5
    },
    "action": {
      "name": "Radarr Action",
      "type": "RADARR",
      "client": "Radarr"
    },
    "result": {
      "status": "PUSH_APPROVED",
      "rejections": [],
      "status_message": ""
    }
  }
}
```

Note: Autobrr's Gotify integration uses `MessageBuilderPlainText` (no formatting). The webhook type sends the full structured JSON above, which is much richer.

---

### Tautulli (Webhook notification agent)

Uses a fully customizable JSON body template. You define the payload shape using 100+ variables.

**Key available variables:**
- **Media:** `media_type`, `title`, `show_name`, `episode_name`, `season_num`, `episode_num`, `year`, `genres`, `content_rating`, `studio`, `summary`, `tagline`
- **Images:** `poster_url`, `poster_thumb`, `art`, `thumb`
- **Quality:** `video_full_resolution`, `video_codec`, `audio_codec`, `audio_channels`, `video_dynamic_range`
- **Stream:** `user`, `player`, `platform`, `device`, `transcode_decision`, `stream_bandwidth`
- **Links:** `plex_url`, `imdb_url`, `thetvdb_url`, `themoviedb_url`, `trakt_url`
- **Server:** `server_name`, `action` (event type)
- **Dates:** `datestamp`, `timestamp`

**Already sends markdown extra to Gotify** (`client::display: {contentType: "text/markdown"}`), but the message content is still plain text by default.

---

### Uptime Kuma (Webhook notification type)

**Payload:**
```json
{
  "heartbeat": {
    "monitorID": 1,
    "status": 1,
    "time": "2026-02-07T12:00:00Z",
    "msg": "200 - OK",
    "ping": 42,
    "important": true,
    "duration": 300,
    "retries": 0
  },
  "monitor": {
    "id": 1,
    "name": "plex",
    "description": "Plex Media Server",
    "url": "http://10.10.2.2:32400/web",
    "type": "http",
    "hostname": "10.10.2.2",
    "port": 32400,
    "active": true,
    "tags": [...]
  },
  "msg": "[plex] [✅ Up] 200 - OK"
}
```

Also supports `custom` body mode with template variables.

---

### Kometa (Raw webhook URL)

Supports plain webhook URLs in `config.yml`. Sends the full JSON payload directly.

**run_end payload:**
```json
{
  "event": "run_end",
  "start_time": "2026-02-07 03:00:19",
  "end_time": "2026-02-07 11:35:13",
  "run_time": "8:34:54",
  "collections_created": 8,
  "collections_modified": 1,
  "collections_deleted": 0,
  "items_added": 3,
  "items_removed": 0,
  "added_to_radarr": 0,
  "added_to_sonarr": 0
}
```

**changes payload (collection created/modified):**
```json
{
  "event": "changes",
  "server_name": "ds423plus",
  "library_name": "TV Shows",
  "collection": "Asian Collection",
  "created": false,
  "additions": [
    {"title": "Bloodhounds", "poster": "https://..."},
    {"title": "The Kidnapping Day", "poster": "https://..."}
  ],
  "removals": [],
  "radarr_adds": [],
  "sonarr_adds": []
}
```

**error payload:**
```json
{
  "event": "error",
  "error": "Error message",
  "critical": false,
  "server_name": "ds423plus",
  "library_name": "Movies",
  "collection": "Trending"
}
```

---

## Services WITHOUT Raw Webhook Support

### Beszel
Uses **Shoutrrr** URLs only (`gotify://`, `pushover://`, etc.). No way to configure a plain HTTP webhook endpoint. Alert data available: `title`, `message`, `link`, `linkText`.

### Watchtower
Uses **Shoutrrr** URLs only. Sends plain text update summaries. No raw webhook option.

---

## Pushover Formatting Options

When forwarding to Pushover via pushtify, these formatting options are available:
- `html=1`: Enables `<b>`, `<i>`, `<u>`, `<font color>`, `<a href>` in message body
- `url` + `url_title`: Supplementary clickable link below the message
- `sound`: Custom notification sound
- `monospace=1`: Fixed-width font

**Note:** HTML tags are stripped from the notification banner preview but render when the notification is opened in the Pushover app.

## Gotify Formatting Options

- `client::display` → `contentType: "text/markdown"`: Renders GitHub Flavored Markdown in the web UI
- `client::notification` → `bigImageUrl`: Large image in notification (Android only)
- `client::notification` → `click.url`: Opens URL on notification tap
