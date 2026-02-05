# Smoked-Salmon Workflow Verification

## Complete Workflow: Deemix → Smoked-Salmon → qBittorrent

### 1. Deemix Download Phase
**Container:** `deemix` (ghcr.io/bambanah/deemix:latest)
- **PUID:** 1026 (raphh) ✓
- **PGID:** 100 (users) ✓
- **UMASK:** 022 ✓
- **Output Path:** `/volume2/downloads/music/Deemix/[Album]/`
- **Permissions:** 777 directories, 755 files, owned by 1026:100 ✓

### 2. Smoked-Salmon Upload Phase
**Container:** `smoked-salmon` (ghcr.io/smokin-salmon/smoked-salmon:latest)
- **Runs as:** root (uid=0, gid=0)
- **PUID/PGID:** Set but NOT respected by the image ✗
- **UMASK:** 022 set but NOT working for hardlinked directories ✗

**Process:**
1. Reads: `/app/music/Deemix/[Album]/`
2. Creates FLAC directory: `/app/music/Orpheus/[Album] [WEB FLAC]/`
   - **Issue:** Created with 700 permissions as root ✗
3. Hardlinks FLAC files from Deemix → Orpheus
   - Files retain source permissions (755) ✓
4. Transcodes to MP3 320 and V0
   - New files created with UMASK (755) ✓
5. Adds torrents to qBittorrent via API

**Known Issues:**
- FLAC directories created with `drwx------` (700) permissions, root-only
- MP3 directories created with `drwxrwxrwx` (777) permissions correctly
- qBittorrent cannot read FLAC folders until permissions are fixed

### 3. Permission Fix Phase
**Script:** `fix-music-permissions.sh` (called by `salmon-upload.sh`)

```bash
chown -R 1026:100 /volume2/downloads/music/Orpheus/*
chmod -R 755 /volume2/downloads/music/Orpheus/*
```

**Result:**
- All directories: `drwxr-xr-x` (755) owned by 1026:100 ✓
- All files: `-rwxr-xr-x` (755) owned by 1026:100 ✓
- qBittorrent can now read all files ✓

### 4. qBittorrent Seeding Phase
**Container:** `qbit-main` (ghcr.io/hotio/qbittorrent:release-5.1.3)
- **Runs as:** root (uid=0)
- **Reads from:** `/downloads/music/Orpheus/`
- **Seeding:** Works correctly after permission fix ✓

**Known Issue - Save Path Bug:**
- **Problem:** Smoked-salmon sometimes adds FLAC torrents with wrong save_path
  - Expected: `/downloads/music/Orpheus`
  - Actual: `/downloads/music` (missing `/Orpheus`)
- **Symptom:** FLAC torrent shows as "stalledDL" at 0% progress
- **Workaround:** Manually relocate torrent or delete and re-add with correct path

## Verification Checklist

After each upload, verify:

1. **Permissions in Deemix:**
   ```bash
   ls -la "/volume2/downloads/music/Deemix/[Album]"
   # Expected: drwxrwxrwx directories, -rwxr-xr-x files, owned by raphh
   ```

2. **Permissions in Orpheus (after fix-music-permissions.sh):**
   ```bash
   ls -la "/volume2/downloads/music/Orpheus/[Album] [WEB FLAC]"
   # Expected: drwxr-xr-x directories, -rwxr-xr-x files, owned by raphh
   ```

3. **Torrent Status in qBittorrent:**
   ```bash
   docker exec qbit-main curl -s "http://admin:password123456@localhost:8080/api/v2/torrents/info?category=music" | python3 -m json.tool | grep -E '"(name|state|progress|save_path)"'
   # Expected: state=stalledUP or uploading, progress=1, save_path=/downloads/music/Orpheus
   ```

4. **File Readability Test:**
   ```bash
   docker exec qbit-main ls -la "/downloads/music/Orpheus/[Album] [WEB FLAC]/"
   # Should list all files without permission errors
   ```

## Automation Status

### ✅ Automated
- Permission fixing after each upload (via `salmon-upload.sh` → `fix-music-permissions.sh`)
- Torrent creation and addition to qBittorrent
- Hardlinking between Deemix and Orpheus

### ⚠️ Manual Intervention Required
- **FLAC torrent save_path verification** - Check if torrent is stalled after upload
- **Torrent relocation** - If FLAC torrent added with wrong path, must manually relocate

## Recommended Usage

```bash
# Upload album from Deemix
salmon "Album Name"

# Script automatically:
# 1. Runs smoked-salmon upload
# 2. Fixes permissions (prompts for sudo password)
# 3. Adds torrents to qBittorrent

# After upload, verify in qBittorrent WebUI:
# - Check if FLAC torrent is seeding (not stalled at 0%)
# - If stalled: delete and re-add with correct save_path
```

## Root Cause Analysis

### Why FLAC directories get root-only permissions:
1. Smoked-salmon container runs as root (image doesn't respect PUID/PGID)
2. When creating hardlink directory structure, uses root's default umask (022 doesn't apply)
3. Directories created with 700 permissions (rwx------)
4. Files inherit source permissions (755 from Deemix) ✓

### Why MP3 directories have correct permissions:
1. MP3 files are transcoded (newly created, not hardlinked)
2. UMASK=022 applies to new file/directory creation
3. Directories get 755 permissions (rwxr-xr-x) ✓

### Why fix-music-permissions.sh works:
1. Runs with sudo on host (has permission to chown root-owned files)
2. Recursively fixes all files and directories in Orpheus
3. Sets consistent 755 permissions and 1026:100 ownership

## Alternative Solutions (Not Implemented)

### Option 1: Modify smoked-salmon source
- Patch to create directories with explicit 755 permissions
- Requires maintaining custom fork

### Option 2: Run smoked-salmon as non-root
- Image doesn't support non-root execution
- Would require extensive image modifications

### Option 3: Post-upload hook in smoked-salmon
- If smoked-salmon supports hooks, could auto-fix permissions
- Would still require sudo access from container

**Current Solution (fix-music-permissions.sh) is the most practical and maintainable.**

## File Locations

- **Deemix Service:** `/volume2/docker/compose/services/torrents/deemix/`
- **Smoked-Salmon Service:** `/volume2/docker/compose/services/torrents/smoked-salmon/`
- **Upload Script:** `/volume2/docker/compose/scripts/salmon-upload.sh`
- **Permission Fix:** `/volume2/docker/compose/scripts/fix-music-permissions.sh`
- **Zsh Completion:** `/volume2/docker/compose/scripts/salmon-completion.zsh`
- **Alias:** `~/.zsh/aliases.zsh` → `alias salmon='/volume2/docker/compose/scripts/salmon-upload.sh'`

## Last Updated
2025-02-02 - Verified complete workflow with permission fixes working correctly
