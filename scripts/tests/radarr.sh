#!/bin/bash
set -e

echo "🎬 Testing Radarr..."

# Wait for Radarr to start
echo "⏳ Waiting for Radarr to initialize..."
sleep 45

# Get the port
port=$(docker-compose port radarr 7878 2>/dev/null | cut -d':' -f2 || echo "7878")

# Test web interface
echo "🌐 Testing Radarr web interface..."
if curl -f -s --connect-timeout 10 "http://localhost:$port" > /dev/null; then
    echo "✅ Radarr web interface accessible on port $port"
else
    echo "❌ Radarr web interface not accessible on port $port"
    exit 1
fi

# Test API without authentication
echo "🔌 Testing Radarr API..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v3/system/status" > /dev/null; then
    echo "✅ Radarr API accessible"
else
    echo "ℹ️  Radarr API requires authentication (this is expected)"
fi

# Test health endpoint
echo "💊 Testing Radarr health..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v3/health" > /dev/null; then
    echo "✅ Radarr health endpoint accessible"
else
    echo "ℹ️  Radarr health endpoint requires authentication"
fi

# Test if config directory is writable
echo "⚙️  Testing config directory..."
if docker exec radarr_radarr_1 test -d /config 2>/dev/null; then
    if docker exec radarr_radarr_1 touch /config/test-write 2>/dev/null && docker exec radarr_radarr_1 rm /config/test-write 2>/dev/null; then
        echo "✅ Radarr config directory is writable"
    else
        echo "❌ Radarr config directory is not writable"
        exit 1
    fi
else
    echo "❌ Radarr config directory not accessible"
    exit 1
fi

# Test downloads directory access
echo "📥 Testing downloads directory..."
if docker exec radarr_radarr_1 ls /downloads > /dev/null 2>&1; then
    echo "✅ Radarr can access downloads directory"
    
    # Check if writable
    if docker exec radarr_radarr_1 test -w /downloads 2>/dev/null; then
        echo "✅ Radarr downloads directory is writable"
    else
        echo "⚠️  Radarr downloads directory may not be writable"
    fi
else
    echo "❌ Radarr cannot access downloads directory"
    exit 1
fi

# Test media directory access (Movies)
echo "🎥 Testing movies directory..."
if docker exec radarr_radarr_1 ls /movies > /dev/null 2>&1; then
    echo "✅ Radarr can access movies directory"
    
    # Check if writable
    if docker exec radarr_radarr_1 test -w /movies 2>/dev/null; then
        echo "✅ Radarr movies directory is writable"
    else
        echo "⚠️  Radarr movies directory may not be writable"
    fi
elif docker exec radarr_radarr_1 ls /data/medias/movies > /dev/null 2>&1; then
    echo "✅ Radarr can access movies directory at /data/medias/movies"
else
    echo "⚠️  Radarr movies directory not found (may be configured differently)"
fi

# Check PUID/PGID settings
echo "👤 Testing user permissions..."
container_user=$(docker exec radarr_radarr_1 id -u 2>/dev/null || echo "unknown")
container_group=$(docker exec radarr_radarr_1 id -g 2>/dev/null || echo "unknown")
echo "ℹ️  Radarr running as UID: $container_user, GID: $container_group"

if [ "$container_user" = "1000" ] && [ "$container_group" = "1000" ]; then
    echo "✅ Radarr running with correct PUID/PGID"
else
    echo "ℹ️  Radarr running with UID: $container_user, GID: $container_group (verify this matches your setup)"
fi

# Check container logs for obvious errors
echo "📋 Checking container logs for errors..."
error_count=$(docker logs radarr_radarr_1 2>&1 | grep -i "error\|exception\|fail" | wc -l || echo "0")
if [ "$error_count" -gt 0 ]; then
    echo "⚠️  Found $error_count potential errors in logs"
    # Show last few error lines
    docker logs radarr_radarr_1 2>&1 | grep -i "error\|exception\|fail" | tail -3
else
    echo "✅ No obvious errors in container logs"
fi

# Check resource usage
echo "📈 Checking container resources..."
memory_usage=$(docker stats radarr_radarr_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
cpu_usage=$(docker stats radarr_radarr_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Radarr memory usage: $memory_usage"
echo "ℹ️  Radarr CPU usage: $cpu_usage"

echo "🎬 Radarr tests completed successfully!" 