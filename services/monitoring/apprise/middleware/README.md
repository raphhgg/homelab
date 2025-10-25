# Apprise Middleware

A lightweight Flask service that transforms monitoring webhook payloads into Apprise API-compatible format for rich Discord notifications.

## Overview

This middleware acts as a bridge between monitoring services (Uptime Kuma, Beszel) and the Apprise notification system. It normalizes different webhook formats into a consistent structure that Apprise can process and route to various notification channels (Discord, Telegram, email, etc.).

## Architecture

```
Monitoring Service → Middleware Webhook → Apprise API → Notification Channels
                     (Transform)          (Route)       (Discord, etc.)
```

### Why Middleware?

- **Format Incompatibility**: Monitoring services send webhooks in their own format, incompatible with Apprise API
- **Enrichment**: Adds emojis, formatting, severity mapping, and rich markdown for better notifications
- **Centralization**: Single transformation layer for multiple monitoring services
- **Flexibility**: Easy to add new monitoring services without modifying Apprise configuration

## Supported Services

### 1. Uptime Kuma

**Endpoint**: `POST /webhook/uptime-kuma`

**Webhook URL**: `http://apprise-middleware:5000/webhook/uptime-kuma`

**Input Format** (Uptime Kuma payload):
```json
{
  "heartbeat": {
    "status": 1,
    "msg": "Error message (if down)",
    "duration": 123,
    "localDateTime": "2025-01-24 10:30:00",
    "time": "2025-01-24T09:30:00Z"
  },
  "monitor": {
    "name": "Plex",
    "type": "http",
    "url": "http://10.10.2.2:32400"
  },
  "msg": "Service is up/down"
}
```

**Transformation**:
- Extracts monitor name, type, URL, status, error message, duration
- Maps status to Apprise type: `1=success`, `0=failure`, `other=warning`
- Adds status emojis: 🟢 (UP), 🔴 (DOWN), 🟡 (UNKNOWN)
- Creates rich markdown body with all relevant details
- Tags: `uptime-kuma`

**Output Format** (sent to Apprise):
```json
{
  "title": "🟢 Plex is UP",
  "body": "**Status:** UP\n**Monitor:** Plex\n**Type:** HTTP\n**URL:** http://10.10.2.2:32400\n**Duration:** 123ms\n**Time:** 2025-01-24 10:30:00",
  "type": "success",
  "format": "markdown",
  "tag": "uptime-kuma"
}
```

### 2. Beszel

**Endpoint**: `POST /webhook/beszel`

**Webhook URL**: `http://apprise-middleware:5000/webhook/beszel`

**Input Format** (Beszel payload):
```json
{
  "title": "NAS CPU above threshold",
  "message": "CPU averaged 75.3% for the previous 10 minutes."
}
```

**Transformation**:
- Extracts title and message from Beszel alert
- All alerts are marked as **Critical** (🔴 red) since Beszel only sends alerts when thresholds are exceeded
- Creates formatted title with red emoji
- Tags: `beszel`, `critical`

**Output Format** (sent to Apprise):
```json
{
  "title": "🔴 NAS CPU above threshold",
  "body": "CPU averaged 75.3% for the previous 10 minutes.",
  "type": "failure",
  "format": "markdown",
  "tag": ["beszel", "critical"]
}
```

**Note**: All Beszel alerts are treated as critical (red) since Beszel only sends alerts when configured thresholds are exceeded.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APPRISE_URL` | `http://apprise:8000` | Apprise API base URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Docker Setup

The middleware runs as a Flask application in a Docker container:

```yaml
services:
  apprise-middleware:
    build: ./middleware
    container_name: apprise-middleware
    networks:
      - main
    environment:
      - APPRISE_URL=http://apprise:8000
      - LOG_LEVEL=INFO
    restart: always
```

## API Endpoints

### `POST /webhook/uptime-kuma`

Receives Uptime Kuma webhook payloads.

**Request**:
```bash
curl -X POST http://apprise-middleware:5000/webhook/uptime-kuma \
  -H "Content-Type: application/json" \
  -d '{"heartbeat": {...}, "monitor": {...}}'
```

**Response**:
```json
{
  "status": "success",
  "message": "Notification forwarded to Apprise"
}
```

### `POST /webhook/beszel`

Receives Beszel webhook payloads.

**Request**:
```bash
curl -X POST http://apprise-middleware:5000/webhook/beszel \
  -H "Content-Type: application/json" \
  -d '{"title": "Alert title", "message": "Alert message"}'
```

**Response**:
```json
{
  "status": "success",
  "message": "Notification forwarded to Apprise"
}
```

### `GET /health`

Health check endpoint for monitoring.

**Response**:
```json
{
  "status": "healthy",
  "service": "apprise-middleware",
  "timestamp": "2025-01-24T10:30:00.123456"
}
```

### `GET /`

Service information and available endpoints.

