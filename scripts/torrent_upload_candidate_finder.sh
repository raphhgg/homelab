#!/bin/bash
# Find torrents missing from selected trackers
# Interactive script to identify upload candidates

DB="/volume2/docker/appdata/cross-seed/cross-seed.db"
OUTPUT_DIR="/tmp/missing_torrents"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate timestamp for file naming
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Caches for API responses
declare -A TMDB_CACHE
declare -A ATH_SLOTS_CACHE

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Torrent Upload Candidate Finder                 ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Define target trackers (ones we want to upload to)
TARGET_TRACKERS=("Aither (API)" "Anthelion (API)" "Blutopia (API)" "Nebulance")

# Get all available indexers from database
mapfile -t ALL_INDEXERS < <(sqlite3 "$DB" "SELECT id || '|' || name FROM indexer WHERE active = 1 ORDER BY name;")

if [ ${#ALL_INDEXERS[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No active indexers found in cross-seed database${NC}"
    echo "Make sure cross-seed is configured with Prowlarr indexers"
    exit 1
fi

# Build target tracker list
declare -A INDEXER_MAP
declare -a TARGET_IDS
declare -a TARGET_NAMES
i=1

for indexer in "${ALL_INDEXERS[@]}"; do
    ID=$(echo "$indexer" | cut -d'|' -f1)
    NAME=$(echo "$indexer" | cut -d'|' -f2)

    # Check if this is a target tracker
    for target in "${TARGET_TRACKERS[@]}"; do
        if [ "$NAME" = "$target" ]; then
            INDEXER_MAP[$i]="$ID|$NAME"
            TARGET_IDS+=("$ID")
            TARGET_NAMES+=("$NAME")
            ((i++))
            break
        fi
    done
done

if [ ${#TARGET_NAMES[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No target trackers found in database${NC}"
    echo "Make sure target trackers are configured in Prowlarr"
    exit 1
fi

# Display target trackers
echo -e "${YELLOW}Target upload trackers:${NC}"
echo ""

i=1
for idx in "${!TARGET_NAMES[@]}"; do
    printf "${GREEN}%d${NC}) ${YELLOW}%s${NC}\n" "$i" "${TARGET_NAMES[$idx]}"
    ((i++))
done

echo ""
echo -e "${CYAN}This will check ALL cross-seed results from ALL trackers${NC}"
echo -e "${CYAN}to find torrents missing from the selected targets.${NC}"
echo ""
echo -e "${YELLOW}Select target trackers to check:${NC}"
echo -e "${CYAN}Enter numbers separated by spaces (e.g., '1 3')${NC}"
echo -e "${CYAN}Or press Enter for all targets${NC}"
read -r SELECTION

# Parse selection
declare -a SELECTED_IDS
declare -a SELECTED_NAMES

if [ -z "$SELECTION" ]; then
    # Default: select all target trackers
    SELECTED_IDS=("${TARGET_IDS[@]}")
    SELECTED_NAMES=("${TARGET_NAMES[@]}")
else
    for num in $SELECTION; do
        if [ -n "${INDEXER_MAP[$num]}" ]; then
            ID=$(echo "${INDEXER_MAP[$num]}" | cut -d'|' -f1)
            NAME=$(echo "${INDEXER_MAP[$num]}" | cut -d'|' -f2)
            SELECTED_IDS+=("$ID")
            SELECTED_NAMES+=("$NAME")
        else
            echo -e "${RED}Warning: Invalid selection '$num' - skipping${NC}"
        fi
    done
fi

if [ ${#SELECTED_IDS[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No valid trackers selected${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Selected trackers:${NC}"
for name in "${SELECTED_NAMES[@]}"; do
    echo -e "  ${BLUE}▪${NC} $name"
done
echo ""

# Build SQL WHERE clause for selected indexers
INDEXER_IDS_SQL=$(IFS=','; echo "${SELECTED_IDS[*]}")

echo -e "${CYAN}Searching for missing torrents...${NC}"
echo ""

# Function to get tracker abbreviation from full name
get_tracker_abbr() {
    local full_name="$1"
    case "$full_name" in
        *"Aither"*) echo "ATH" ;;
        *"Anthelion"*) echo "ANT" ;;
        *"Blutopia"*) echo "BLU" ;;
        *"Nebulance"*) echo "NBL" ;;
        *"TorrentLeech"*) echo "TL" ;;
        *"FileList"*) echo "FL" ;;
        *) echo "" ;;
    esac
}

# ============================================================================
# ATH Slot System Functions
# ============================================================================

# Parse resolution from torrent name
get_resolution() {
    local name="$1"
    if [[ "$name" =~ 2160p|4K|UHD ]]; then
        echo "2160p"
    elif [[ "$name" =~ 1080p ]]; then
        echo "1080p"
    elif [[ "$name" =~ 720p ]]; then
        echo "720p"
    else
        echo "unknown"
    fi
}

# Parse codec from torrent name
get_codec() {
    local name="$1"
    if [[ "$name" =~ [xXhH]\.?265|HEVC ]]; then
        echo "H.265"
    elif [[ "$name" =~ [xXhH]\.?264 ]]; then
        echo "H.264"
    elif [[ "$name" =~ AV1 ]]; then
        echo "AV1"
    else
        echo "unknown"
    fi
}

# Parse HDR type from torrent name
get_hdr_type() {
    local name="$1"
    local hdr_type=""

    # Check for Dolby Vision
    if [[ "$name" =~ DV|DoVi|Dolby\.?Vision ]]; then
        hdr_type="DV"
    fi

    # Check for HDR variants
    if [[ "$name" =~ HDR10\+ ]]; then
        hdr_type="${hdr_type}+HDR10+"
    elif [[ "$name" =~ HDR10 ]]; then
        hdr_type="${hdr_type}+HDR10"
    elif [[ "$name" =~ HDR ]]; then
        hdr_type="${hdr_type}+HDR"
    fi

    # Check for SDR
    if [[ "$name" =~ SDR ]]; then
        hdr_type="SDR"
    fi

    # Clean up leading + and handle DV+HDR combinations
    hdr_type="${hdr_type#+}"

    if [[ -z "$hdr_type" ]]; then
        echo "unknown"
    else
        echo "$hdr_type"
    fi
}

# Parse source type from torrent name
get_source_type() {
    local name="$1"

    if [[ "$name" =~ REMUX|Remux ]]; then
        echo "REMUX"
    elif [[ "$name" =~ WEB-DL|WEBDL|WEB\.DL ]]; then
        echo "WEB-DL"
    elif [[ "$name" =~ WEBRip|WEB-Rip ]]; then
        echo "WEBDL"  # ATH treats WEBRip same as WEB-DL for slot purposes
    elif [[ "$name" =~ BluRay|Blu-ray|UHD\.BluRay ]]; then
        echo "ENCODE"
    else
        echo "unknown"
    fi
}

# Classify torrent into ATH slot category
classify_ath_slot() {
    local name="$1"
    local resolution=$(get_resolution "$name")
    local codec=$(get_codec "$name")
    local hdr=$(get_hdr_type "$name")
    local source=$(get_source_type "$name")

    # Build slot identifier (using : as separator to avoid conflict with | field delimiter)
    local slot="${resolution}:${source}:${codec}:${hdr}"
    echo "$slot"
}

# Check if torrent has ambiguous classification
is_ambiguous_classification() {
    local slot="$1"
    if [[ "$slot" =~ unknown ]]; then
        echo "true"
    else
        echo "false"
    fi
}

# ============================================================================
# TMDB and Aither API Functions
# ============================================================================

# API Keys
TMDB_API_KEY="773db029ad39c7e6639e984b6c0cab6b"
AITHER_API_KEY="3gNJnbif3QCzY3dOgB1IycBMSh16NnuNh0Pq9T9advKal8RC0H9Dgcg2IdqkvuS1PMILcRrh4tUrxjTKAUTH9CdOEUZcRz8U1jup"

# API URLs
TMDB_API_URL="https://api.themoviedb.org/3"
AITHER_API_URL="https://aither.cc/api/torrents/filter"

# Extract movie title and year from torrent name
extract_movie_info() {
    local name="$1"

    # Common pattern: Movie.Title.YEAR.resolution...
    if [[ "$name" =~ ^(.+)\.(19[0-9]{2}|20[0-9]{2})\. ]]; then
        local title="${BASH_REMATCH[1]}"
        local year="${BASH_REMATCH[2]}"

        # Clean up title (replace dots/underscores with spaces)
        title="${title//[\._]/ }"

        echo "${title}|${year}"
    else
        echo "unknown|unknown"
    fi
}

