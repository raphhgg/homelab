# Apprise - Centralized Notification Hub

Unified notification system for sending alerts to Discord, Telegram, and 90+ other platforms.

## Overview

Apprise acts as the central notification hub for the homelab, providing a single API to send notifications to multiple platforms. This eliminates the need to configure individual notification services for each tool.

**Access**:
- **Web UI**: `http://ds423plus:8089` or `http://10.10.2.2:8089` (from network/browser)
- **API (from host)**: `http://localhost:8089`
- **API (from containers)**: `http://apprise:8000` (within Docker `main` network)

## Setup

### 1. Configure Notification Services

Copy the example configuration and add your service URLs:

```bash
cd /volume2/docker/compose/services/monitoring/apprise/config
cp apprise.yml.example apprise.yml
```

Edit `apprise.yml` and add your notification service URLs:

**Security Notes**:
- The config directory is local to the service (`./config`) rather than in appdata
- `apprise.yml` is gitignored and contains your webhook secrets
- Apprise does NOT support environment variable substitution in YAML (this is the standard approach)
- Set restrictive permissions: `chmod 600 config/apprise.yml`
- **Never commit `apprise.yml` to git!**

**Discord**:
1. Go to Discord Server Settings > Integrations > Webhooks
2. Create New Webhook, customize name and avatar, copy the URL
3. Extract WEBHOOK_ID and WEBHOOK_TOKEN from URL: `https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN`
4. Add to config with parameters:
   ```yaml
   - discord://WEBHOOK_ID/WEBHOOK_TOKEN?avatar=No&image=No&footer=No:
     - tag: watchtower, critical
   ```

   **URL Parameters**:
   - `avatar=No` - Use webhook's configured avatar (not Apprise's dynamic icons)
   - `image=No` - Don't include inline notification type image
   - `footer=No` - Don't add footer text
   - `tts=No` - Disable text-to-speech (default)

**Telegram**:
1. Message @BotFather on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Message your bot to activate it
5. Get chat_id: Visit `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
6. Add to config: `tgram://BOT_TOKEN/CHAT_ID`

### 2. Deploy Container

```bash
cd /volume2/docker/compose/services/monitoring/apprise
docker-compose up -d
```

### 3. Test Notification

```bash
# Test using stateful key (uses apprise.yml config)
curl -X POST http://localhost:8089/notify/apprise \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Notification",
    "body": "Apprise is working!",
    "tag": "watchtower"
  }'

# Test stateless (direct URL, no config needed)
curl -X POST http://localhost:8089/notify \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["discord://WEBHOOK_ID/WEBHOOK_TOKEN"],
    "title": "Test",
    "body": "Hello from Apprise!"
  }'
```

## Usage

### Stateful Mode (Recommended)

Uses the configuration from `/config/apprise.yml`:

```bash
# From within Docker network (other containers)
curl -X POST http://apprise:8000/notify/apprise \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Container Updated",
    "body": "Sonarr updated: v1.0 → v1.1",
    "format": "markdown",
    "tag": "watchtower"
  }'

# From host machine
curl -X POST http://localhost:8089/notify/apprise \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Container Updated",
    "body": "Sonarr updated: v1.0 → v1.1",
    "format": "markdown",
    "tag": "watchtower"
  }'
```

### Notification Tags

Tags defined in `apprise.yml` allow routing notifications to specific services:

- `watchtower` - Container update notifications
- `cronicle` - Scheduled job results
- `monitoring` - System alerts (Uptime Kuma, Beszel)
- `critical` - High-priority alerts
- `media` - Media server events

### API Endpoints

- `POST /notify/apprise` - Send using config file
- `POST /notify` - Send with inline URLs (stateless)
- `GET /json/urls/apprise` - View configured URLs

## Integration Examples

### Watchtower (via Cronicle)

See updated Cronicle job "Watchtower - Daily Update Check" that parses output and sends Apprise notifications.

### Uptime Kuma

Uptime Kuma has built-in Apprise support:
1. Go to Settings > Notifications
2. Setup Type: Apprise (url)
3. Apprise URL: `http://apprise:8000/notify/apprise`
4. Set as Default

### Cronicle Jobs

Add to job's script:

```bash
# On success
curl -X POST http://apprise:8000/notify/apprise \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Job Complete\",\"body\":\"$JOB_NAME completed successfully\",\"tag\":\"cronicle\"}"

# On failure
curl -X POST http://apprise:8000/notify/apprise \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Job Failed\",\"body\":\"$JOB_NAME failed\",\"tag\":\"critical\"}"
```

### Shell Scripts

```bash
#!/bin/bash
RESULT=$(run_backup.sh 2>&1)
if [ $? -eq 0 ]; then
  curl -s -X POST http://apprise:8000/notify/apprise \
    -H "Content-Type: application/json" \
    -d '{"title":"✅ Backup Complete","body":"'"$RESULT"'","tag":"monitoring"}'
fi
```

## Current Integrations

- **Watchtower**: Container update notifications (Tier 1 auto-updates + Tier 2 available updates)
- **Uptime Kuma**: Service down/up alerts (planned)
- **Cronicle**: Scheduled job results (planned)
- **Beszel**: Resource threshold alerts (planned)

## Configuration

### Environment Variables

- `APPRISE_STATEFUL_MODE=simple` - Maps keys to config files
- `APPRISE_WORKER_COUNT=1` - Lightweight for homelab
- `APPRISE_DEFAULT_THEME=dark` - UI theme

### File Locations

- Config: `${DOCKER_APPDATA_PATH}/apprise/config/apprise.yml`
- Attachments: `${DOCKER_APPDATA_PATH}/apprise/attach/`

## Monitoring

Apprise is monitored by Uptime Kuma:
- **Monitor type**: HTTP
- **URL**: `http://apprise:8000`
- **Check interval**: 120 seconds
- **Watchtower**: Auto-update enabled (Tier 1)

## Troubleshooting

### Check container logs

```bash
docker-compose logs -f apprise-api
```

### Verify configuration

```bash
# View configured URLs (returns JSON)
curl http://localhost:8000/json/urls/apprise | python3 -m json.tool
```

### Test specific service

```bash
# Test Discord
curl -X POST http://localhost:8000/notify \
  -H "Content-Type: application/json" \
  -d '{"urls":["discord://WEBHOOK_ID/TOKEN"],"title":"Test","body":"Hello"}'

# Test Telegram
curl -X POST http://localhost:8000/notify \
  -H "Content-Type: application/json" \
  -d '{"urls":["tgram://BOT_TOKEN/CHAT_ID"],"title":"Test","body":"Hello"}'
```

### Common Issues

**Notifications not sending**:
- Check `apprise.yml` syntax
- Verify service URLs are correct
- Check container logs for errors
- Test with stateless mode to isolate config issues

**Permission errors**:
```bash
# Fix config directory permissions
chown -R 1000:1000 /volume2/docker/appdata/apprise/config
chmod -R 775 /volume2/docker/appdata/apprise/config
```

## Resources

- [Official Documentation](https://github.com/caronc/apprise)
- [Apprise API Documentation](https://github.com/caronc/apprise-api)
- [Config YAML Format](https://github.com/caronc/apprise/wiki/config_yaml)
- [Telegram Setup](https://github.com/caronc/apprise/wiki/Notify_telegram)
- [Discord Setup](https://github.com/caronc/apprise/wiki/Notify_discord)
- [Supported Services](https://github.com/caronc/apprise/wiki#notification-services)
