#!/bin/bash
set -e

echo "🛡️  Testing Pi-hole + Unbound..."

# Wait for services to start
echo "⏳ Waiting for Pi-hole and Unbound to initialize..."
sleep 45

# Test Pi-hole web interface
echo "🌐 Testing Pi-hole web interface..."
if curl -f -s --connect-timeout 10 http://localhost:80/admin > /dev/null; then
    echo "✅ Pi-hole web interface accessible"
elif curl -f -s --connect-timeout 10 http://localhost/admin > /dev/null; then
    echo "✅ Pi-hole web interface accessible"
else
    echo "❌ Pi-hole web interface not accessible"
    exit 1
fi

# Test Pi-hole API
echo "🔌 Testing Pi-hole API..."
if curl -f -s --connect-timeout 10 "http://localhost/admin/api.php" > /dev/null; then
    echo "✅ Pi-hole API accessible"
    
    # Get some basic stats
    stats=$(curl -s --connect-timeout 10 "http://localhost/admin/api.php?summaryRaw" 2>/dev/null || echo "")
    if [ -n "$stats" ]; then
        echo "ℹ️  Pi-hole API responding with stats"
    fi
else
    echo "⚠️  Pi-hole API may not be accessible"
fi

# Test DNS resolution via Pi-hole
echo "🔍 Testing DNS resolution via Pi-hole..."
if docker exec pihole_unbound_pihole_1 nslookup google.com localhost > /dev/null 2>&1; then
    echo "✅ Pi-hole DNS resolution working"
    
    # Test specific DNS query
    dns_result=$(docker exec pihole_unbound_pihole_1 nslookup google.com localhost 2>/dev/null | grep "Address:" | tail -1 | awk '{print $2}' || echo "unknown")
    if [ "$dns_result" != "unknown" ] && [ -n "$dns_result" ]; then
        echo "ℹ️  DNS query for google.com returned: $dns_result"
    fi
else
    echo "❌ Pi-hole DNS resolution failed"
    exit 1
fi

# Test Unbound is running and accessible
echo "🔄 Testing Unbound DNS resolver..."
if docker exec pihole_unbound_unbound_1 dig @localhost google.com > /dev/null 2>&1; then
    echo "✅ Unbound DNS resolver working"
    
    # Test DNSSEC validation
    if docker exec pihole_unbound_unbound_1 dig @localhost +dnssec google.com > /dev/null 2>&1; then
        echo "✅ Unbound DNSSEC validation available"
    else
        echo "ℹ️  DNSSEC validation may not be enabled"
    fi
else
    echo "❌ Unbound DNS resolver not working"
    exit 1
fi

# Test ad blocking functionality
echo "🚫 Testing ad blocking..."
# Test known ad domain
ad_test_domains=("ads.yahoo.com" "googleadservices.com" "doubleclick.net")
blocked_count=0

for domain in "${ad_test_domains[@]}"; do
    result=$(docker exec pihole_unbound_pihole_1 nslookup "$domain" localhost 2>/dev/null | grep "Address:" | tail -1 | awk '{print $2}' || echo "")
    if [ "$result" = "0.0.0.0" ] || [ "$result" = "127.0.0.1" ]; then
        blocked_count=$((blocked_count + 1))
        echo "✅ $domain is blocked"
    else
        echo "ℹ️  $domain returned: $result"
    fi
done

if [ "$blocked_count" -gt 0 ]; then
    echo "✅ Ad blocking appears to be working ($blocked_count/3 test domains blocked)"
else
    echo "⚠️  Ad blocking may not be working properly"
fi

# Test reverse DNS lookup
echo "🔄 Testing reverse DNS..."
if docker exec pihole_unbound_pihole_1 nslookup 8.8.8.8 localhost > /dev/null 2>&1; then
    echo "✅ Reverse DNS lookup working"
else
    echo "⚠️  Reverse DNS lookup may not be working"
fi