**Response**:
```json
{
  "service": "Apprise Middleware",
  "version": "2.0.0",
  "description": "Transforms monitoring webhook payloads (Uptime Kuma, Beszel) to Apprise API format",
  "endpoints": {
    "POST /webhook/uptime-kuma": "Receive Uptime Kuma webhooks",
    "POST /webhook/beszel": "Receive Beszel webhooks",
    "GET /health": "Health check endpoint",
    "GET /": "Service information"
  }
}
```

## Setting Up Webhooks

### Uptime Kuma Configuration

1. Go to **Settings** → **Notifications** in Uptime Kuma
2. Create new notification:
   - **Notification Type**: Webhook
   - **Friendly Name**: `Apprise (uptime-kuma - Middleware)`
   - **Post URL**: `http://apprise-middleware:5000/webhook/uptime-kuma`
   - **Content Type**: `application/json`
3. Set as **Default** to apply to all monitors
4. Apply to existing monitors via bulk edit

### Beszel Configuration

1. Go to **Settings** → **Notifications** in Beszel Hub
2. Add notification URL using Shoutrrr generic webhook:
   ```
   generic://apprise-middleware:5000/webhook/beszel?template=json
   ```
3. Enable alerts for systems in the systems table
4. Configure alert thresholds (CPU, memory, disk, etc.)

**Recommended Alert Thresholds**:
- **Disk space**: 95%
- **CPU sustained usage**: 80%+
- **Memory usage**: 90%+
- **Temperature**: 70°C+ (if available)

## Logging

The middleware logs all webhook activities with timestamps:

**View logs**:
```bash
docker logs -f apprise-middleware
```

**Sample logs**:
```
2025-01-24 10:30:00 - __main__ - INFO - Received Uptime Kuma webhook payload: {...}
2025-01-24 10:30:00 - __main__ - INFO - Transformed payload for monitor 'Plex' (status: UP)
2025-01-24 10:30:00 - __main__ - INFO - Forwarding notification to Apprise: http://apprise:8000/notify/uptime-kuma
2025-01-24 10:30:00 - __main__ - INFO - Notification sent to Apprise successfully
```

## Error Handling

The middleware includes comprehensive error handling:

- **Empty payload**: Returns `400 Bad Request`
- **Transformation errors**: Logged with full stack trace
- **Apprise connection failures**: Returns `502 Bad Gateway`
- **Apprise errors**: Logged with status code and response text
- **Internal errors**: Returns `500 Internal Server Error`

## Troubleshooting

### Webhook not received

1. Check middleware logs: `docker logs apprise-middleware`
2. Verify network connectivity: `docker exec <service> ping apprise-middleware`
3. Ensure correct webhook URL (use internal port 5000, not external)

### Notification not sent to Discord

1. Check middleware logs for Apprise forwarding
2. Verify Apprise configuration and tags match
3. Check Apprise logs: `docker logs apprise`
4. Test Apprise directly:
   ```bash
   curl -X POST http://apprise:8000/notify/beszel \
     -H "Content-Type: application/json" \
     -d '{"title":"Test","body":"Test message","tag":"beszel"}'
   ```

### Severity not detected correctly (Beszel)

The severity detection uses keyword matching. If alerts are not categorized correctly:

1. Check the keywords in the transformation function
2. Update the keyword lists in `transform_beszel_payload()` function
3. Restart middleware: `docker restart apprise-middleware`

## Development

### Project Structure

```
middleware/
├── app.py              # Main Flask application
├── Dockerfile          # Container image definition
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

### Adding New Monitoring Services

To add support for a new monitoring service:

1. Create transformation function in `app.py`:
   ```python
   def transform_<service>_payload(payload):
       # Extract data from service-specific format
       # Map to Apprise format
       return apprise_payload
   ```

2. Add webhook endpoint:
   ```python
   @app.route("/webhook/<service>", methods=["POST"])
   def <service>_webhook():
       payload = request.get_json()
       apprise_payload = transform_<service>_payload(payload)
       # Forward to Apprise
       return jsonify({"status": "success"})
   ```

3. Update index endpoint to document new service
4. Update this README
5. Rebuild and restart: `docker-compose up -d --build`

### Testing

**Manual webhook test**:
```bash
# Test Uptime Kuma endpoint
curl -X POST http://localhost:5000/webhook/uptime-kuma \
  -H "Content-Type: application/json" \
  -d '{"heartbeat":{"status":0},"monitor":{"name":"Test"}}'

# Test Beszel endpoint
curl -X POST http://localhost:5000/webhook/beszel \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Alert","message":"CPU above threshold"}'
```

## Resources

- **Apprise Documentation**: https://github.com/caronc/apprise
- **Uptime Kuma Webhook Format**: https://github.com/louislam/uptime-kuma/wiki/Notification-Methods#webhook
- **Beszel Notifications**: https://beszel.dev/guide/notifications/generic
- **Shoutrrr (Beszel backend)**: https://containrrr.dev/shoutrrr/