# Query TMDB API for movie ID
get_tmdb_id() {
    local title="$1"
    local year="$2"

    # URL encode the title
    local encoded_title=$(echo "$title" | sed 's/ /%20/g')

    # Query TMDB API
    local response=$(curl -s "${TMDB_API_URL}/search/movie?api_key=${TMDB_API_KEY}&query=${encoded_title}&year=${year}" 2>/dev/null)

    # Extract first result's ID
    local tmdb_id=$(echo "$response" | jq -r '.results[0].id // empty' 2>/dev/null)

    if [ -n "$tmdb_id" ]; then
        echo "$tmdb_id"
    else
        echo "unknown"
    fi
}

# Query Aither API for existing torrents
# Returns: slot classifications of existing torrents for the movie/show
query_aither_existing_slots() {
    local tmdb_id="$1"
    local category_id="$2"  # 1=movie, 2=tv

    # Query API for all torrents matching this TMDB ID
    local response=$(curl -s "${AITHER_API_URL}?api_token=${AITHER_API_KEY}&tmdbId=${tmdb_id}&categories[]=${category_id}" 2>/dev/null)

    # Parse response and extract slot classifications from torrent names
    echo "$response" | jq -r '.data[].attributes.name' 2>/dev/null | while read -r torrent_name; do
        [ -z "$torrent_name" ] && continue
        classify_ath_slot "$torrent_name"
    done
}

# Query for each tracker separately to get organized results
for idx in "${!SELECTED_IDS[@]}"; do
    TRACKER_ID="${SELECTED_IDS[$idx]}"
    TRACKER_NAME="${SELECTED_NAMES[$idx]}"
    OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"

    # Get tracker domain pattern from indexer name
    TRACKER_PATTERN=$(sqlite3 "$DB" "SELECT LOWER(REPLACE(REPLACE(name, ' (API)', ''), '+', '')) FROM indexer WHERE id = $TRACKER_ID;")

    # Check if this is Anthelion (movies only) or other trackers (movies + TV)
    MOVIES_ONLY=false
    if [[ "$TRACKER_NAME" == "Anthelion"* ]]; then
        MOVIES_ONLY=true
    fi

    # Build category filter based on tracker type
    if [ "$MOVIES_ONLY" = true ]; then
        CATEGORY_FILTER="AND cs.category = 'movies'"
    else
        CATEGORY_FILTER="AND cs.category IN ('movies', 'tvshows')"
    fi

    # Query for missing torrents on this specific tracker (movies)
    sqlite3 "$DB" <<EOF > "${OUTPUT_FILE}.movies"
.mode list
.separator "|"

SELECT DISTINCT
    s.name,
    COALESCE(cs.length, 0) as file_size,
    datetime(s.last_searched, 'unixepoch') as last_search_date,
    CASE
        WHEN cs.tags IS NULL THEN ''
        WHEN cs.tags LIKE '%cross-seed%' THEN ''
        WHEN json_extract(cs.tags, '\$[0]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[0]'), '[', ''), ']', '')
        WHEN json_extract(cs.tags, '\$[1]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[1]'), '[', ''), ']', '')
        WHEN json_extract(cs.tags, '\$[2]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[2]'), '[', ''), ']', '')
        ELSE ''
    END as original_tracker
