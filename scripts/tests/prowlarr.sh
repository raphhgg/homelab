#!/bin/bash
set -e

echo "🔍 Testing Prowlarr..."

# Wait for Prowlarr to start
echo "⏳ Waiting for Prowlarr to initialize..."
sleep 45

# Get the port
port=$(docker-compose port prowlarr 9696 2>/dev/null | cut -d':' -f2 || echo "9696")

# Test web interface
echo "🌐 Testing Prowlarr web interface..."
if curl -f -s --connect-timeout 10 "http://localhost:$port" > /dev/null; then
    echo "✅ Prowlarr web interface accessible on port $port"
else
    echo "❌ Prowlarr web interface not accessible on port $port"
    exit 1
fi

# Test API without authentication
echo "🔌 Testing Prowlarr API..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v1/system/status" > /dev/null; then
    echo "✅ Prowlarr API accessible"
else
    echo "ℹ️  Prowlarr API requires authentication (this is expected)"
fi

# Test health endpoint
echo "💊 Testing Prowlarr health..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v1/health" > /dev/null; then
    echo "✅ Prowlarr health endpoint accessible"
else
    echo "ℹ️  Prowlarr health endpoint requires authentication"
fi

# Test indexer stats endpoint
echo "📊 Testing Prowlarr indexer stats..."
if curl -f -s --connect-timeout 10 "http://localhost:$port/api/v1/indexerstats" > /dev/null; then
    echo "✅ Prowlarr indexer stats accessible"
else
    echo "ℹ️  Prowlarr indexer stats requires authentication"
fi

# Test if config directory is writable
echo "⚙️  Testing config directory..."
if docker exec prowlarr_prowlarr_1 test -d /config 2>/dev/null; then
    if docker exec prowlarr_prowlarr_1 touch /config/test-write 2>/dev/null && docker exec prowlarr_prowlarr_1 rm /config/test-write 2>/dev/null; then
        echo "✅ Prowlarr config directory is writable"
    else
        echo "❌ Prowlarr config directory is not writable"
        exit 1
    fi
else
    echo "❌ Prowlarr config directory not accessible"
    exit 1
fi

# Check PUID/PGID settings
echo "👤 Testing user permissions..."
container_user=$(docker exec prowlarr_prowlarr_1 id -u 2>/dev/null || echo "unknown")
container_group=$(docker exec prowlarr_prowlarr_1 id -g 2>/dev/null || echo "unknown")
echo "ℹ️  Prowlarr running as UID: $container_user, GID: $container_group"

if [ "$container_user" = "1000" ] && [ "$container_group" = "1000" ]; then
    echo "✅ Prowlarr running with correct PUID/PGID"
else
    echo "ℹ️  Prowlarr running with UID: $container_user, GID: $container_group (verify this matches your setup)"
fi

# Test network connectivity (important for indexers)
echo "🌐 Testing external connectivity..."
if docker exec prowlarr_prowlarr_1 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ Prowlarr has external network connectivity"
else
    echo "❌ Prowlarr cannot reach external network"
    exit 1
fi

# Test DNS resolution
echo "🔍 Testing DNS resolution..."
if docker exec prowlarr_prowlarr_1 nslookup google.com > /dev/null 2>&1; then
    echo "✅ Prowlarr DNS resolution working"
else
    echo "❌ Prowlarr DNS resolution failed"
    exit 1
fi

# Check if can resolve common indexer domains
echo "🔎 Testing indexer domain resolution..."
test_domains=("thepiratebay.org" "1337x.to" "rarbg.to")
resolved_count=0

for domain in "${test_domains[@]}"; do
    if docker exec prowlarr_prowlarr_1 nslookup "$domain" > /dev/null 2>&1; then
        resolved_count=$((resolved_count + 1))
    fi
done

if [ "$resolved_count" -gt 0 ]; then
    echo "✅ Prowlarr can resolve indexer domains ($resolved_count/3 test domains)"
else
    echo "⚠️  Prowlarr may have issues resolving indexer domains (this could be due to DNS filtering)"
fi

# Check container logs for obvious errors
echo "📋 Checking container logs for errors..."
error_count=$(docker logs prowlarr_prowlarr_1 2>&1 | grep -i "error\|exception\|fail" | grep -v "Failed to lookup" | wc -l || echo "0")
if [ "$error_count" -gt 0 ]; then
    echo "⚠️  Found $error_count potential errors in logs"
    # Show last few error lines (excluding DNS lookup failures which are common)
    docker logs prowlarr_prowlarr_1 2>&1 | grep -i "error\|exception\|fail" | grep -v "Failed to lookup" | tail -3
else
    echo "✅ No obvious errors in container logs"
fi

# Check for common Prowlarr issues
echo "🔧 Checking for common configuration issues..."

# Check if running in host network mode (common for indexer access)
network_mode=$(docker inspect prowlarr_prowlarr_1 --format='{{.HostConfig.NetworkMode}}' 2>/dev/null || echo "unknown")
if [ "$network_mode" = "host" ]; then
    echo "ℹ️  Prowlarr running in host network mode (good for indexer access)"
elif [ "$network_mode" = "bridge" ]; then
    echo "ℹ️  Prowlarr running in bridge network mode"
else
    echo "ℹ️  Prowlarr network mode: $network_mode"
fi

# Check resource usage
echo "📈 Checking container resources..."
memory_usage=$(docker stats prowlarr_prowlarr_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
cpu_usage=$(docker stats prowlarr_prowlarr_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Prowlarr memory usage: $memory_usage"
echo "ℹ️  Prowlarr CPU usage: $cpu_usage"

echo "🔍 Prowlarr tests completed successfully!" 