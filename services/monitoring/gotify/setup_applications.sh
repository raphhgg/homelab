#!/bin/bash
#
# Gotify Application Setup Script
# Creates applications with icons for all homelab services
#
# Usage: ./setup_applications.sh
# Requires: curl, jq
#

set -euo pipefail

# Configuration - Update these values
GOTIFY_URL="http://10.10.2.2:8093"
GOTIFY_USER="admin"
GOTIFY_PASS="${GOTIFY_PASS:-}"  # Set via environment or prompt

# Prompt for password if not set
if [ -z "$GOTIFY_PASS" ]; then
    read -sp "Enter Gotify admin password: " GOTIFY_PASS
    echo
fi

# Directory for downloaded icons
ICON_DIR="/tmp/gotify-icons"
mkdir -p "$ICON_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}!${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Function to create application and return its ID
create_app() {
    local name="$1"
    local description="$2"

    response=$(curl -s -X POST "$GOTIFY_URL/application" \
        -u "$GOTIFY_USER:$GOTIFY_PASS" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$name\", \"description\": \"$description\"}")

    app_id=$(echo "$response" | jq -r '.id // empty')
    token=$(echo "$response" | jq -r '.token // empty')

    if [ -n "$app_id" ]; then
        echo "$app_id:$token"
    else
        echo ""
    fi
}

# Function to upload image to application
upload_image() {
    local app_id="$1"
    local image_path="$2"

    if [ -f "$image_path" ]; then
        curl -s -X POST "$GOTIFY_URL/application/$app_id/image" \
            -u "$GOTIFY_USER:$GOTIFY_PASS" \
            -F "file=@$image_path" > /dev/null
        return 0
    fi
    return 1
}

# Function to download icon
download_icon() {
    local url="$1"
    local filename="$2"
    local output="$ICON_DIR/$filename"

    if curl -sL "$url" -o "$output" 2>/dev/null; then
        # Check if file is valid (not empty and not HTML error page)
        if [ -s "$output" ] && ! grep -q "<!DOCTYPE" "$output" 2>/dev/null; then
            echo "$output"
            return 0
        fi
    fi
    rm -f "$output" 2>/dev/null
    echo ""
    return 1
}

echo "=========================================="
echo "Gotify Application Setup"
echo "=========================================="
echo ""

# Test connection
echo "Testing connection to Gotify..."
if ! curl -s -u "$GOTIFY_USER:$GOTIFY_PASS" "$GOTIFY_URL/current/user" | jq -e '.id' > /dev/null 2>&1; then
    log_error "Failed to connect to Gotify. Check URL and credentials."
    exit 1
fi
log_success "Connected to Gotify"
echo ""

# Define applications: name|description|icon_url|icon_filename
declare -a APPS=(
    # Monitoring
    "uptime-kuma|Service availability monitoring|https://raw.githubusercontent.com/louislam/uptime-kuma/master/public/icon.png|uptime-kuma.png"
    "beszel|Hardware and resource monitoring|https://raw.githubusercontent.com/henrygd/beszel/main/beszel/site/public/static/favicon.svg|beszel.svg"
    "watchtower|Container update notifications|https://raw.githubusercontent.com/containrrr/watchtower/main/logo.png|watchtower.png"
    "netronome|Network monitoring|http://10.10.2.2:7575/assets/logo_small-BqRcpYEM.png|netronome.png"

    # Arrs
    "sonarr|TV show management|https://raw.githubusercontent.com/Sonarr/Sonarr/develop/Logo/256.png|sonarr.png"
    "radarr|Movie management|https://raw.githubusercontent.com/Radarr/Radarr/develop/Logo/256.png|radarr.png"
    "prowlarr|Indexer management|https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/Logo/256.png|prowlarr.png"
    "bazarr|Subtitle management|https://raw.githubusercontent.com/morpheus65535/bazarr/master/frontend/public/images/logo128.png|bazarr.png"

    # Media Server
    "tautulli|Plex activity monitoring|https://raw.githubusercontent.com/Tautulli/Tautulli/master/data/interfaces/default/images/logo-circle.png|tautulli.png"
    "jellyseerr|Media request management|https://raw.githubusercontent.com/Fallenbagel/jellyseerr/develop/public/logo_full.svg|jellyseerr.svg"
    "kometa|Plex metadata management|https://raw.githubusercontent.com/Kometa-Team/Kometa/master/docs/assets/logo.png|kometa.png"
    "plex|Media streaming server|https://www.plex.tv/wp-content/uploads/2018/01/pmp-icon-1.png|plex.png"

    # Torrents
    "autobrr|Release automation|https://raw.githubusercontent.com/autobrr/autobrr/develop/web/public/logo.svg|autobrr.svg"
    "qbittorrent|Torrent client|https://upload.wikimedia.org/wikipedia/commons/6/66/New_qBittorrent_Logo.svg|qbittorrent.svg"

    # System
    "synology|Synology DSM alerts|https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/synology-dsm.svg|synology.svg"
)

echo "Creating applications..."
echo ""

# Store results for summary
declare -A TOKENS

for app_entry in "${APPS[@]}"; do
    IFS='|' read -r name description icon_url icon_filename <<< "$app_entry"

    echo "Creating: $name"

    # Create application
    result=$(create_app "$name" "$description")

    if [ -n "$result" ]; then
        app_id="${result%%:*}"
        token="${result##*:}"
        TOKENS["$name"]="$token"
        log_success "Created application (ID: $app_id)"

        # Download and upload icon
        icon_path=$(download_icon "$icon_url" "$icon_filename")
        if [ -n "$icon_path" ]; then
            if upload_image "$app_id" "$icon_path"; then
                log_success "Uploaded icon"
            else
                log_warning "Failed to upload icon"
            fi
        else
            log_warning "Failed to download icon from: $icon_url"
        fi
    else
        log_error "Failed to create application (may already exist)"
    fi
    echo ""
done

# Summary
echo "=========================================="
echo "Application Tokens"
echo "=========================================="
echo ""
echo "Save these tokens for configuring your services:"
echo ""

for name in "${!TOKENS[@]}"; do
    echo "$name: ${TOKENS[$name]}"
done

echo ""
echo "=========================================="
echo "Setup Complete"
echo "=========================================="

# Cleanup
rm -rf "$ICON_DIR"