FROM searchee s
LEFT JOIN client_searchee cs ON s.name = cs.name AND (cs.tags NOT LIKE '%cross-seed%' OR cs.tags IS NULL)
WHERE
    -- MUST have at least one MATCH somewhere (this filters to actual cross-seed finds)
    EXISTS (
        SELECT 1 FROM decision d_any
        WHERE d_any.searchee_id = s.id
        AND d_any.decision = 'MATCH'
    )
    -- But has no match on this specific tracker (check GUID domain)
    AND NOT EXISTS (
        SELECT 1 FROM decision d
        WHERE d.searchee_id = s.id
        AND d.decision = 'MATCH'
        AND LOWER(d.guid) LIKE '%$TRACKER_PATTERN%'
    )
    -- Filter to video content only
    AND (
        s.name LIKE '%1080p%' OR
        s.name LIKE '%2160p%' OR
        s.name LIKE '%720p%' OR
        s.name LIKE '%4K%' OR
        s.name LIKE '%UHD%' OR
        s.name LIKE '%BluRay%' OR
        s.name LIKE '%BDRip%' OR
        s.name LIKE '%WEB%' OR
        s.name LIKE '%AMZN%' OR
        s.name LIKE '%NF%' OR
        s.name LIKE '%DSNP%' OR
        s.name LIKE '%HMAX%' OR
        s.name LIKE '%iT%' OR
        s.name LIKE '%MA%'
    )
    -- Exclude likely false positives
    AND s.name NOT LIKE '%sample%'
    AND s.name NOT LIKE '%trailer%'
    -- Only include movies
    AND EXISTS (
        SELECT 1 FROM client_searchee cs
        WHERE cs.name = s.name
        AND cs.category = 'movies'
    )
    -- Exclude pre-retail releases (banned on ANT)
    AND s.name NOT LIKE '%CAM%'
    AND s.name NOT LIKE '%HDCAM%'
    AND s.name NOT LIKE '%.TS.%'
    AND s.name NOT LIKE '%.TC.%'
    AND s.name NOT LIKE '%R5%'
    AND s.name NOT LIKE '%DVDScr%'
    AND s.name NOT LIKE '%DVDSCR%'
    AND s.name NOT LIKE '%HDRip%'
    AND s.name NOT LIKE '%HDRIP%'
    AND s.name NOT LIKE '%VODRip%'
    AND s.name NOT LIKE '%VODRIP%'
    AND s.name NOT LIKE '%WORKPRINT%'
    -- Exclude low quality/banned formats (ANT rules)
    AND s.name NOT LIKE '%BRrip%'
    AND s.name NOT LIKE '%BRRip%'
    AND s.name NOT LIKE '%BRRIP%'
    AND s.name NOT LIKE '%mHD%'
    AND s.name NOT LIKE '%nHD%'
    AND s.name NOT LIKE '%nSD%'
    AND s.name NOT LIKE '%mSD%'
    AND s.name NOT LIKE '%PSP%'
    AND s.name NOT LIKE '%iPad%'
    -- ANT Forbidden Groups (from Anthelion tracker rules)
    AND s.name NOT LIKE '%-3LTON%' AND s.name NOT LIKE '%-4yEo%'
    AND s.name NOT LIKE '%-ADE%' AND s.name NOT LIKE '%-AFG%' AND s.name NOT LIKE '%-AniHLS%' AND s.name NOT LIKE '%-AnimeRG%' AND s.name NOT LIKE '%-AniURL%' AND s.name NOT LIKE '%-AOC%' AND s.name NOT LIKE '%-AROMA%' AND s.name NOT LIKE '%-aXXo%'
    AND s.name NOT LIKE '%-BdC%' AND s.name NOT LIKE '%-beAst%'
    AND s.name NOT LIKE '%-CHD%' AND s.name NOT LIKE '%-CM8%' AND s.name NOT LIKE '%-CrEwSaDe%'
    AND s.name NOT LIKE '%-d3g%' AND s.name NOT LIKE '%-DDR%' AND s.name NOT LIKE '%-DeadFish%' AND s.name NOT LIKE '%-DEViSE%' AND s.name NOT LIKE '%-DNL%'
    AND s.name NOT LIKE '%-ELiTE%' AND s.name NOT LIKE '%-eSc%' AND s.name NOT LIKE '%-EVO%'
    AND s.name NOT LIKE '%-FaNGDiNG0%' AND s.name NOT LIKE '%-FGT%' AND s.name NOT LIKE '%-FRDS%' AND s.name NOT LIKE '%-FUM%' AND s.name NOT LIKE '%-FZHD%'
    AND s.name NOT LIKE '%-HAiKU%' AND s.name NOT LIKE '%-HD2DVD%' AND s.name NOT LIKE '%-HDH%' AND s.name NOT LIKE '%-HDS%' AND s.name NOT LIKE '%-HDTime%' AND s.name NOT LIKE '%-Hi10%'
    AND s.name NOT LIKE '%-IMAGiNE%' AND s.name NOT LIKE '%-ION10%' AND s.name NOT LIKE '%-iPlanet%'
    AND s.name NOT LIKE '%-JIVE%'
    AND s.name NOT LIKE '%-KingBen%' AND s.name NOT LIKE '%-KiNGDOM%' AND s.name NOT LIKE '%-KLAXXON%'
    AND s.name NOT LIKE '%-LAMA%' AND s.name NOT LIKE '%-Leffe%' AND s.name NOT LIKE '%-LiGaS%' AND s.name NOT LIKE '%-LOAD%' AND s.name NOT LIKE '%-LTRG%'
    AND s.name NOT LIKE '%-MeGusta%' AND s.name NOT LIKE '%-mHD%' AND s.name NOT LIKE '%-MkvCage%' AND s.name NOT LIKE '%-mSD%'
    AND s.name NOT LIKE '%-NhaNc3%' AND s.name NOT LIKE '%-nHD%' AND s.name NOT LIKE '%-nSD%' AND s.name NOT LIKE '%-NOIVTC%'
    AND s.name NOT LIKE '%-Oj%' AND s.name NOT LIKE '%-Ozlem%'
    AND s.name NOT LIKE '%-PiRaTeS%' AND s.name NOT LIKE '%-PrisM%' AND s.name NOT LIKE '%-PRoDJi%' AND s.name NOT LIKE '%-PxHD%' AND s.name NOT LIKE '%-PxHDMobies%'
    AND s.name NOT LIKE '%-RAPiDCOWS%' AND s.name NOT LIKE '%-RARBG%' AND s.name NOT LIKE '%-RDN%' AND s.name NOT LIKE '%-REsuRRecTioN%' AND s.name NOT LIKE '%-RetroPeeps%' AND s.name NOT LIKE '%-RMTeam%' AND s.name NOT LIKE '%-Rx%'
    AND s.name NOT LIKE '%-SANTi%' AND s.name NOT LIKE '%-SicFoI%' AND s.name NOT LIKE '%-SM737%' AND s.name NOT LIKE '%-SPASM%' AND s.name NOT LIKE '%-SPDVD%' AND s.name NOT LIKE '%-STUTTERSHIT%'
    AND s.name NOT LIKE '%-TBS%' AND s.name NOT LIKE '%-Telly%' AND s.name NOT LIKE '%-TM%'
    AND s.name NOT LIKE '%-UPiNSMOKE%' AND s.name NOT LIKE '%-URANiME%'
    AND s.name NOT LIKE '%-ViSiON%'
    AND s.name NOT LIKE '%-WAF%' AND s.name NOT LIKE '%-WHiiZz%' AND s.name NOT LIKE '%-WORLD%'
    AND s.name NOT LIKE '%-xRed%' AND s.name NOT LIKE '%-XS%'
    AND s.name NOT LIKE '%-YIFY%' AND s.name NOT LIKE '%-YTS%'
    AND s.name NOT LIKE '%-Zeus%' AND s.name NOT LIKE '%-ZKBL%' AND s.name NOT LIKE '%-ZmN%' AND s.name NOT LIKE '%-ZMNT%'
    -- ATH Blacklisted Groups (from Aither tracker rules)
    AND s.name NOT LIKE '%-4K4U%' AND s.name NOT LIKE '%-afm72%' AND s.name NOT LIKE '%-Bandi%'
    AND s.name NOT LIKE '%-BiTOR%' AND s.name NOT LIKE '%-Bluespots%' AND s.name NOT LIKE '%-BOLS%'
    AND s.name NOT LIKE '%-Chivaman%' AND s.name NOT LIKE '%-DepraveD%' AND s.name NOT LIKE '%-edge2020%' AND s.name NOT LIKE '%-EMBER%'
    AND s.name NOT LIKE '%-Flights%' AND s.name NOT LIKE '%-FreetheFish%' AND s.name NOT LIKE '%-Garshasp%' AND s.name NOT LIKE '%-Ghost%' AND s.name NOT LIKE '%-Grym%'
    AND s.name NOT LIKE '%-HDT%' AND s.name NOT LIKE '%-HiQVE%'
    AND s.name NOT LIKE '%-ImE%' AND s.name NOT LIKE '%-iVy%' AND s.name NOT LIKE '%-Judas%'
    AND s.name NOT LIKE '%-Langbard%' AND s.name NOT LIKE '%-LION%' AND s.name NOT LIKE '%-MONOLITH%' AND s.name NOT LIKE '%-MRCS%'
    AND s.name NOT LIKE '%-Natty%' AND s.name NOT LIKE '%-nikt0%' AND s.name NOT LIKE '%-noxxus%'
    AND s.name NOT LIKE '%-OEPlus%' AND s.name NOT LIKE '%-OFT%' AND s.name NOT LIKE '%-OsC%'
    AND s.name NOT LIKE '%-Panda%' AND s.name NOT LIKE '%-PHOCiS%' AND s.name NOT LIKE '%-PYC%'
    AND s.name NOT LIKE '%-QxR%' AND s.name NOT LIKE '%-r00t%' AND s.name NOT LIKE '%-Ralphy%' AND s.name NOT LIKE '%-RCVR%' AND s.name NOT LIKE '%-RZeroX%'
    AND s.name NOT LIKE '%-SAMPA%' AND s.name NOT LIKE '%-SasukeducK%' AND s.name NOT LIKE '%-Sicario%' AND s.name NOT LIKE '%-SiCFoI%' AND s.name NOT LIKE '%-Silence%' AND s.name NOT LIKE '%-SkipTT%' AND s.name NOT LIKE '%-SWTYBLZ%'
    AND s.name NOT LIKE '%-t3nzin%' AND s.name NOT LIKE '%-TAoE%' AND s.name NOT LIKE '%-TEKNO3D%' AND s.name NOT LIKE '%-TGx%' AND s.name NOT LIKE '%-Tigole%' AND s.name NOT LIKE '%-TSP%' AND s.name NOT LIKE '%-TSPxL%'
    AND s.name NOT LIKE '%-UnKn0wn%' AND s.name NOT LIKE '%-VXT%' AND s.name NOT LIKE '%-Vyndros%'
    AND s.name NOT LIKE '%-W32%' AND s.name NOT LIKE '%-Weasley%' AND s.name NOT LIKE '%-Will1869%'
    AND s.name NOT LIKE '%-x0r%' AND s.name NOT LIKE '%-YAWNiX%'
ORDER BY s.last_searched DESC
LIMIT 150;
EOF

    # If tracker allows TV shows, run separate query for TV shows
    if [ "$MOVIES_ONLY" = false ]; then
        sqlite3 "$DB" <<EOF > "${OUTPUT_FILE}.tvshows"
.mode list
.separator "|"

SELECT DISTINCT
    s.name,
    COALESCE(cs.length, 0) as file_size,
    datetime(s.last_searched, 'unixepoch') as last_search_date,
    CASE
        WHEN cs.tags IS NULL THEN ''
        WHEN cs.tags LIKE '%cross-seed%' THEN ''
        WHEN json_extract(cs.tags, '\$[0]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[0]'), '[', ''), ']', '')
        WHEN json_extract(cs.tags, '\$[1]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[1]'), '[', ''), ']', '')
        WHEN json_extract(cs.tags, '\$[2]') LIKE '[%' THEN REPLACE(REPLACE(json_extract(cs.tags, '\$[2]'), '[', ''), ']', '')
        ELSE ''
    END as original_tracker
