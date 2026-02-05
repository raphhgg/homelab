# Gotify

Self-hosted push notification server for mobile and desktop notifications.

## Overview

Gotify is the central notification hub, providing:
- Native mobile app (Android via Play Store/F-Droid, iOS via Pushover+Pushtify)
- Web UI for viewing all notifications
- Simple REST API for sending messages
- Per-service application organization with separate tokens and icons

## Architecture

```
┌─────────────────┐     ┌─────────┐     ┌──────────┐
│ Services        │────►│ Gotify  │────►│ Pushtify │────► Pushover (iOS)
│ (Sonarr, etc.)  │     │         │     └──────────┘
└─────────────────┘     │         │────► Android App
                        │         │────► Web UI
                        └─────────┘
```

## Quick Start

1. Copy `.env.example` to `.env` and configure
2. Deploy: `docker-compose up -d`
3. Access UI: `http://10.10.2.2:8093`
4. Run `./setup_applications.sh` to create all apps with icons

## Applications & Tokens

Per-service applications with icons (created via setup script):

### Monitoring (Priority 8 - High)
| Application | Token | Use For |
|-------------|-------|---------|
| uptime-kuma | `A7Mt4oo1Tpf1.2h` | Service availability alerts |
| beszel | `AUUlViIRVi1R3nb` | Hardware/resource alerts |
| watchtower | `A7TOa4DIExYNniy` | Container update notifications |
| netronome | `AohAP..m8cRlulp` | Network monitoring |

### Arrs (Priority 5 - Normal)
| Application | Token | Use For |
|-------------|-------|---------|
| sonarr | `AV8NuUuIPzSyBwG` | TV show grabs/imports |
| radarr | `A8YLFLcNDsnwR6A` | Movie grabs/imports |
| prowlarr | `AWQaRT8B537e.HQ` | Indexer events |
| bazarr | `AUs_Uat4uMApTfM` | Subtitle downloads |

### Media Server (Priority 5 - Normal)
| Application | Token | Use For |
|-------------|-------|---------|
| tautulli | `ADVHQeQc4SBls5_` | Plex activity |
| jellyseerr | `ArG-liIsG6Ggk5h` | Media requests |
| kometa | `AbWOcqwd7SO4bAu` | Library updates |
| plex | `AvFS5o-3g-0G8mb` | Plex server alerts |

### Torrents (Priority 5 - Normal)
| Application | Token | Use For |
|-------------|-------|---------|
| autobrr | `AWWIS.x3hHK3WAx` | Release automation |
| qbittorrent | `AxCQKo1XYs4Sxl1` | Torrent completions |

### System (Priority 9 - Critical)
| Application | Token | Use For |
|-------------|-------|---------|
| synology | `AM9EE_qRoCmBjQy` | DSM alerts, manual notifications |

## Priority Levels

| Priority | Gotify | Pushover | Use Case |
|----------|--------|----------|----------|
| 0 | Silent | Lowest | Logged only |
| 1-3 | Low | Low | Informational |
| 4-7 | Normal | Normal | Downloads, updates |
| 8-10 | High | High (bypasses DND) | Service down, critical |

## Service Configuration

### Shoutrrr Format (Beszel, Watchtower)
```
gotify://gotify:80/TOKEN?priority=8&disabletls=yes
```

### Uptime Kuma
Settings > Notifications > Add > Gotify:
- Server URL: `http://gotify:80`
- Token: `A7Mt4oo1Tpf1.2h`
- Priority: 8

### Beszel
Settings > Notifications:
```
gotify://gotify:80/AUUlViIRVi1R3nb?priority=8&disabletls=yes
```

### Sonarr/Radarr
Settings > Connect > Add > Gotify:
- Server: `http://gotify:80`
- Token: (use sonarr/radarr token from table)
- Priority: 5

### Tautulli
Settings > Notification Agents > Add > Gotify:
- Gotify URL: `http://gotify:80`
- API Key: `ADVHQeQc4SBls5_`

### Autobrr
Settings > Notifications > Add > Gotify:
- Host: `http://gotify:80`
- Token: `AWWIS.x3hHK3WAx`
- Priority: 5

## iOS Push Notifications (Pushtify + Pushover)

Since Gotify doesn't natively support iOS push, we use Pushtify to bridge to Pushover:

1. Install [Pushover app](https://pushover.net/) on iOS ($5 one-time)
2. Get your User Key from Pushover dashboard
3. Create a Gotify **Client** (not Application) for Pushtify
4. Configure in `.env`:
   ```
   GOTIFY_CLIENT_TOKEN=<client_token>
   PUSHOVER_USERKEY=<your_pushover_user_key>
   ```

## API Usage

```bash
# Send test notification
curl "http://10.10.2.2:8093/message?token=AM9EE_qRoCmBjQy" \
  -F "title=Test" \
  -F "message=Hello from Gotify!" \
  -F "priority=5"
```

## Troubleshooting

### Shoutrrr "HTTP response to HTTPS client" error
Add `&disabletls=yes` to the URL:
```
gotify://gotify:80/TOKEN?priority=8&disabletls=yes
```

### Notifications not forwarded to Pushover
1. Check Pushtify logs: `docker logs pushtify`
2. Verify GOTIFY_CLIENT_TOKEN is a **Client** token, not an Application token
3. Verify PUSHOVER_USERKEY is correct

## References

- [Gotify Documentation](https://gotify.net/docs/)
- [Shoutrrr Gotify](https://containrrr.dev/shoutrrr/v0.8/services/gotify/)
- [Pushtify](https://github.com/sebw/pushtify)
- [Pushover](https://pushover.net/)
