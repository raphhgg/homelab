#!/bin/bash
set -e

COMPOSE_DIR="/volume2/docker/compose"
APPDATA_DIR="/volume2/docker/appdata"

# Function to deploy a single service
deploy_service() {
    local service_path=$1
    local service_name=$(basename "$service_path")
    
    echo "Deploying $service_name..."
    
    # Create appdata directory if it doesn't exist
    mkdir -p "$APPDATA_DIR/$service_name"
    
    # Copy compose file to NAS
    cp "$service_path/docker-compose.yml" "$COMPOSE_DIR/$service_name.yml"
    
    # Deploy the service
    cd "$COMPOSE_DIR"
    docker-compose -f "$service_name.yml" down
    docker-compose -f "$service_name.yml" pull
    docker-compose -f "$service_name.yml" up -d
    
    echo "$service_name deployed successfully!"
}

# Deploy all services or only changed ones
if [ "$GITHUB_EVENT_NAME" = "push" ]; then
    # Get changed files and deploy only affected services
    changed_services=$(git diff --name-only HEAD~1 HEAD | grep "^services/" | cut -d'/' -f2 | sort -u)
    
    if [ -n "$changed_services" ]; then
        for service in $changed_services; do
            if [ -d "services/$service" ]; then
                deploy_service "services/$service"
            fi
        done
    else
        echo "No service changes detected"
    fi
else
    # Deploy all services
    for service_dir in services/*/; do
        if [ -d "$service_dir" ]; then
            deploy_service "$service_dir"
        fi
    done
fi 