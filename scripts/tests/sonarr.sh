#!/bin/bash
set -e

echo "📺 Testing Sonarr..."

# Wait for Sonarr to start
echo "⏳ Waiting for Sonarr to initialize..."
sleep 45

# Get the port
port=$(docker-compose port sonarr 8989 2>/dev/null | cut -d':' -f2 || echo "8989")

# Test web interface
echo "🌐 Testing Sonarr web interface..."
if curl -f -s --connect-timeout 10 "http://localhost:$port" > /dev/null; then
    echo "✅ Sonarr web interface accessible on port $port"
else
    echo "❌ Sonarr web interface not accessible on port $port"
    exit 1
fi

# Test API without authentication
echo "🔌 Testing Sonarr API..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v3/system/status" > /dev/null; then
    echo "✅ Sonarr API accessible"
else
    # Try with authentication (though we don't have real API key in tests)
    echo "ℹ️  Sonarr API requires authentication (this is expected)"
fi

# Test health endpoint
echo "💊 Testing Sonarr health..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v3/health" > /dev/null; then
    echo "✅ Sonarr health endpoint accessible"
else
    echo "ℹ️  Sonarr health endpoint requires authentication"
fi

# Test if config directory is writable
echo "⚙️  Testing config directory..."
if docker exec sonarr_sonarr_1 test -d /config 2>/dev/null; then
    if docker exec sonarr_sonarr_1 touch /config/test-write 2>/dev/null && docker exec sonarr_sonarr_1 rm /config/test-write 2>/dev/null; then
        echo "✅ Sonarr config directory is writable"
    else
        echo "❌ Sonarr config directory is not writable"
        exit 1
    fi
else
    echo "❌ Sonarr config directory not accessible"
    exit 1
fi

# Test downloads directory access
echo "📥 Testing downloads directory..."
if docker exec sonarr_sonarr_1 ls /downloads > /dev/null 2>&1; then
    echo "✅ Sonarr can access downloads directory"
    
    # Check if writable
    if docker exec sonarr_sonarr_1 test -w /downloads 2>/dev/null; then
        echo "✅ Sonarr downloads directory is writable"
    else
        echo "⚠️  Sonarr downloads directory may not be writable"
    fi
else
    echo "❌ Sonarr cannot access downloads directory"
    exit 1
fi

# Test media directory access (TV shows)
echo "📺 Testing TV shows directory..."
if docker exec sonarr_sonarr_1 ls /tv > /dev/null 2>&1; then
    echo "✅ Sonarr can access TV shows directory"
    
    # Check if writable
    if docker exec sonarr_sonarr_1 test -w /tv 2>/dev/null; then
        echo "✅ Sonarr TV directory is writable"
    else
        echo "⚠️  Sonarr TV directory may not be writable"
    fi
elif docker exec sonarr_sonarr_1 ls /data/medias/tv > /dev/null 2>&1; then
    echo "✅ Sonarr can access TV shows directory at /data/medias/tv"
else
    echo "⚠️  Sonarr TV shows directory not found (may be configured differently)"
fi

# Check PUID/PGID settings
echo "👤 Testing user permissions..."
container_user=$(docker exec sonarr_sonarr_1 id -u 2>/dev/null || echo "unknown")
container_group=$(docker exec sonarr_sonarr_1 id -g 2>/dev/null || echo "unknown")
echo "ℹ️  Sonarr running as UID: $container_user, GID: $container_group"

if [ "$container_user" = "1000" ] && [ "$container_group" = "1000" ]; then
    echo "✅ Sonarr running with correct PUID/PGID"
else
    echo "ℹ️  Sonarr running with UID: $container_user, GID: $container_group (verify this matches your setup)"
fi

# Check container logs for obvious errors
echo "📋 Checking container logs for errors..."
error_count=$(docker logs sonarr_sonarr_1 2>&1 | grep -i "error\|exception\|fail" | wc -l || echo "0")
if [ "$error_count" -gt 0 ]; then
    echo "⚠️  Found $error_count potential errors in logs"
    # Show last few error lines
    docker logs sonarr_sonarr_1 2>&1 | grep -i "error\|exception\|fail" | tail -3
else
    echo "✅ No obvious errors in container logs"
fi

# Check resource usage
echo "📈 Checking container resources..."
memory_usage=$(docker stats sonarr_sonarr_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
cpu_usage=$(docker stats sonarr_sonarr_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Sonarr memory usage: $memory_usage"
echo "ℹ️  Sonarr CPU usage: $cpu_usage"

echo "📺 Sonarr tests completed successfully!" 