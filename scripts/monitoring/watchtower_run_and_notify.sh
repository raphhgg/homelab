#!/bin/bash
#
# Watchtower Update and Notification Script for Cronicle
# Runs Watchtower to update containers and sends Discord notification via Apprise
#
# This script should be copied into the Cronicle job.
# Source location: scripts/monitoring/watchtower_run_and_notify.sh
#

set -euo pipefail

export APPRISE_URL="http://apprise:8000/notify/watchtower"

# Create log file with timestamp
LOG_FILE="/tmp/watchtower-update-$(date +%Y%m%d-%H%M%S).log"

echo "Running Watchtower - Updating containers..."
docker exec watchtower /watchtower --run-once --label-enable --cleanup --debug 2>&1 | tee "$LOG_FILE"

echo ""
echo "Parsing log and sending notification..."

# Verify log file exists
if [[ ! -f "$LOG_FILE" ]]; then
    echo "Error: Log file not found: $LOG_FILE"
    exit 1
fi

# Function to get real version from container
get_version() {
    local container="$1"
    local image="$2"
    local version=""

    # Try to get version from container labels (BusyBox-compatible)
    version=$(docker inspect "$container" 2>/dev/null | \
        grep '"org.opencontainers.image.version"' | \
        sed 's/.*"org.opencontainers.image.version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' | \
        head -1)

    # Clean up version strings for specific containers
    case "$image" in
        ghcr.io/dan-online/autopulse*)
            # autopulse uses "main" as version - get date instead
            if [[ "$version" == "main" ]]; then
                local created=$(docker inspect "$container" 2>/dev/null | \
                    grep '"org.opencontainers.image.created"' | \
                    sed 's/.*"org.opencontainers.image.created"[[:space:]]*:[[:space:]]*"\([^"T]*\).*/\1/' | \
                    head -1)
                version="latest (${created})"
            else
                # Remove "autopulse-v" or "v" prefix if present
                version=$(echo "$version" | sed 's/^autopulse-v//;s/^v//')
            fi
            ;;
        myoung34/github-runner*)
            # github-runner uses ubuntu version (e.g., "20.04") - get creation date instead
            if [[ "$version" =~ ^[0-9]+\.[0-9]+$ ]]; then
                local created=$(docker inspect "$container" 2>/dev/null | \
                    grep '"org.opencontainers.image.created"' | \
                    sed 's/.*"org.opencontainers.image.created"[[:space:]]*:[[:space:]]*"\([^"T]*\).*/\1/' | \
                    head -1)
                if [[ -n "$created" ]]; then
                    version="latest (${created})"
                else
                    version="latest"
                fi
            else
                # Remove "ubuntu-", "runner-v", or "v" prefix if present
                version=$(echo "$version" | sed 's/^ubuntu-//;s/^runner-v//;s/^v//')
            fi
            ;;
    esac

    # If no version label or empty after cleanup, return "latest"
    echo "${version:-latest}"
}

# Function to get image build date
get_image_date() {
    local container="$1"
    local created=$(docker inspect "$container" 2>/dev/null | \
        grep '"Created"' | head -1 | \
        sed 's/.*"Created"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' | \
        cut -d'T' -f1)
    echo "${created:-unknown}"
}

# Function to get image age in days
get_image_age() {
    local created="$1"
    if [[ "$created" != "unknown" ]]; then
        local created_epoch=$(date -d "$created" +%s 2>/dev/null || echo "0")
        local now_epoch=$(date +%s)
        if [[ "$created_epoch" -gt 0 ]]; then
            local age_days=$(( (now_epoch - created_epoch) / 86400 ))
            echo "$age_days"
            return
        fi
    fi
    echo "unknown"
}

