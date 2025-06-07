#!/bin/bash
set -e

echo "⬇️  Testing qBittorrent..."

# Wait for qBittorrent to start
echo "⏳ Waiting for qBittorrent to initialize..."
sleep 30

# Test web UI
echo "🌐 Testing qBittorrent web UI..."
if curl -f -s --connect-timeout 10 http://localhost:8080 > /dev/null; then
    echo "✅ qBittorrent web UI accessible on port 8080"
else
    echo "❌ qBittorrent web UI not accessible on port 8080"
    exit 1
fi

# Test login page specifically
echo "🔐 Testing qBittorrent login page..."
if curl -s --connect-timeout 10 http://localhost:8080 | grep -q "qBittorrent\|login\|password"; then
    echo "✅ qBittorrent login page loads correctly"
else
    echo "⚠️  qBittorrent login page may not be loading correctly"
fi

# Test if config directory is writable
echo "⚙️  Testing config directory..."
if docker exec qbittorrent_qbittorrent_1 test -d /config 2>/dev/null; then
    if docker exec qbittorrent_qbittorrent_1 touch /config/test-write 2>/dev/null && docker exec qbittorrent_qbittorrent_1 rm /config/test-write 2>/dev/null; then
        echo "✅ qBittorrent config directory is writable"
    else
        echo "❌ qBittorrent config directory is not writable"
        exit 1
    fi
else
    echo "❌ qBittorrent config directory not accessible"
    exit 1
fi

# Test downloads directory
echo "📥 Testing downloads directory..."
if docker exec qbittorrent_qbittorrent_1 ls /downloads > /dev/null 2>&1; then
    echo "✅ qBittorrent can access downloads directory"
    
    # Check if writable
    if docker exec qbittorrent_qbittorrent_1 test -w /downloads 2>/dev/null; then
        echo "✅ qBittorrent downloads directory is writable"
    else
        echo "❌ qBittorrent downloads directory is not writable"
        exit 1
    fi
    
    # Check available space
    available_space=$(docker exec qbittorrent_qbittorrent_1 df -h /downloads 2>/dev/null | tail -1 | awk '{print $4}' || echo "unknown")
    echo "ℹ️  Available space in downloads directory: $available_space"
else
    echo "❌ qBittorrent cannot access downloads directory"
    exit 1
fi

# Check PUID/PGID settings
echo "👤 Testing user permissions..."
container_user=$(docker exec qbittorrent_qbittorrent_1 id -u 2>/dev/null || echo "unknown")
container_group=$(docker exec qbittorrent_qbittorrent_1 id -g 2>/dev/null || echo "unknown")
echo "ℹ️  qBittorrent running as UID: $container_user, GID: $container_group"

if [ "$container_user" = "1000" ] && [ "$container_group" = "1000" ]; then
    echo "✅ qBittorrent running with correct PUID/PGID"
else
    echo "ℹ️  qBittorrent running with UID: $container_user, GID: $container_group (verify this matches your setup)"
fi

# Test network connectivity
echo "🌐 Testing external connectivity..."
if docker exec qbittorrent_qbittorrent_1 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ qBittorrent has external network connectivity"
else
    echo "❌ qBittorrent cannot reach external network"
    exit 1
fi

# Check external IP (useful for VPN setups)
echo "🔍 Testing external IP..."
external_ip=$(docker exec qbittorrent_qbittorrent_1 curl -s --connect-timeout 10 ifconfig.me 2>/dev/null || echo "unknown")
if [ "$external_ip" != "unknown" ] && [ -n "$external_ip" ]; then
    echo "ℹ️  qBittorrent external IP: $external_ip"
    
    # Check if IP is private (might indicate VPN issue)
    if echo "$external_ip" | grep -qE "^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)" 2>/dev/null; then
        echo "⚠️  External IP appears to be private - check VPN configuration"
    else
        echo "✅ External IP appears to be public"
    fi
else
    echo "⚠️  Could not determine external IP"
fi

# Test BitTorrent ports (if exposed)
echo "🔌 Testing BitTorrent connectivity..."
# Most common ports are 6881-6889
bt_port_exposed=false
for port in 6881 6882 6883; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        echo "ℹ️  BitTorrent port $port appears to be exposed"
        bt_port_exposed=true
        break
    fi
done

if [ "$bt_port_exposed" = false ]; then
    echo "ℹ️  No standard BitTorrent ports detected (this may be normal depending on configuration)"
fi

# Check for VPN container (common setup)
echo "🔒 Checking for VPN integration..."
if docker ps --format "table {{.Names}}" | grep -iq vpn; then
    vpn_container=$(docker ps --format "table {{.Names}}" | grep -i vpn | head -1)
    echo "ℹ️  VPN container detected: $vpn_container"
    
    # Check if qBittorrent is using VPN network
    qbt_network=$(docker inspect qbittorrent_qbittorrent_1 --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null || echo "unknown")
    echo "ℹ️  qBittorrent network: $qbt_network"
else
    echo "ℹ️  No VPN container detected"
fi

# Check container logs for errors
echo "📋 Checking container logs for errors..."
error_count=$(docker logs qbittorrent_qbittorrent_1 2>&1 | grep -i "error\|exception\|fail\|fatal" | wc -l || echo "0")
if [ "$error_count" -gt 0 ]; then
    echo "⚠️  Found $error_count potential errors in logs"
    # Show last few error lines
    docker logs qbittorrent_qbittorrent_1 2>&1 | grep -i "error\|exception\|fail\|fatal" | tail -3
else
    echo "✅ No obvious errors in container logs"
fi

# Check resource usage
echo "📈 Checking container resources..."
memory_usage=$(docker stats qbittorrent_qbittorrent_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
cpu_usage=$(docker stats qbittorrent_qbittorrent_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  qBittorrent memory usage: $memory_usage"
echo "ℹ️  qBittorrent CPU usage: $cpu_usage"

# Check disk I/O (important for torrenting)
echo "💾 Checking disk I/O..."
io_stats=$(docker stats qbittorrent_qbittorrent_1 --no-stream --format "{{.BlockIO}}" 2>/dev/null || echo "unknown")
echo "ℹ️  qBittorrent disk I/O: $io_stats"

echo "⬇️  qBittorrent tests completed successfully!" 