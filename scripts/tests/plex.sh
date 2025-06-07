#!/bin/bash
set -e

echo "🎬 Testing Plex..."

# Wait for Plex to fully start (Plex takes longer to initialize)
echo "⏳ Waiting for Plex to initialize..."
sleep 60

# Test web interface
echo "🌐 Testing Plex web interface..."
if curl -f -s --connect-timeout 10 http://localhost:32400/web > /dev/null; then
    echo "✅ Plex web interface accessible"
else
    echo "❌ Plex web interface not accessible"
    exit 1
fi

# Test Plex API
echo "🔌 Testing Plex API..."
if curl -f -s --connect-timeout 10 "http://localhost:32400/identity" > /dev/null; then
    echo "✅ Plex API responding"
else
    echo "❌ Plex API not responding"
    exit 1
fi

# Test server status endpoint
echo "📊 Testing Plex server status..."
if curl -f -s --connect-timeout 10 "http://localhost:32400/status/sessions" > /dev/null; then
    echo "✅ Plex server status accessible"
else
    echo "⚠️  Plex server status not accessible (may need authentication)"
fi

# Check if Plex can access media directory
echo "📁 Testing media directory access..."
if docker exec plex_plex_1 ls /data/medias > /dev/null 2>&1; then
    echo "✅ Plex can access media directory"
    
    # Check permissions
    if docker exec plex_plex_1 test -r /data/medias 2>/dev/null; then
        echo "✅ Plex has read access to media directory"
    else
        echo "⚠️  Plex may not have read access to media directory"
    fi
else
    echo "❌ Plex cannot access media directory"
    exit 1
fi

# Check config directory
echo "⚙️  Testing config directory..."
if docker exec plex_plex_1 test -d /config 2>/dev/null; then
    if docker exec plex_plex_1 touch /config/test-write 2>/dev/null && docker exec plex_plex_1 rm /config/test-write 2>/dev/null; then
        echo "✅ Plex config directory is writable"
    else
        echo "❌ Plex config directory is not writable"
        exit 1
    fi
else
    echo "❌ Plex config directory not accessible"
    exit 1
fi

# Test hardware acceleration (if available)
echo "🎮 Testing hardware acceleration..."
if docker exec plex_plex_1 ls /dev/dri > /dev/null 2>&1; then
    echo "✅ Hardware acceleration device available"
    
    # Check if render group has proper permissions
    if docker exec plex_plex_1 test -r /dev/dri/renderD128 2>/dev/null; then
        echo "✅ Hardware acceleration device accessible"
    else
        echo "⚠️  Hardware acceleration device may not be accessible"
    fi
else
    echo "ℹ️  No hardware acceleration detected (this is normal for some setups)"
fi

# Test transcoding directory
echo "💾 Testing transcoding directory..."
if docker exec plex_plex_1 test -d /transcode 2>/dev/null; then
    if docker exec plex_plex_1 test -w /transcode 2>/dev/null; then
        echo "✅ Transcoding directory is writable"
    else
        echo "⚠️  Transcoding directory may not be writable"
    fi
else
    echo "⚠️  Transcoding directory not found"
fi

# Check container resource usage
echo "📈 Checking container resources..."
memory_usage=$(docker stats plex_plex_1 --no-stream --format "{{.MemUsage}}" 2>/dev/null || echo "unknown")
cpu_usage=$(docker stats plex_plex_1 --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "unknown")
echo "ℹ️  Plex memory usage: $memory_usage"
echo "ℹ️  Plex CPU usage: $cpu_usage"

echo "🎬 Plex tests completed successfully!" 