#!/bin/bash
set -e

service=$1

echo "🔧 Running default tests for $service..."

# Basic container health check
if docker-compose ps | grep -q "Up"; then
    echo "✅ $service container is running"
else
    echo "❌ $service container is not running"
    exit 1
fi

# Check if container has health check defined
# Use the service name as container name (matches container_name in compose files)
full_container_name="$service"

if docker inspect "$full_container_name" 2>/dev/null | grep -q "Health"; then
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$full_container_name" 2>/dev/null || echo "unknown")
    echo "ℹ️  $service health status: $health_status"
    
    if [ "$health_status" = "unhealthy" ]; then
        echo "❌ $service is unhealthy"
        exit 1
    fi
fi

# Check if container can write to config directory (if it exists)
if docker exec "$full_container_name" test -d /config 2>/dev/null; then
    if docker exec "$full_container_name" touch /config/test-write 2>/dev/null && docker exec "$full_container_name" rm /config/test-write 2>/dev/null; then
        echo "✅ $service config directory is writable"
    else
        echo "⚠️  $service config directory may not be writable"
    fi
fi

# Basic connectivity test - check if any ports are exposed
exposed_ports=$(docker-compose port 2>/dev/null | head -1 || echo "")
if [ -n "$exposed_ports" ]; then
    echo "ℹ️  $service has exposed ports: $exposed_ports"
else
    echo "ℹ️  $service has no exposed ports"
fi

echo "ℹ️  Default tests completed - consider adding specific tests at scripts/tests/${service}.sh" 