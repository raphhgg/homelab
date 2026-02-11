#!/bin/bash
# Smoked-Salmon Upload Helper Script
# Usage: salmon-upload [album-directory]
#   - If run from /volume2/downloads/music/Deemix/, you can use relative paths
#   - Supports tab completion for directory names

set -e

# Configuration
DEEMIX_HOST_PATH="/volume2/downloads/music/tmp"
CONTAINER_PATH="/app/music/tmp"
CONTAINER_NAME="smoked-salmon"
SOURCE="WEB"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to show usage
show_usage() {
    echo "Usage: $(basename $0) [album-directory]"
    echo ""
    echo "Examples:"
    echo "  $(basename $0) \"Artist - Album\"           # Relative to current directory"
    echo "  $(basename $0) /volume2/downloads/music/tmp/Artist\ -\ Album"
    echo "  $(basename $0) .                            # Use current directory"
    echo ""
    echo "If no argument provided, will list available albums in tmp folder."
}

# Function to convert host path to container path
host_to_container_path() {
    local host_path="$1"
    # Remove the host base path and prepend container path
    echo "${host_path/#$DEEMIX_HOST_PATH/$CONTAINER_PATH}"
}

# Main logic
main() {
    # If no argument provided, list available albums
    if [ $# -eq 0 ]; then
        echo -e "${YELLOW}Available albums in Deemix folder:${NC}"
        echo ""
        if [ -d "$DEEMIX_HOST_PATH" ]; then
            ls -1 "$DEEMIX_HOST_PATH" | while read -r album; do
                if [ -d "$DEEMIX_HOST_PATH/$album" ]; then
                    echo "  📁 $album"
                fi
            done
        else
            echo -e "${RED}Error: $DEEMIX_HOST_PATH does not exist${NC}"
            exit 1
        fi
        echo ""
        echo -e "${YELLOW}Usage: $(basename $0) \"Album Name\"${NC}"
        exit 0
    fi

    # Handle special arguments
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_usage
        exit 0
    fi

    local album_dir="$1"
    local host_path=""

    # Determine full host path
    if [ "$album_dir" = "." ]; then
        # Use current directory
        host_path="$(pwd)"
    elif [[ "$album_dir" = /* ]]; then
        # Absolute path provided
        host_path="$album_dir"
    else
        # Relative path - check if we're in Deemix directory
        if [[ "$(pwd)" == "$DEEMIX_HOST_PATH"* ]]; then
            host_path="$(pwd)/$album_dir"
        else
            # Assume it's relative to Deemix directory
            host_path="$DEEMIX_HOST_PATH/$album_dir"
        fi
    fi

    # Validate that path exists
    if [ ! -d "$host_path" ]; then
        echo -e "${RED}Error: Directory not found: $host_path${NC}"
        exit 1
    fi

    # Validate that path is within Deemix directory
    if [[ "$host_path" != "$DEEMIX_HOST_PATH"* ]]; then
        echo -e "${RED}Error: Directory must be within $DEEMIX_HOST_PATH${NC}"
        exit 1
    fi

    # Convert to container path
    local container_path=$(host_to_container_path "$host_path")

    # Display what we're doing
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  🎵 Smoked-Salmon Upload Helper                                ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Host path:${NC}      $host_path"
    echo -e "${YELLOW}Container path:${NC} $container_path"
    echo -e "${YELLOW}Source:${NC}         $SOURCE"
    echo ""
    echo -e "${GREEN}Starting upload...${NC}"
    echo ""

    # Start background permission fixer (runs every 2 seconds during upload)
    # This ensures permissions are fixed BEFORE qBittorrent tries to access files
    PERM_FIX_PID=""
    (
        while true; do
            sudo /volume2/docker/compose/scripts/fix-music-permissions.sh >/dev/null 2>&1
            sleep 2
        done
    ) &
    PERM_FIX_PID=$!

    # Run the upload command
    # -n: auto-rename files/folders based on metadata
    # yes_all config handles auto-confirm and transcode selection
    docker exec -it "$CONTAINER_NAME" .venv/bin/salmon up "$container_path" -s "$SOURCE" -n
    UPLOAD_EXIT_CODE=$?

    # Stop background permission fixer
    if [ -n "$PERM_FIX_PID" ]; then
        kill $PERM_FIX_PID 2>/dev/null
        wait $PERM_FIX_PID 2>/dev/null
    fi

    # Final permission fix to ensure everything is correct
    echo ""
    echo -e "${GREEN}Final permission check...${NC}"
    sudo /volume2/docker/compose/scripts/fix-music-permissions.sh

    echo ""
    if [ $UPLOAD_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ Upload complete!${NC}"
    else
        echo -e "${RED}✗ Upload failed (exit code: $UPLOAD_EXIT_CODE)${NC}"
        exit $UPLOAD_EXIT_CODE
    fi
}

# Run main function
main "$@"
