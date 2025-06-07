#!/bin/bash
set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <service_name>"
    echo "Example: $0 plex"
    exit 1
fi

SERVICE_NAME=$1
COMPOSE_DIR="/volume2/docker/compose"
APPDATA_DIR="/volume2/docker/appdata"
SERVICE_PATH="services/$SERVICE_NAME"

if [ ! -d "$SERVICE_PATH" ]; then
    echo "Error: Service directory $SERVICE_PATH does not exist"
    exit 1
fi

if [ ! -f "$SERVICE_PATH/docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found in $SERVICE_PATH"
    exit 1
fi

echo "Deploying $SERVICE_NAME..."

# Create appdata directory if it doesn't exist
mkdir -p "$APPDATA_DIR/$SERVICE_NAME"

# Copy compose file to NAS
cp "$SERVICE_PATH/docker-compose.yml" "$COMPOSE_DIR/$SERVICE_NAME.yml"

# Deploy the service
cd "$COMPOSE_DIR"
docker-compose -f "$SERVICE_NAME.yml" down
docker-compose -f "$SERVICE_NAME.yml" pull
docker-compose -f "$SERVICE_NAME.yml" up -d

echo "$SERVICE_NAME deployed successfully!" 