#!/bin/sh
# Migration 003: Create 1080p Efficient AV1 profile
# Migrated from profilarr v1 custom profile "1080p Efficient AV1.yml"
# Based on 1080p Efficient with: AV1 unbanned (+375000), Vialle Bluray/WEB boosted,
# upgrade_until_score=600000, AV1 tag added

DB="/volume2/docker/appdata/profilarr-v2/data/profilarr.db"
INNER_SQL_FILE="$(dirname "$0")/003-1080p-efficient-av1-profile.sql"

# Read the inner SQL and escape single quotes for pcd_ops insertion
INNER_SQL=$(cat "$INNER_SQL_FILE")
ESCAPED_SQL=$(printf '%s' "$INNER_SQL" | sed "s/'/''/g")

# Insert as a single user op
sqlite3 "$DB" "INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  '$ESCAPED_SQL',
  '{\"new_profile\":\"1080p Efficient AV1\",\"based_on\":\"1080p Efficient\",\"changes\":[\"upgrade_until_score: 600000\",\"AV1: 375000\",\"Vialle Bluray boosted\",\"Vialle WEB boosted\",\"AV1 tag added\"]}',
  '{\"operation\":\"create\",\"entity\":\"quality_profile\",\"name\":\"1080p Efficient AV1\",\"summary\":\"Create 1080p Efficient AV1 profile based on 1080p Efficient\",\"title\":\"Create quality profile \\\"1080p Efficient AV1\\\"\",\"changed_fields\":[\"quality_profile\"],\"stable_key\":{\"key\":\"quality_profile_name\",\"value\":\"1080p Efficient AV1\"}}'
);"

echo "Migration 003 applied: 1080p Efficient AV1 profile created"
