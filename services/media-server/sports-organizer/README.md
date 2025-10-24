# Sports Organizer

Sports Organizer is a Python-based service that automatically organizes sports content from download directories into properly structured folders for Plex. It monitors a source directory for new sports content and moves it to the appropriate destination directory with proper naming conventions.

## Overview

This service watches the sports downloads directory and automatically organizes files into the Plex sports library structure, ensuring content is properly categorized and named for optimal Plex recognition.

## Configuration

The service is configured through environment variables in the `.env` file:

- **Source Directory**: `/data/medias/downloads/torrents/complete/sports`
- **Destination Directory**: `/data/medias/sports`
- **Process Interval**: 60 seconds (default)
- **Pushover Notifications**: Disabled by default

## Features

- Automatic file organization from downloads to media library
- Configurable processing interval
- Optional Pushover notifications for processing events
- Debug mode for troubleshooting

## Documentation

For detailed information about Sports Organizer's functionality, configuration options, and usage:

**Project Repository**: [s0len/Sports-Organizer](https://github.com/s0len/Sports-Organizer)

## Related Services

- **Unpackerr**: Extracts compressed sports downloads before processing
- **Kometa**: Manages sports collections and metadata in Plex
- **Autopulse**: Handles automated Plex library management

## Deployment

```bash
cd services/media-server/sports-organizer
docker-compose up -d
```

## Monitoring

The service runs continuously and can be monitored via:
- Docker logs: `docker logs -f sports-organizer`
- Uptime Kuma (if configured)
- Optional Pushover notifications