FROM searchee s
LEFT JOIN client_searchee cs ON s.name = cs.name AND (cs.tags NOT LIKE '%cross-seed%' OR cs.tags IS NULL)
WHERE
    -- MUST have at least one MATCH somewhere
    EXISTS (
        SELECT 1 FROM decision d_any
        WHERE d_any.searchee_id = s.id
        AND d_any.decision = 'MATCH'
    )
    -- But has no match on this specific tracker
    AND NOT EXISTS (
        SELECT 1 FROM decision d
        WHERE d.searchee_id = s.id
        AND d.decision = 'MATCH'
        AND LOWER(d.guid) LIKE '%$TRACKER_PATTERN%'
    )
    -- Filter to video content only
    AND (
        s.name LIKE '%1080p%' OR
        s.name LIKE '%2160p%' OR
        s.name LIKE '%720p%' OR
        s.name LIKE '%4K%' OR
        s.name LIKE '%UHD%' OR
        s.name LIKE '%BluRay%' OR
        s.name LIKE '%BDRip%' OR
        s.name LIKE '%WEB%' OR
        s.name LIKE '%AMZN%' OR
        s.name LIKE '%NF%' OR
        s.name LIKE '%DSNP%' OR
        s.name LIKE '%HMAX%' OR
        s.name LIKE '%iT%' OR
        s.name LIKE '%MA%'
    )
    -- Exclude likely false positives
    AND s.name NOT LIKE '%sample%'
    AND s.name NOT LIKE '%trailer%'
    -- Only include TV shows
    AND EXISTS (
        SELECT 1 FROM client_searchee cs
        WHERE cs.name = s.name
        AND cs.category = 'tvshows'
    )
    -- Exclude pre-retail releases
    AND s.name NOT LIKE '%CAM%'
    AND s.name NOT LIKE '%HDCAM%'
    AND s.name NOT LIKE '%.TS.%'
    AND s.name NOT LIKE '%.TC.%'
    AND s.name NOT LIKE '%R5%'
    AND s.name NOT LIKE '%DVDScr%'
    AND s.name NOT LIKE '%DVDSCR%'
    AND s.name NOT LIKE '%HDRip%'
    AND s.name NOT LIKE '%HDRIP%'
    AND s.name NOT LIKE '%VODRip%'
    AND s.name NOT LIKE '%VODRIP%'
    AND s.name NOT LIKE '%WORKPRINT%'
    -- Exclude low quality/banned formats
    AND s.name NOT LIKE '%BRrip%'
    AND s.name NOT LIKE '%BRRip%'
    AND s.name NOT LIKE '%BRRIP%'
    AND s.name NOT LIKE '%mHD%'
    AND s.name NOT LIKE '%nHD%'
    AND s.name NOT LIKE '%nSD%'
    AND s.name NOT LIKE '%mSD%'
    AND s.name NOT LIKE '%PSP%'
    AND s.name NOT LIKE '%iPad%'
    -- ANT Forbidden Groups
    AND s.name NOT LIKE '%-3LTON%' AND s.name NOT LIKE '%-4yEo%'
    AND s.name NOT LIKE '%-ADE%' AND s.name NOT LIKE '%-AFG%' AND s.name NOT LIKE '%-AniHLS%' AND s.name NOT LIKE '%-AnimeRG%' AND s.name NOT LIKE '%-AniURL%' AND s.name NOT LIKE '%-AOC%' AND s.name NOT LIKE '%-AROMA%' AND s.name NOT LIKE '%-aXXo%'
    AND s.name NOT LIKE '%-BdC%' AND s.name NOT LIKE '%-beAst%'
    AND s.name NOT LIKE '%-CHD%' AND s.name NOT LIKE '%-CM8%' AND s.name NOT LIKE '%-CrEwSaDe%'
    AND s.name NOT LIKE '%-d3g%' AND s.name NOT LIKE '%-DDR%' AND s.name NOT LIKE '%-DeadFish%' AND s.name NOT LIKE '%-DEViSE%' AND s.name NOT LIKE '%-DNL%'
    AND s.name NOT LIKE '%-ELiTE%' AND s.name NOT LIKE '%-eSc%' AND s.name NOT LIKE '%-EVO%'
    AND s.name NOT LIKE '%-FaNGDiNG0%' AND s.name NOT LIKE '%-FGT%' AND s.name NOT LIKE '%-FRDS%' AND s.name NOT LIKE '%-FUM%' AND s.name NOT LIKE '%-FZHD%'
    AND s.name NOT LIKE '%-HAiKU%' AND s.name NOT LIKE '%-HD2DVD%' AND s.name NOT LIKE '%-HDH%' AND s.name NOT LIKE '%-HDS%' AND s.name NOT LIKE '%-HDTime%' AND s.name NOT LIKE '%-Hi10%'
    AND s.name NOT LIKE '%-IMAGiNE%' AND s.name NOT LIKE '%-ION10%' AND s.name NOT LIKE '%-iPlanet%'
    AND s.name NOT LIKE '%-JIVE%'
    AND s.name NOT LIKE '%-KingBen%' AND s.name NOT LIKE '%-KiNGDOM%' AND s.name NOT LIKE '%-KLAXXON%'
    AND s.name NOT LIKE '%-LAMA%' AND s.name NOT LIKE '%-Leffe%' AND s.name NOT LIKE '%-LiGaS%' AND s.name NOT LIKE '%-LOAD%' AND s.name NOT LIKE '%-LTRG%'
    AND s.name NOT LIKE '%-MeGusta%' AND s.name NOT LIKE '%-mHD%' AND s.name NOT LIKE '%-MkvCage%' AND s.name NOT LIKE '%-mSD%'
    AND s.name NOT LIKE '%-NhaNc3%' AND s.name NOT LIKE '%-nHD%' AND s.name NOT LIKE '%-nSD%' AND s.name NOT LIKE '%-NOIVTC%'
    AND s.name NOT LIKE '%-Oj%' AND s.name NOT LIKE '%-Ozlem%'
    AND s.name NOT LIKE '%-PiRaTeS%' AND s.name NOT LIKE '%-PrisM%' AND s.name NOT LIKE '%-PRoDJi%' AND s.name NOT LIKE '%-PxHD%' AND s.name NOT LIKE '%-PxHDMobies%'
    AND s.name NOT LIKE '%-RAPiDCOWS%' AND s.name NOT LIKE '%-RARBG%' AND s.name NOT LIKE '%-RDN%' AND s.name NOT LIKE '%-REsuRRecTioN%' AND s.name NOT LIKE '%-RetroPeeps%' AND s.name NOT LIKE '%-RMTeam%' AND s.name NOT LIKE '%-Rx%'
    AND s.name NOT LIKE '%-SANTi%' AND s.name NOT LIKE '%-SicFoI%' AND s.name NOT LIKE '%-SM737%' AND s.name NOT LIKE '%-SPASM%' AND s.name NOT LIKE '%-SPDVD%' AND s.name NOT LIKE '%-STUTTERSHIT%'
    AND s.name NOT LIKE '%-TBS%' AND s.name NOT LIKE '%-Telly%' AND s.name NOT LIKE '%-TM%'
    AND s.name NOT LIKE '%-UPiNSMOKE%' AND s.name NOT LIKE '%-URANiME%'
    AND s.name NOT LIKE '%-ViSiON%'
    AND s.name NOT LIKE '%-WAF%' AND s.name NOT LIKE '%-WHiiZz%' AND s.name NOT LIKE '%-WORLD%'
    AND s.name NOT LIKE '%-xRed%' AND s.name NOT LIKE '%-XS%'
    AND s.name NOT LIKE '%-YIFY%' AND s.name NOT LIKE '%-YTS%'
    AND s.name NOT LIKE '%-Zeus%' AND s.name NOT LIKE '%-ZKBL%' AND s.name NOT LIKE '%-ZmN%' AND s.name NOT LIKE '%-ZMNT%'
    -- ATH Blacklisted Groups
    AND s.name NOT LIKE '%-4K4U%' AND s.name NOT LIKE '%-afm72%' AND s.name NOT LIKE '%-Bandi%'
    AND s.name NOT LIKE '%-BiTOR%' AND s.name NOT LIKE '%-Bluespots%' AND s.name NOT LIKE '%-BOLS%'
    AND s.name NOT LIKE '%-Chivaman%' AND s.name NOT LIKE '%-DepraveD%' AND s.name NOT LIKE '%-edge2020%' AND s.name NOT LIKE '%-EMBER%'
    AND s.name NOT LIKE '%-Flights%' AND s.name NOT LIKE '%-FreetheFish%' AND s.name NOT LIKE '%-Garshasp%' AND s.name NOT LIKE '%-Ghost%' AND s.name NOT LIKE '%-Grym%'
    AND s.name NOT LIKE '%-HDT%' AND s.name NOT LIKE '%-HiQVE%'
    AND s.name NOT LIKE '%-ImE%' AND s.name NOT LIKE '%-iVy%' AND s.name NOT LIKE '%-Judas%'
    AND s.name NOT LIKE '%-Langbard%' AND s.name NOT LIKE '%-LION%' AND s.name NOT LIKE '%-MONOLITH%' AND s.name NOT LIKE '%-MRCS%'
    AND s.name NOT LIKE '%-Natty%' AND s.name NOT LIKE '%-nikt0%' AND s.name NOT LIKE '%-noxxus%'
    AND s.name NOT LIKE '%-OEPlus%' AND s.name NOT LIKE '%-OFT%' AND s.name NOT LIKE '%-OsC%'
    AND s.name NOT LIKE '%-Panda%' AND s.name NOT LIKE '%-PHOCiS%' AND s.name NOT LIKE '%-PYC%'
    AND s.name NOT LIKE '%-QxR%' AND s.name NOT LIKE '%-r00t%' AND s.name NOT LIKE '%-Ralphy%' AND s.name NOT LIKE '%-RCVR%' AND s.name NOT LIKE '%-RZeroX%'
    AND s.name NOT LIKE '%-SAMPA%' AND s.name NOT LIKE '%-SasukeducK%' AND s.name NOT LIKE '%-Sicario%' AND s.name NOT LIKE '%-SiCFoI%' AND s.name NOT LIKE '%-Silence%' AND s.name NOT LIKE '%-SkipTT%' AND s.name NOT LIKE '%-SWTYBLZ%'
    AND s.name NOT LIKE '%-t3nzin%' AND s.name NOT LIKE '%-TAoE%' AND s.name NOT LIKE '%-TEKNO3D%' AND s.name NOT LIKE '%-TGx%' AND s.name NOT LIKE '%-Tigole%' AND s.name NOT LIKE '%-TSP%' AND s.name NOT LIKE '%-TSPxL%'
    AND s.name NOT LIKE '%-UnKn0wn%' AND s.name NOT LIKE '%-VXT%' AND s.name NOT LIKE '%-Vyndros%'
    AND s.name NOT LIKE '%-W32%' AND s.name NOT LIKE '%-Weasley%' AND s.name NOT LIKE '%-Will1869%'
    AND s.name NOT LIKE '%-x0r%' AND s.name NOT LIKE '%-YAWNiX%'
