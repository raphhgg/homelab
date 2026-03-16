# Gotify

Self-hosted push notification server. Central hub for all homelab service notifications.

## Architecture

```
Services ──► Gotify ──► Pushtify ──► Pushover (iOS)
                   ├──► Android App
                   └──► Web UI
```

- **Gotify**: receives notifications from all services via REST API
- **Pushtify**: listens to Gotify's WebSocket stream and forwards to Pushover for iOS push notifications
- **Gotify Middleware**: reformats webhook payloads (Sonarr, Radarr, Autobrr) into richer Gotify messages with posters

## Priority System

### Gotify Priorities (0-10)

Gotify uses a numeric scale. Pushtify maps these to Pushover priorities:

| Gotify | → Pushover | Pushover Name | Behavior |
|--------|------------|---------------|----------|
| 0      | -1         | Low           | No sound/vibration, appears in notification list only |
| 1-3    | 0          | **Normal**    | Standard notification with sound, respects quiet hours |
| 4-7    | 1          | High          | Bypasses quiet hours (Do Not Disturb) |
| 8-10   | 2          | Emergency     | Repeats every 60s until manually acknowledged |

### App Priority Assignments

**Priority 3** (Pushover Normal) — infrastructure monitoring, you want to notice these:

| App | Description |
|-----|-------------|
| uptime-kuma | Service availability alerts |

**Priority 1** (Pushover Normal) — informational, everything else:

| App | Description |
|-----|-------------|
| watchtower | Container updates |
| sonarr | TV show grabs/imports |
| radarr | Movie grabs/imports |
| prowlarr | Indexer events |
| bazarr | Subtitle downloads |
| tautulli | Plex activity |
| jellyseerr | Media requests |
| kometa | Library metadata updates |
| plex | Plex server alerts |
| autobrr | Release automation |
| synology | DSM alerts |

Both tiers map to Pushover Normal (sound, respects quiet hours). The split allows future differentiation if needed.

## Pushtify (Gotify → Pushover Bridge)

Pushtify connects to Gotify's WebSocket and forwards messages to Pushover for iOS push notifications.

Per-app Pushover tokens are configured in `.env` using the naming convention `<APPNAME>_PUSHOVER_TOKEN`. Create Pushover apps at https://pushover.net/apps.

Apps without a token are silently skipped (unless `PUSHOVER_DEFAULT_TOKEN` is set as fallback).

## Service Configuration Examples

### Shoutrrr (Watchtower)
```
gotify://gotify:80/TOKEN?disabletls=yes
```
Priority is controlled by the Gotify app's `defaultPriority`, not the Shoutrrr URL.

### Sonarr / Radarr
Settings → Connect → Gotify:
- Server: `http://gotify:80`
- Token: use the app token from Gotify UI

### Uptime Kuma
Settings → Notifications → Gotify:
- Server URL: `http://gotify:80`
- Token: use the app token from Gotify UI

## Troubleshooting

- **Shoutrrr "HTTP response to HTTPS client"**: add `&disabletls=yes` to the URL
- **Notifications not on iOS**: check `docker logs pushtify` — verify the app is "mapped" at startup
- **Pushover "expire must be supplied"**: Gotify priority 8+ maps to Pushover Emergency which requires retry/expire (handled by Pushtify)
