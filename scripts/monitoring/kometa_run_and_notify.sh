#!/bin/bash
#
# Kometa Job Notification Script for Cronicle
# Runs Kometa jobs and sends Discord notification via Apprise
#
# Usage: kometa_run_and_notify.sh <job_type>
# Example: kometa_run_and_notify.sh metadata
#
# This script should be copied into the Cronicle job UI for testing.
# Source location: scripts/monitoring/kometa_run_and_notify.sh
#

set -euo pipefail

# Configuration
JOB_TYPE="${1:-collections}" # operations, metadata, collections, overlays
LOG_FILE="/tmp/kometa-${JOB_TYPE}-$(date +%Y%m%d-%H%M%S).log"
APPRISE_URL="http://10.10.2.2:8089/notify/kometa"

# Validate job type and map to Kometa flag
case "$JOB_TYPE" in
  metadata)
    FLAG="--metadata-only"
    JOB_NAME="Metadata Update"
    ;;
  overlays)
    FLAG="--overlays-only"
    JOB_NAME="Overlays Update"
    ;;
  collections)
    FLAG="--collections-only"
    JOB_NAME="Collections Update"
    ;;
  operations)
    FLAG="--operations-only"
    JOB_NAME="Operations"
    ;;
  playlists)
    FLAG="--playlists-only"
    JOB_NAME="Playlists Update"
    ;;
  *)
    echo "ERROR: Invalid job type: $JOB_TYPE"
    echo "Valid types: metadata, overlays, collections, operations, playlists"
    exit 1
    ;;
esac

echo "========================================"
echo "Kometa - $JOB_NAME"
echo "========================================"
echo "Started: $(date)"
echo "Log file: $LOG_FILE"
echo ""

# Run Kometa and capture output
START_TIME=$(date +%s)
set +e  # Don't exit on error, we want to capture the exit code
docker exec kometa python -u kometa.py --run $FLAG 2>&1 | tee "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e
END_TIME=$(date +%s)

# Calculate duration
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

echo ""
echo "========================================"
echo "Job completed"
echo "Duration: ${DURATION_MIN}m ${DURATION_SEC}s"
echo "Exit code: $EXIT_CODE"
echo "========================================"

# Verify log file exists
if [[ ! -f "$LOG_FILE" ]]; then
    echo "ERROR: Log file not found: $LOG_FILE"
    exit 1
fi

# Extract and format log summary for Discord
# Extract key information from Kometa's output (process file directly, don't load into memory)
# Temporarily disable pipefail for grep commands that might not match
set +o pipefail

echo "DEBUG: Extracting version..."
VERSION=$(grep -E 'Version:' "$LOG_FILE" | tail -1 | sed 's/.*Version:[[:space:]]*\([0-9.]*\).*/\1/' || echo "unknown")
echo "DEBUG: Version=$VERSION"

echo "DEBUG: Extracting times..."
START_TIME=$(grep -E 'Start Time:' "$LOG_FILE" | tail -1 | sed 's/.*Start Time:[[:space:]]*\([0-9:]*[[:space:]]*[0-9-]*\).*/\1/' || echo "unknown")
FINISH_TIME=$(grep -E 'Finished:' "$LOG_FILE" | tail -1 | sed 's/.*Finished:[[:space:]]*\([0-9:]*[[:space:]]*[0-9-]*\).*/\1/' || echo "unknown")
RUN_TIME=$(grep -E 'Run Time:' "$LOG_FILE" | tail -1 | sed 's/.*Run Time:[[:space:]]*\([0-9:]*\).*/\1/' || echo "unknown")
echo "DEBUG: Times extracted"

# Extract warning and error counts from the summary tables
echo "DEBUG: Extracting warning count..."
WARNING_COUNT=$(grep -A 999 "Warning Summary" "$LOG_FILE" | grep -E '^\|[[:space:]]+[0-9]+' | awk -F'|' '{sum += $2} END {print sum+0}')
echo "DEBUG: Warning count=$WARNING_COUNT"

echo "DEBUG: Extracting error count..."
ERROR_COUNT=$(grep -A 999 "Error Summary" "$LOG_FILE" | grep -E '^\|[[:space:]]+[0-9]+' | awk -F'|' '{sum += $2} END {print sum+0}')
echo "DEBUG: Error count=$ERROR_COUNT"

# Extract top 5 errors (if any) and wrap words with underscores in backticks
echo "DEBUG: Extracting top errors..."
TOP_ERRORS=$(grep -A 999 "Error Summary" "$LOG_FILE" | grep -E '^\|[[:space:]]+[0-9]+' | sed 's/^|//;s/|$//' | awk -F'|' '{
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1);
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2);
  # Wrap words containing underscores in backticks
  gsub(/[a-zA-Z_]+_[a-zA-Z_]+/, "`&`", $2);
  print $1 "x " $2
}' | head -5)
echo "DEBUG: Top errors extracted"