ORDER BY s.last_searched DESC
LIMIT 150;
EOF
    fi

    # Combine results
    cat "${OUTPUT_FILE}.movies" > "$OUTPUT_FILE" 2>/dev/null || true
    if [ -f "${OUTPUT_FILE}.tvshows" ]; then
        cat "${OUTPUT_FILE}.tvshows" >> "$OUTPUT_FILE" 2>/dev/null || true
    fi

    # Count results (only count non-empty lines)
    MOVIES_COUNT=0
    TV_COUNT=0
    if [ -f "${OUTPUT_FILE}.movies" ] && [ -s "${OUTPUT_FILE}.movies" ]; then
        MOVIES_COUNT=$(grep -c '.' "${OUTPUT_FILE}.movies" 2>/dev/null || echo "0")
    fi
    if [ -f "${OUTPUT_FILE}.tvshows" ] && [ -s "${OUTPUT_FILE}.tvshows" ]; then
        TV_COUNT=$(grep -c '.' "${OUTPUT_FILE}.tvshows" 2>/dev/null || echo "0")
    fi
    RESULT_COUNT=$((MOVIES_COUNT + TV_COUNT))

    # Save full unfiltered list to timestamped file (no display)
done

# Summary
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║ Summary                                                    ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL_FOUND=0
for idx in "${!SELECTED_NAMES[@]}"; do
    TRACKER_NAME="${SELECTED_NAMES[$idx]}"
    OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"
    COUNT=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo "0")
    TOTAL_FOUND=$((TOTAL_FOUND + COUNT))
    printf "${GREEN}%-30s${NC}: ${YELLOW}%d${NC} missing torrents\n" "$TRACKER_NAME" "$COUNT"
done

echo ""
echo -e "${YELLOW}Total missing torrents found: ${TOTAL_FOUND}${NC}"
echo ""