# Function to get changelog URL from image
get_changelog() {
    local image="$1"

    # Map common images to their GitHub releases
    case "$image" in
        ghcr.io/hotio/sonarr*)
            echo "https://github.com/Sonarr/Sonarr/releases"
            ;;
        ghcr.io/hotio/radarr*)
            echo "https://github.com/Radarr/Radarr/releases"
            ;;
        ghcr.io/hotio/bazarr*)
            echo "https://github.com/morpheus65535/bazarr/releases"
            ;;
        ghcr.io/hotio/prowlarr*)
            echo "https://github.com/Prowlarr/Prowlarr/releases"
            ;;
        ghcr.io/hotio/readarr*)
            echo "https://github.com/Readarr/Readarr/releases"
            ;;
        ghcr.io/hotio/*)
            # Fallback for other hotio images - link to hotio.dev
            local app=$(echo "$image" | sed 's|.*hotio/\([^:]*\).*|\1|')
            echo "https://hotio.dev/containers/${app}/"
            ;;
        ghcr.io/autobrr/*)
            echo "$image" | sed 's|ghcr.io/\(autobrr/[^:]*\).*|https://github.com/\1/releases|'
            ;;
        ghcr.io/containrrr/*)
            echo "$image" | sed 's|ghcr.io/\(containrrr/[^:]*\).*|https://github.com/\1/releases|'
            ;;
        ghcr.io/home-assistant/*)
            echo "https://github.com/home-assistant/core/releases"
            ;;
        lscr.io/linuxserver/*)
            local app=$(echo "$image" | sed 's|.*linuxserver/\([^:]*\).*|\1|')
            echo "https://github.com/linuxserver/docker-${app}/releases"
            ;;
        myoung34/github-runner*)
            echo "https://github.com/myoung34/docker-github-actions-runner/releases"
            ;;
        henrygd/beszel*)
            echo "https://github.com/henrygd/beszel/releases"
            ;;
        journeyover/plex-auto-languages*)
            echo "https://github.com/RemiRigal/Plex-Auto-Languages/releases"
            ;;
        ghcr.io/dan-online/autopulse*)
            echo "https://github.com/dan-online/autopulse/releases"
            ;;
        ghcr.io/calibrain/*)
            echo "https://github.com/calibrain/calibre-web-automated-book-downloader/releases"
            ;;
        louislam/uptime-kuma*)
            echo "https://github.com/louislam/uptime-kuma/releases"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Parse for updates
declare -A updates
declare -A images
declare -A image_ids
while IFS= read -r line; do
    if [[ "$line" =~ level=info\ msg=\"Found\ new\ ([^\ ]+)\ image\ \(([a-f0-9]+)\) ]]; then
        image="${BASH_REMATCH[1]}"
        image_id="${BASH_REMATCH[2]}"
        # Extract container name
        if [[ "$image" =~ /([^/:]+)(:latest|:.+)?$ ]]; then
            container="${BASH_REMATCH[1]}"
            version=$(get_version "$container" "$image")
            updates["$container"]="$version"
            images["$container"]="$image"
            image_ids["$container"]="$image_id"
        fi
    fi
done < "$LOG_FILE"

# Exit if no updates
set +u  # Temporarily disable unbound variable check
num_updates=${#updates[@]}
set -u
if [[ $num_updates -eq 0 ]]; then
    echo "No updates found"
    exit 0
fi

# Build notification
count=${#updates[@]}
title="$count Containers Updated"

# Body WITHOUT ## header - let title handle the header
body=""

# Sort containers alphabetically
for container in $(printf '%s\n' "${!updates[@]}" | sort); do
    version="${updates[$container]}"
    image="${images[$container]}"
    image_id="${image_ids[$container]}"
    changelog=$(get_changelog "$image")

    # Get image build date and age
    build_date=$(get_image_date "$container")
    age_days=$(get_image_age "$build_date")

    # Build the line with enhanced info
    line="- **${container}** → \`${version}\`"

    # Add image age context if available
    if [[ "$age_days" != "unknown" ]]; then
        if [[ "$age_days" -eq 0 ]]; then
            line+=" (built today)"
        elif [[ "$age_days" -eq 1 ]]; then
            line+=" (built yesterday)"
        elif [[ "$age_days" -le 7 ]]; then
            line+=" (${age_days}d old)"
        fi
    fi

    # Add changelog link
    if [[ -n "$changelog" ]]; then
        line+=" • [Changelog]($changelog)"
    fi

    # Add image digest as small text for debugging
    line+=" \`${image_id:0:12}\`"

    body+="${line}"$'\n'
done

# Add footer with explanation
body+=$'\n'
body+="_Updates may include base image patches, dependencies, or new releases._"

# Send using EXACT format from your working command
curl -X POST "$APPRISE_URL" \
  --data-urlencode "title=$title" \
  --data-urlencode "body=$body" \
  -d tag=watchtower

echo "✓ Sent notification for $count update(s)"
