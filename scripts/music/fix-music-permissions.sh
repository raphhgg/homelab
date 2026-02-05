#!/bin/bash
# Fix permissions on music files for qBittorrent seeding
# Run this after uploads to ensure qBittorrent can read the files

MUSIC_DIR="/volume2/downloads/music"

echo "Fixing permissions in $MUSIC_DIR..."

# Find directories with wrong ownership (root) and fix them
find "$MUSIC_DIR" -maxdepth 1 -type d -user root ! -name "@eaDir" -exec chown -R 1026:100 {} \; 2>/dev/null
find "$MUSIC_DIR" -maxdepth 1 -type d -user root ! -name "@eaDir" -exec chmod -R 755 {} \; 2>/dev/null

# Also fix any files with wrong permissions inside existing folders
find "$MUSIC_DIR" -type d ! -name "@eaDir" -perm 700 -exec chmod 755 {} \; 2>/dev/null

echo "✓ Permissions fixed!"
echo "  Owner: 1026:100 (raphh:users)"
echo "  Permissions: 755 (rwxr-xr-x)"