# Create grouped summary showing which torrents are missing from multiple trackers
if [ ${#SELECTED_NAMES[@]} -gt 1 ]; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║ ${YELLOW}Multi-Tracker Upload Opportunities${GREEN} - Missing from ALL ${#SELECTED_NAMES[@]} trackers${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Create temporary file to track torrent appearances with size
    TEMP_ANALYSIS="$OUTPUT_DIR/torrent_analysis.tmp"
    > "$TEMP_ANALYSIS"

    # Check if ALL selected trackers support TV shows and build tracker abbreviation string
    ALL_SUPPORT_TV=true
    TRACKER_ABBRS=""
    for idx in "${!SELECTED_NAMES[@]}"; do
        TRACKER_NAME="${SELECTED_NAMES[$idx]}"
        if [[ "$TRACKER_NAME" == "Anthelion"* ]]; then
            ALL_SUPPORT_TV=false
        fi
        # Build tracker abbreviation string for filenames
        case "$TRACKER_NAME" in
            "Aither (API)") TRACKER_ABBRS="${TRACKER_ABBRS}_ATH" ;;
            "Anthelion (API)") TRACKER_ABBRS="${TRACKER_ABBRS}_ANT" ;;
            "Blutopia (API)") TRACKER_ABBRS="${TRACKER_ABBRS}_BLU" ;;
            "Nebulance") TRACKER_ABBRS="${TRACKER_ABBRS}_NBL" ;;
        esac
    done
    # Remove leading underscore
    TRACKER_ABBRS="${TRACKER_ABBRS#_}"

    # Analyze each torrent across all selected trackers (Movies)
    TEMP_MOVIES="$OUTPUT_DIR/torrent_analysis_movies.tmp"
    > "$TEMP_MOVIES"
    for idx in "${!SELECTED_NAMES[@]}"; do
        TRACKER_NAME="${SELECTED_NAMES[$idx]}"
        OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"

        # Get current tracker abbreviation
        CURRENT_TRACKER_ABBR=$(get_tracker_abbr "$TRACKER_NAME")

        if [ -f "${OUTPUT_FILE}.movies" ]; then
            while IFS='|' read -r torrent_name size date original_tracker; do
                [ -z "$torrent_name" ] && continue

                # Get source tracker abbreviation
                SOURCE_TRACKER_ABBR=$(get_tracker_abbr "$original_tracker")

                # Skip if trying to upload back to source tracker
                if [ -n "$SOURCE_TRACKER_ABBR" ] && [ "$SOURCE_TRACKER_ABBR" = "$CURRENT_TRACKER_ABBR" ]; then
                    continue  # Skip this torrent for this tracker
                fi

                echo "$torrent_name|$size" >> "$TEMP_MOVIES"
            done < "${OUTPUT_FILE}.movies"
        fi
    done

    # Analyze TV shows if all trackers support them
    TEMP_TV="$OUTPUT_DIR/torrent_analysis_tv.tmp"
    if [ "$ALL_SUPPORT_TV" = true ]; then
        > "$TEMP_TV"
        for idx in "${!SELECTED_NAMES[@]}"; do
            TRACKER_NAME="${SELECTED_NAMES[$idx]}"
            OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"

            # Get current tracker abbreviation
            CURRENT_TRACKER_ABBR=$(get_tracker_abbr "$TRACKER_NAME")

            if [ -f "${OUTPUT_FILE}.tvshows" ]; then
                while IFS='|' read -r torrent_name size date original_tracker; do
                    [ -z "$torrent_name" ] && continue

                    # Get source tracker abbreviation
                    SOURCE_TRACKER_ABBR=$(get_tracker_abbr "$original_tracker")

                    # Skip if trying to upload back to source tracker
                    if [ -n "$SOURCE_TRACKER_ABBR" ] && [ "$SOURCE_TRACKER_ABBR" = "$CURRENT_TRACKER_ABBR" ]; then
                        continue  # Skip this torrent for this tracker
                    fi

                    echo "$torrent_name|$size" >> "$TEMP_TV"
                done < "${OUTPUT_FILE}.tvshows"
            fi
        done
    fi

    # Find movies missing from ALL selected trackers
    if [ -f "$TEMP_MOVIES" ] && [ -s "$TEMP_MOVIES" ]; then
        # Count occurrences and get size for movies
        sort "$TEMP_MOVIES" | awk -F'|' -v target="${#SELECTED_NAMES[@]}" '
        {
            torrent = $1
            if (!size[torrent]) size[torrent] = $2  # Store first size seen
            count[torrent]++
        }
        END {
            for (t in count) {
                if (count[t] == target) {
                    print t "|" size[t]
                }
            }
        }
        ' > "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt"
    fi

    # Find TV shows missing from ALL selected trackers (if applicable)
    if [ "$ALL_SUPPORT_TV" = true ] && [ -f "$TEMP_TV" ] && [ -s "$TEMP_TV" ]; then
        # Count occurrences and get size for TV shows
        sort "$TEMP_TV" | awk -F'|' -v target="${#SELECTED_NAMES[@]}" '
        {
            torrent = $1
            if (!size[torrent]) size[torrent] = $2  # Store first size seen
            count[torrent]++
        }
        END {
            for (t in count) {
                if (count[t] == target) {
                    print t "|" size[t]
                }
            }
        }
        ' > "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt"
    fi

    # Display multi-tracker results in table format
    MULTI_MOVIES_COUNT=0
    MULTI_TV_COUNT=0
    if [ -f "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt" ]; then
        MULTI_MOVIES_COUNT=$(wc -l < "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt" 2>/dev/null || echo "0")
    fi
    if [ "$ALL_SUPPORT_TV" = true ] && [ -f "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt" ]; then
        MULTI_TV_COUNT=$(wc -l < "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt" 2>/dev/null || echo "0")
    fi

    if [ "$MULTI_MOVIES_COUNT" -gt 0 ] || [ "$MULTI_TV_COUNT" -gt 0 ]; then
        # Convert tracker names to abbreviations for upload command
        UPLOAD_TRACKERS=""
        for name in "${SELECTED_NAMES[@]}"; do
            case "$name" in
                "Aither (API)") UPLOAD_TRACKERS="$UPLOAD_TRACKERS ATH" ;;
                "Anthelion (API)") UPLOAD_TRACKERS="$UPLOAD_TRACKERS ANT" ;;
                "Blutopia (API)") UPLOAD_TRACKERS="$UPLOAD_TRACKERS BLU" ;;
                "Nebulance") UPLOAD_TRACKERS="$UPLOAD_TRACKERS NBL" ;;
            esac
        done
        UPLOAD_TRACKERS=$(echo "$UPLOAD_TRACKERS" | xargs)  # Trim spaces

        echo -e "${CYAN}Upload command: ${YELLOW}--trackers $UPLOAD_TRACKERS${NC}"
        echo ""

        # Display Movies section
        if [ "$MULTI_MOVIES_COUNT" -gt 0 ]; then
            echo -e "${CYAN}Movies (${MULTI_MOVIES_COUNT})${NC}"
            echo ""

            # Sort by size and display
            sort -t'|' -k2 -rn "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt" | awk -F'|' '
            function format_size(bytes) {
                if (bytes >= 1099511627776) return sprintf("%.2f TB", bytes/1099511627776)
                if (bytes >= 1073741824) return sprintf("%.2f GB", bytes/1073741824)
                if (bytes >= 1048576) return sprintf("%.2f MB", bytes/1048576)
                if (bytes >= 1024) return sprintf("%.2f KB", bytes/1024)
                return sprintf("%d B", bytes)
            }
            BEGIN {
                num = 1
            }
            {
                name = $1
                size = $2

                # Truncate long names
                display_name = name
                if (length(name) > 90) display_name = substr(name, 1, 87) "..."

                # Format with size
                printf "  %3d) %-92s %10s\n", num, display_name, format_size(size)
                num++
            }
            '
            echo ""
        fi

        # Display TV Shows section (if applicable)
        if [ "$MULTI_TV_COUNT" -gt 0 ]; then
            echo -e "${CYAN}TV Shows (${MULTI_TV_COUNT})${NC}"
            echo ""

            # Sort by size and display
            sort -t'|' -k2 -rn "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt" | awk -F'|' '
            function format_size(bytes) {
                if (bytes >= 1099511627776) return sprintf("%.2f TB", bytes/1099511627776)
                if (bytes >= 1073741824) return sprintf("%.2f GB", bytes/1073741824)
                if (bytes >= 1048576) return sprintf("%.2f MB", bytes/1048576)
                if (bytes >= 1024) return sprintf("%.2f KB", bytes/1024)
                return sprintf("%d B", bytes)
            }
            BEGIN {
                num = 1
            }
            {
                name = $1
                size = $2

                # Truncate long names
                display_name = name
                if (length(name) > 90) display_name = substr(name, 1, 87) "..."

                # Format with size
                printf "  %3d) %-92s %10s\n", num, display_name, format_size(size)
                num++
            }
            '
            echo ""
        fi

        echo -e "${BLUE}Full lists saved to: ${OUTPUT_DIR}/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt"
        if [ "$MULTI_TV_COUNT" -gt 0 ]; then
            echo -e "                      ${OUTPUT_DIR}/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt${NC}"
        else
            echo -e "${NC}"
        fi
        echo ""
        echo -e "${GREEN}────────────────────────────────────────────────────────────────────────────────${NC}"
        echo ""
    else
            echo -e "${YELLOW}No torrents found that are missing from ALL selected trackers${NC}"
            echo ""
        fi

        # Now display individual tracker tables, filtering out multi-tracker releases
        # Extract multi-tracker names for filtering
        if [ -f "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt" ]; then
            cut -d'|' -f1 "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_movies.txt" > "$OUTPUT_DIR/multi_names_movies.tmp"
        else
            > "$OUTPUT_DIR/multi_names_movies.tmp"
        fi
        if [ "$ALL_SUPPORT_TV" = true ] && [ -f "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt" ]; then
            cut -d'|' -f1 "$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBRS}_tv.txt" > "$OUTPUT_DIR/multi_names_tv.tmp"
        else
            > "$OUTPUT_DIR/multi_names_tv.tmp"
        fi

        for idx in "${!SELECTED_NAMES[@]}"; do
            TRACKER_NAME="${SELECTED_NAMES[$idx]}"
            OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"

            # Get tracker abbreviation for this specific tracker
            TRACKER_ABBR=""
            case "$TRACKER_NAME" in
                "Aither (API)") TRACKER_ABBR="ATH" ;;
                "Anthelion (API)") TRACKER_ABBR="ANT" ;;
                "Blutopia (API)") TRACKER_ABBR="BLU" ;;
                "Nebulance") TRACKER_ABBR="NBL" ;;
            esac

            FILTERED_MOVIES="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBR}_only_movies.txt"
            FILTERED_TV="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_ABBR}_only_tv.txt"

            # Check if this tracker is movies-only
            TRACKER_MOVIES_ONLY=false
            if [[ "$TRACKER_NAME" == "Anthelion"* ]]; then
                TRACKER_MOVIES_ONLY=true
            fi

            # Filter movies - exclude multi-tracker releases, source tracker matches, and ATH slot conflicts
            > "$FILTERED_MOVIES"
            if [ -f "${OUTPUT_FILE}.movies" ]; then
                while IFS='|' read -r torrent_name size date original_tracker; do
                    [ -z "$torrent_name" ] && continue

                    # Get source tracker abbreviation
                    SOURCE_TRACKER_ABBR=$(get_tracker_abbr "$original_tracker")

                    # Skip if trying to upload back to source tracker
                    if [ -n "$SOURCE_TRACKER_ABBR" ] && [ "$SOURCE_TRACKER_ABBR" = "$TRACKER_ABBR" ]; then
                        continue
                    fi

                    # ATH-specific slot validation
                    if [ "$TRACKER_ABBR" = "ATH" ]; then
                        # Classify this torrent's slot
                        slot=$(classify_ath_slot "$torrent_name")
                        is_ambiguous=$(is_ambiguous_classification "$slot")

                        # Extract movie info for TMDB lookup
                        movie_info=$(extract_movie_info "$torrent_name")
                        movie_title=$(echo "$movie_info" | cut -d'|' -f1)
                        movie_year=$(echo "$movie_info" | cut -d'|' -f2)

                        # Get TMDB ID (cached)
                        cache_key="${movie_title}_${movie_year}"
                        if [ -z "${TMDB_CACHE[$cache_key]}" ]; then
                            TMDB_CACHE[$cache_key]=$(get_tmdb_id "$movie_title" "$movie_year")
                        fi
                        tmdb_id="${TMDB_CACHE[$cache_key]}"

                        # Query Aither for existing slots (cached)
                        skip_due_to_slot=false
                        if [ -n "$tmdb_id" ] && [ "$tmdb_id" != "unknown" ]; then
                            if [ -z "${ATH_SLOTS_CACHE[$tmdb_id]}" ]; then
                                ATH_SLOTS_CACHE[$tmdb_id]=$(query_aither_existing_slots "$tmdb_id" "1")
                            fi
                            existing_slots="${ATH_SLOTS_CACHE[$tmdb_id]}"

                            # Check if slot is occupied
                            if echo "$existing_slots" | grep -Fxq "$slot"; then
                                skip_due_to_slot=true
                            fi
                        fi

                        # Skip if slot occupied
                        if [ "$skip_due_to_slot" = "true" ]; then
                            continue
                        fi

                        # Add to filtered list (with slot info for display)
                        if ! grep -Fxq "$torrent_name" "$OUTPUT_DIR/multi_names_movies.tmp" 2>/dev/null; then
                            echo "$torrent_name|$size|$date|$slot|$is_ambiguous" >> "$FILTERED_MOVIES"
                        fi
                    else
                        # Other trackers: original format, no slot validation
                        if ! grep -Fxq "$torrent_name" "$OUTPUT_DIR/multi_names_movies.tmp" 2>/dev/null; then
                            echo "$torrent_name|$size|$date" >> "$FILTERED_MOVIES"
                        fi
                    fi
                done < "${OUTPUT_FILE}.movies"
            fi

            # Filter TV shows - exclude multi-tracker releases, source tracker matches, and ATH slot conflicts (if tracker supports TV)
            > "$FILTERED_TV"
            if [ "$TRACKER_MOVIES_ONLY" = false ] && [ -f "${OUTPUT_FILE}.tvshows" ]; then
                while IFS='|' read -r torrent_name size date original_tracker; do
                    [ -z "$torrent_name" ] && continue

                    # Get source tracker abbreviation
                    SOURCE_TRACKER_ABBR=$(get_tracker_abbr "$original_tracker")

                    # Skip if trying to upload back to source tracker
                    if [ -n "$SOURCE_TRACKER_ABBR" ] && [ "$SOURCE_TRACKER_ABBR" = "$TRACKER_ABBR" ]; then
                        continue
                    fi

                    # ATH-specific slot validation for TV shows
                    if [ "$TRACKER_ABBR" = "ATH" ]; then
                        # Classify this torrent's slot
                        slot=$(classify_ath_slot "$torrent_name")
                        is_ambiguous=$(is_ambiguous_classification "$slot")

                        # Extract show info for TMDB lookup (simplified - same as movies for now)
                        show_info=$(extract_movie_info "$torrent_name")
                        show_title=$(echo "$show_info" | cut -d'|' -f1)
                        show_year=$(echo "$show_info" | cut -d'|' -f2)

                        # Get TMDB ID (cached) - Note: using category 2 for TV
                        cache_key="${show_title}_${show_year}_tv"
                        if [ -z "${TMDB_CACHE[$cache_key]}" ]; then
                            TMDB_CACHE[$cache_key]=$(get_tmdb_id "$show_title" "$show_year")
                        fi
                        tmdb_id="${TMDB_CACHE[$cache_key]}"

                        # Query Aither for existing slots (cached, category 2 for TV)
                        skip_due_to_slot=false
                        if [ -n "$tmdb_id" ] && [ "$tmdb_id" != "unknown" ]; then
                            cache_tv_key="${tmdb_id}_tv"
                            if [ -z "${ATH_SLOTS_CACHE[$cache_tv_key]}" ]; then
                                ATH_SLOTS_CACHE[$cache_tv_key]=$(query_aither_existing_slots "$tmdb_id" "2")
                            fi
                            existing_slots="${ATH_SLOTS_CACHE[$cache_tv_key]}"

                            # Check if slot is occupied
                            if echo "$existing_slots" | grep -Fxq "$slot"; then
                                skip_due_to_slot=true
                            fi
                        fi

                        # Skip if slot occupied
                        if [ "$skip_due_to_slot" = "true" ]; then
                            continue
                        fi

                        # Add to filtered list (with slot info for display)
                        if ! grep -Fxq "$torrent_name" "$OUTPUT_DIR/multi_names_tv.tmp" 2>/dev/null; then
                            echo "$torrent_name|$size|$date|$slot|$is_ambiguous" >> "$FILTERED_TV"
                        fi
                    else
                        # Other trackers: original format, no slot validation
                        if ! grep -Fxq "$torrent_name" "$OUTPUT_DIR/multi_names_tv.tmp" 2>/dev/null; then
                            echo "$torrent_name|$size|$date" >> "$FILTERED_TV"
                        fi
                    fi
                done < "${OUTPUT_FILE}.tvshows"
            fi

            # Count filtered results
            FILTERED_MOVIES_COUNT=0
            FILTERED_TV_COUNT=0
            if [ -f "$FILTERED_MOVIES" ] && [ -s "$FILTERED_MOVIES" ]; then
                FILTERED_MOVIES_COUNT=$(wc -l < "$FILTERED_MOVIES")
            fi
            if [ -f "$FILTERED_TV" ] && [ -s "$FILTERED_TV" ]; then
                FILTERED_TV_COUNT=$(wc -l < "$FILTERED_TV")
            fi

            # Display filtered results if there are any
            if [ "$FILTERED_MOVIES_COUNT" -gt 0 ] || [ "$FILTERED_TV_COUNT" -gt 0 ]; then
                TOTAL_FILTERED=$((FILTERED_MOVIES_COUNT + FILTERED_TV_COUNT))

                echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
                echo -e "${GREEN}║ ${YELLOW}${TRACKER_NAME}${GREEN} - ${TOTAL_FILTERED} unique releases (not on other trackers)${NC}"
                echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
                echo ""
                echo -e "${CYAN}Upload command: ${YELLOW}--trackers $TRACKER_ABBR${NC}"
                echo ""

                # Display Movies section
                if [ "$FILTERED_MOVIES_COUNT" -gt 0 ]; then
                    echo -e "${CYAN}Movies (${FILTERED_MOVIES_COUNT})${NC}"

                    # For ATH, show slot system notice
                    if [ "$TRACKER_ABBR" = "ATH" ]; then
                        echo -e "${YELLOW}  ℹ ATH Slot System: Slots validated automatically${NC}"
                        echo -e "${YELLOW}  ⚠ Slots with 'unknown' attributes need manual review${NC}"
                    fi
                    echo ""

                    # Sort by size and display
                    sort -t'|' -k2 -rn "$FILTERED_MOVIES" | awk -F'|' -v tracker="$TRACKER_ABBR" '
                    function format_size(bytes) {
                        if (bytes >= 1099511627776) return sprintf("%.2f TB", bytes/1099511627776)
                        if (bytes >= 1073741824) return sprintf("%.2f GB", bytes/1073741824)
                        if (bytes >= 1048576) return sprintf("%.2f MB", bytes/1048576)
                        if (bytes >= 1024) return sprintf("%.2f KB", bytes/1024)
                        return sprintf("%d B", bytes)
                    }

                    function format_slot(slot, is_ambiguous) {
                        # Parse slot: resolution:source:codec:hdr (using : separator)
                        split(slot, parts, ":")
                        res = parts[1]
                        source = parts[2]
                        codec = parts[3]
                        hdr = parts[4]

                        # Build readable slot description
                        slot_desc = res " " source " " codec
                        if (hdr != "unknown" && hdr != "") {
                            slot_desc = slot_desc " " hdr
                        }

                        # Add warning marker if ambiguous
                        if (is_ambiguous == "true") {
                            slot_desc = slot_desc " ⚠"
                        }

                        return slot_desc
                    }

                    BEGIN { num = 1 }
                    {
                        name = $1
                        size = $2

                        # Truncate long names
                        display_name = name
                        if (length(name) > 75) display_name = substr(name, 1, 72) "..."

                        # Format output based on tracker
                        if (tracker == "ATH") {
                            # ATH format includes slot info (5 fields total)
                            slot = $4
                            is_ambiguous = $5
                            slot_info = format_slot(slot, is_ambiguous)

                            printf "  %3d) %-77s %10s\n", num, display_name, format_size(size)
                            printf "       Slot: %s\n", slot_info
                        } else {
                            # Other trackers: original format (3 fields)
                            printf "  %3d) %-92s %10s\n", num, display_name, format_size(size)
                        }
                        num++
                    }
                    '
                    echo ""
                fi

                # Display TV Shows section (if tracker supports TV)
                if [ "$FILTERED_TV_COUNT" -gt 0 ]; then
                    echo -e "${CYAN}TV Shows (${FILTERED_TV_COUNT})${NC}"
                    echo ""

                    # Sort by size and display
                    sort -t'|' -k2 -rn "$FILTERED_TV" | awk -F'|' -v tracker="$TRACKER_ABBR" '
                    function format_size(bytes) {
                        if (bytes >= 1099511627776) return sprintf("%.2f TB", bytes/1099511627776)
                        if (bytes >= 1073741824) return sprintf("%.2f GB", bytes/1073741824)
                        if (bytes >= 1048576) return sprintf("%.2f MB", bytes/1048576)
                        if (bytes >= 1024) return sprintf("%.2f KB", bytes/1024)
                        return sprintf("%d B", bytes)
                    }

                    function format_slot(slot, is_ambiguous) {
                        # Parse slot: resolution:source:codec:hdr (using : separator)
                        split(slot, parts, ":")
                        res = parts[1]
                        source = parts[2]
                        codec = parts[3]
                        hdr = parts[4]

                        # Build readable slot description
                        slot_desc = res " " source " " codec
                        if (hdr != "unknown" && hdr != "") {
                            slot_desc = slot_desc " " hdr
                        }

                        # Add warning marker if ambiguous
                        if (is_ambiguous == "true") {
                            slot_desc = slot_desc " ⚠"
                        }

                        return slot_desc
                    }

                    BEGIN { num = 1 }
                    {
                        name = $1
                        size = $2

                        # Truncate long names
                        display_name = name
                        if (length(name) > 75) display_name = substr(name, 1, 72) "..."

                        # Format output based on tracker
                        if (tracker == "ATH") {
                            # ATH format includes slot info (5 fields total)
                            slot = $4
                            is_ambiguous = $5
                            slot_info = format_slot(slot, is_ambiguous)

                            printf "  %3d) %-77s %10s\n", num, display_name, format_size(size)
                            printf "       Slot: %s\n", slot_info
                        } else {
                            # Other trackers: original format (3 fields)
                            printf "  %3d) %-92s %10s\n", num, display_name, format_size(size)
                        }
                        num++
                    }
                    '
                    echo ""
                fi

                echo -e "${BLUE}Full lists saved to: ${FILTERED_MOVIES}"
                if [ "$FILTERED_TV_COUNT" -gt 0 ]; then
                    echo -e "                      ${FILTERED_TV}${NC}"
                else
                    echo -e "${NC}"
                fi
                echo ""
                echo -e "${GREEN}────────────────────────────────────────────────────────────────────────────────${NC}"
                echo ""
            fi
        done

        # Cleanup
        rm -f "$TEMP_ANALYSIS" "$TEMP_MOVIES" "$TEMP_TV" "$OUTPUT_DIR/multi_names_movies.tmp" "$OUTPUT_DIR/multi_names_tv.tmp"