# Extract top 2 warnings (if any) and wrap words with underscores in backticks
echo "DEBUG: Extracting top warnings..."
TOP_WARNINGS=$(grep -A 999 "Warning Summary" "$LOG_FILE" | grep -E '^\|[[:space:]]+[0-9]+' | sed 's/^|//;s/|$//' | awk -F'|' '{
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1);
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2);
  # Wrap words containing underscores in backticks
  gsub(/[a-zA-Z_]+_[a-zA-Z_]+/, "`&`", $2);
  print $1 "x " $2
}' | head -2)
echo "DEBUG: Top warnings extracted"

# Extract library summaries (Movies, TV Shows, Sports)
echo "DEBUG: Extracting library summaries..."
MOVIES_TIME=$(grep -A 5 "Movies Summary" "$LOG_FILE" | grep "Library Loading and Mapping" | awk -F'|' '{print $3}' | tr -d ' ' || echo "N/A")
TVSHOWS_TIME=$(grep -A 5 "TV Shows Summary" "$LOG_FILE" | grep "Library Loading and Mapping" | awk -F'|' '{print $3}' | tr -d ' ' || echo "N/A")
SPORTS_TIME=$(grep -A 5 "Sports Summary" "$LOG_FILE" | grep "Library Loading and Mapping" | awk -F'|' '{print $3}' | tr -d ' ' || echo "N/A")
echo "DEBUG: Library summaries extracted"

# Re-enable pipefail
set -o pipefail

# Format the output cleanly
# LOG_TAIL="---"$'\n'
# LOG_TAIL+="Finished Run"$'\n'
LOG_TAIL+="Kometa Version:  $VERSION"$'\n'
# LOG_TAIL+="---"$'\n'
LOG_TAIL+="Start Time:      $START_TIME"$'\n'
LOG_TAIL+="Finished:        $FINISH_TIME"$'\n'
LOG_TAIL+="Run Time:        $RUN_TIME"$'\n'
LOG_TAIL+=""$'\n'
LOG_TAIL+="Library Processing Times:"$'\n'
LOG_TAIL+="• Movies:        $MOVIES_TIME"$'\n'
LOG_TAIL+="• TV Shows:      $TVSHOWS_TIME"$'\n'
LOG_TAIL+="• Sports:        $SPORTS_TIME"$'\n'

# Add top warnings if there are any
# if [ "$WARNING_COUNT" -gt 0 ] && [ -n "$TOP_WARNINGS" ]; then
#   LOG_TAIL+=$'\n\n'"Top Warnings:"$'\n'
#   while IFS= read -r warning_line; do
#     LOG_TAIL+="- $warning_line"$'\n'
#   done <<< "$TOP_WARNINGS"
# fi

# Add top errors if there are any
if [ "$ERROR_COUNT" -gt 0 ] && [ -n "$TOP_ERRORS" ]; then
  LOG_TAIL+=$'\n'"Top Errors:"$'\n'
  while IFS= read -r error_line; do
    LOG_TAIL+="- $error_line"$'\n'
  done <<< "$TOP_ERRORS"
fi

# Determine success/failure
if [ $EXIT_CODE -eq 0 ]; then
  STATUS_EMOJI="✅"
  STATUS_TEXT="Complete"
  APPRISE_TYPE="success"
else
  STATUS_EMOJI="❌"
  STATUS_TEXT="Failed"
  APPRISE_TYPE="failure"
fi

# Build notification
title="$STATUS_EMOJI Kometa - $JOB_NAME $STATUS_TEXT"

# Build body using same pattern as Watchtower
body=""
body+="**Duration:** ${DURATION_MIN}m ${DURATION_SEC}s"$'\n'
body+="**Exit Code:** $EXIT_CODE"$'\n'

# Add Cronicle job link if running in Cronicle
if [ -n "${JOB_ID:-}" ]; then
  body+=$'\n'
  body+="[View Full Logs in Cronicle](http://10.10.2.2:3012/#JobDetails?id=$JOB_ID)"
fi

body+=$'\n'
body+="### Summary"$'\n'
body+="$LOG_TAIL"$'\n'

echo ""
echo "Sending notification to Apprise..."
echo "Title length: ${#title}"
echo "Body length: ${#body}"

# Send using EXACT format from Watchtower
curl -X POST "$APPRISE_URL" \
  --data-urlencode "title=$title" \
  --data-urlencode "body=$body" \
  -d tag=kometa

echo "✓ Sent notification for $JOB_NAME"
echo ""
echo "Log file saved: $LOG_FILE"
