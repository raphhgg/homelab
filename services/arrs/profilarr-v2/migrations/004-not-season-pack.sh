#!/bin/sh
# Migration 004: Create "Not Season Pack" CF and ban it on all profiles (sonarr only)
# Purpose: Ban non-season-pack episodes from being downloaded
# Creates an inverted version of the existing "Season Pack" CF (negate=1)

DB="/volume2/docker/appdata/profilarr-v2/data/profilarr.db"

INNER_SQL=$(cat << 'EOSQL'
-- Create the "Not Season Pack" custom format
INSERT INTO custom_formats (name, description, include_in_rename) VALUES ('Not Season Pack', 'Matches releases that are NOT Season Packs on Sonarr. Used to ban individual episode downloads.', 0);

-- Create the condition (same as Season Pack but negated)
INSERT INTO custom_format_conditions (custom_format_name, name, type, arr_type, negate, required) VALUES ('Not Season Pack', 'Not Season Pack', 'release_type', 'all', 1, 1);

-- Create the release type condition detail
INSERT INTO condition_release_types (custom_format_name, condition_name, release_type) VALUES ('Not Season Pack', 'Not Season Pack', 'season_pack');

-- Ban on all 11 profiles (sonarr only, score -999999)
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Balanced', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Compact', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Efficient', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Efficient AV1', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Quality', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Quality HDR', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('1080p Remux', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('2160p Balanced', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('2160p Efficient', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('2160p Quality', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('2160p Remux', 'Not Season Pack', 'sonarr', -999999);
INSERT INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES ('720p Quality', 'Not Season Pack', 'sonarr', -999999);
EOSQL
)

ESCAPED_SQL=$(printf '%s' "$INNER_SQL" | sed "s/'/''/g")

sqlite3 "$DB" "INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  '$ESCAPED_SQL',
  '{\"new_custom_format\":\"Not Season Pack\",\"profiles_affected\":12,\"score\":-999999,\"arr_type\":\"sonarr\"}',
  '{\"operation\":\"create\",\"entity\":\"custom_format\",\"name\":\"Not Season Pack\",\"summary\":\"Create Not Season Pack CF and ban on all profiles (sonarr)\",\"title\":\"Create custom format \\\"Not Season Pack\\\" and ban on all profiles\",\"changed_fields\":[\"custom_format\",\"quality_profile_custom_formats\"],\"stable_key\":{\"key\":\"custom_format_name\",\"value\":\"Not Season Pack\"}}'
);"

echo "Migration 004 applied: Not Season Pack CF created and banned on all 12 profiles"