else
    # Single tracker selected - display all results for that tracker
    TRACKER_NAME="${SELECTED_NAMES[0]}"
    OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_${TRACKER_NAME// /_}.txt"

    # Get tracker abbreviation
    TRACKER_ABBR=""
    case "$TRACKER_NAME" in
        "Aither (API)") TRACKER_ABBR="ATH" ;;
        "Anthelion (API)") TRACKER_ABBR="ANT" ;;
        "Blutopia (API)") TRACKER_ABBR="BLU" ;;
        "Nebulance") TRACKER_ABBR="NBL" ;;
    esac

    # Check if this tracker is movies-only
    TRACKER_MOVIES_ONLY=false
    if [[ "$TRACKER_NAME" == "Anthelion"* ]]; then
        TRACKER_MOVIES_ONLY=true
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║ ${YELLOW}${TRACKER_NAME}${GREEN} - All missing torrents${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Upload command: ${YELLOW}--trackers ${TRACKER_ABBR}${NC}"
    echo ""

    # Display movies
    if [ -f "${OUTPUT_FILE}.movies" ]; then
        MOVIE_COUNT=$(wc -l < "${OUTPUT_FILE}.movies" 2>/dev/null || echo 0)
        if [ $MOVIE_COUNT -gt 0 ]; then
            echo -e "${CYAN}Movies (${MOVIE_COUNT})${NC}"

            # For ATH, show slot system notice
            if [ "$TRACKER_ABBR" = "ATH" ]; then
                echo -e "${YELLOW}  ℹ ATH Slot System: Slots validated automatically${NC}"
                echo -e "${YELLOW}  ⚠ Slots with 'unknown' attributes need manual review${NC}"
            fi
            echo ""

            # Format and display (simpler version for single tracker - no slot validation needed here)
            awk -F'|' '
                function format_size(bytes) {
                    if (bytes >= 1099511627776)
                        return sprintf("%.2f TB", bytes / 1099511627776)
                    else if (bytes >= 1073741824)
                        return sprintf("%.2f GB", bytes / 1073741824)
                    else if (bytes >= 1048576)
                        return sprintf("%.2f MB", bytes / 1048576)
                    else if (bytes >= 1024)
                        return sprintf("%.2f KB", bytes / 1024)
                    else
                        return sprintf("%d B", bytes)
                }
                {
                    name = $1
                    size = $2

                    # Truncate long names
                    display_name = name
                    if (length(display_name) > 77) {
                        display_name = substr(display_name, 1, 74) "..."
                    }

                    printf "  %3d) %-77s %10s\n", NR, display_name, format_size(size)
                }
            ' "${OUTPUT_FILE}.movies"
            echo ""
            echo -e "${BLUE}Full list saved to: ${OUTPUT_DIR}/${TIMESTAMP}_${TRACKER_ABBR}_movies.txt${NC}"
            echo ""
        fi
    fi

    # Display TV shows (if tracker supports them)
    if [ "$TRACKER_MOVIES_ONLY" = false ] && [ -f "${OUTPUT_FILE}.tvshows" ]; then
        TV_COUNT=$(wc -l < "${OUTPUT_FILE}.tvshows" 2>/dev/null || echo 0)
        if [ $TV_COUNT -gt 0 ]; then
            echo -e "${CYAN}TV Shows (${TV_COUNT})${NC}"

            # For ATH, show slot system notice
            if [ "$TRACKER_ABBR" = "ATH" ]; then
                echo -e "${YELLOW}  ℹ ATH Slot System: Slots validated automatically${NC}"
                echo -e "${YELLOW}  ⚠ Slots with 'unknown' attributes need manual review${NC}"
            fi
            echo ""

            # Format and display
            awk -F'|' '
                function format_size(bytes) {
                    if (bytes >= 1099511627776)
                        return sprintf("%.2f TB", bytes / 1099511627776)
                    else if (bytes >= 1073741824)
                        return sprintf("%.2f GB", bytes / 1073741824)
                    else if (bytes >= 1048576)
                        return sprintf("%.2f MB", bytes / 1048576)
                    else if (bytes >= 1024)
                        return sprintf("%.2f KB", bytes / 1024)
                    else
                        return sprintf("%d B", bytes)
                }
                {
                    name = $1
                    size = $2

                    # Truncate long names
                    display_name = name
                    if (length(display_name) > 77) {
                        display_name = substr(display_name, 1, 74) "..."
                    }

                    printf "  %3d) %-77s %10s\n", NR, display_name, format_size(size)
                }
            ' "${OUTPUT_FILE}.tvshows"
            echo ""
            echo -e "${BLUE}Full list saved to: ${OUTPUT_DIR}/${TIMESTAMP}_${TRACKER_ABBR}_tv.txt${NC}"
            echo ""
        fi
    fi

    echo -e "${GREEN}────────────────────────────────────────────────────────────────────────────────${NC}"
    echo ""
fi

echo -e "${CYAN}Next steps:${NC}"
echo -e "  ${BLUE}1.${NC} Browse to Upload-Assistant: ${GREEN}http://10.10.2.2:8086${NC}"
echo -e "  ${BLUE}2.${NC} Navigate to ${GREEN}torrent_storage_dir → movies${NC}"
echo -e "  ${BLUE}3.${NC} Find one of the torrents from the lists above"
echo -e "  ${BLUE}4.${NC} Upload-Assistant will verify it doesn't exist"
echo -e "  ${BLUE}5.${NC} Upload with: ${YELLOW}python upload.py \"file.mkv\" --trackers ANT ATH${NC}"
echo -e "  ${BLUE}Note:${NC} Use tracker abbreviations: ${GREEN}ANT ATH BLU NBL${NC} (no brackets!)"
echo ""
echo -e "${CYAN}Results saved in: ${OUTPUT_DIR}/${NC}"