# Check Pi-hole logs for functionality
echo "📋 Testing Pi-hole logging..."
if docker exec pihole_unbound_pihole_1 test -f /var/log/pihole.log 2>/dev/null; then
    log_entries=$(docker exec pihole_unbound_pihole_1 wc -l /var/log/pihole.log 2>/dev/null | awk '{print $1}' || echo "0")
    echo "ℹ️  Pi-hole log has $log_entries entries"
    
    if [ "$log_entries" -gt 0 ]; then
        echo "✅ Pi-hole is logging DNS queries"
    else
        echo "⚠️  Pi-hole may not be logging queries yet"
    fi
else
    echo "⚠️  Pi-hole log file not found"
fi

# Test blocklist updates
echo "📝 Testing blocklist status..."
if docker exec pihole_unbound_pihole_1 test -f /etc/pihole/gravity.db 2>/dev/null; then
    echo "✅ Pi-hole gravity database exists"
    
    # Check database size (indicates blocklist data)
    db_size=$(docker exec pihole_unbound_pihole_1 ls -lh /etc/pihole/gravity.db 2>/dev/null | awk '{print $5}' || echo "unknown")
    echo "ℹ️  Gravity database size: $db_size"
else
    echo "⚠️  Pi-hole gravity database not found - may need initial setup"
fi

# Check container resources and health
echo "📈 Checking Pi-hole container resources..."
pihole_memory=$(docker stats pihole_unbound_pihole_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
pihole_cpu=$(docker stats pihole_unbound_pihole_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Pi-hole memory usage: $pihole_memory"
echo "ℹ️  Pi-hole CPU usage: $pihole_cpu"

echo "📈 Checking Unbound container resources..."
unbound_memory=$(docker stats pihole_unbound_unbound_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
unbound_cpu=$(docker stats pihole_unbound_unbound_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Unbound memory usage: $unbound_memory"
echo "ℹ️  Unbound CPU usage: $unbound_cpu"

# Check for common configuration issues
echo "🔧 Checking configuration..."

# Verify Pi-hole is using Unbound as upstream
echo "🔗 Testing Pi-hole -> Unbound integration..."
if docker exec pihole_unbound_pihole_1 grep -q "127.0.0.1#5335" /etc/pihole/setupVars.conf 2>/dev/null; then
    echo "✅ Pi-hole configured to use Unbound as upstream"
elif docker exec pihole_unbound_pihole_1 grep -q "unbound" /etc/pihole/setupVars.conf 2>/dev/null; then
    echo "✅ Pi-hole appears to be configured for Unbound"
else
    echo "⚠️  Pi-hole may not be configured to use Unbound as upstream"
fi

# Check for errors in logs
echo "📋 Checking for errors in logs..."
pihole_errors=$(docker logs pihole_unbound_pihole_1 2>&1 | grep -i "error\|fail\|exception" | wc -l || echo "0")
unbound_errors=$(docker logs pihole_unbound_unbound_1 2>&1 | grep -i "error\|fail\|exception" | wc -l || echo "0")

if [ "$pihole_errors" -gt 0 ]; then
    echo "⚠️  Found $pihole_errors potential errors in Pi-hole logs"
    docker logs pihole_unbound_pihole_1 2>&1 | grep -i "error\|fail\|exception" | tail -2
else
    echo "✅ No obvious errors in Pi-hole logs"
fi

if [ "$unbound_errors" -gt 0 ]; then
    echo "⚠️  Found $unbound_errors potential errors in Unbound logs"
    docker logs pihole_unbound_unbound_1 2>&1 | grep -i "error\|fail\|exception" | tail -2
else
    echo "✅ No obvious errors in Unbound logs"
fi

# Test external connectivity from containers
echo "🌐 Testing external connectivity from containers..."
if docker exec pihole_unbound_pihole_1 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ Pi-hole container has external connectivity"
else
    echo "❌ Pi-hole container cannot reach external network"
    exit 1
fi

if docker exec pihole_unbound_unbound_1 ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ Unbound container has external connectivity"
else
    echo "❌ Unbound container cannot reach external network"
    exit 1
fi

echo "🛡️  Pi-hole + Unbound tests completed successfully!" 