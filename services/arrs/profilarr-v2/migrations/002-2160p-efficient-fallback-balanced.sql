-- Migration 002: 2160p Efficient fallback priority change
-- Migrated from profilarr v1 commit c83422c: "Change 2160p Efficient fallback to 1080p Balanced"
-- Goal: Fallback order 1080p Balanced > 1080p Quality HDR (HEVC) > 1080p Efficient
-- Current order: HEVC (860k/840k) > Efficient (824k-800k) > Balanced (781k-780k)
-- New order: Balanced (865k/864k/844k) > HEVC (860k/840k) > Efficient (824k-800k)

-- Op 1: 1080p Balanced Tier 1 radarr 781000 → 865000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 865000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p Balanced Tier 1'' AND arr_type = ''radarr'' AND score = 781000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p Balanced Tier 1","arr_type":"radarr","from":781000,"to":865000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p Balanced Tier 1 above HEVC (radarr)","title":"Update radarr score for \"1080p Balanced Tier 1\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p Balanced Tier 1:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 2: 1080p Balanced Tier 1 sonarr 781000 → 865000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 865000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p Balanced Tier 1'' AND arr_type = ''sonarr'' AND score = 781000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p Balanced Tier 1","arr_type":"sonarr","from":781000,"to":865000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p Balanced Tier 1 above HEVC (sonarr)","title":"Update sonarr score for \"1080p Balanced Tier 1\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p Balanced Tier 1:sonarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 3: 1080p Balanced Tier 2 radarr 780000 → 864000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 864000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p Balanced Tier 2'' AND arr_type = ''radarr'' AND score = 780000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p Balanced Tier 2","arr_type":"radarr","from":780000,"to":864000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p Balanced Tier 2 above HEVC (radarr)","title":"Update radarr score for \"1080p Balanced Tier 2\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p Balanced Tier 2:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 4: 1080p Balanced Tier 2 sonarr 780000 → 864000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 864000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p Balanced Tier 2'' AND arr_type = ''sonarr'' AND score = 780000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p Balanced Tier 2","arr_type":"sonarr","from":780000,"to":864000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p Balanced Tier 2 above HEVC (sonarr)","title":"Update sonarr score for \"1080p Balanced Tier 2\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p Balanced Tier 2:sonarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 5: 1080p WEB-DL (h264) radarr 780000 → 844000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 844000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p WEB-DL (h264)'' AND arr_type = ''radarr'' AND score = 780000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p WEB-DL (h264)","arr_type":"radarr","from":780000,"to":844000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p WEB-DL (h264) above HEVC WEB (radarr)","title":"Update radarr score for \"1080p WEB-DL (h264)\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p WEB-DL (h264):radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 6: 1080p WEB-DL (h264) sonarr 780000 → 844000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 844000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''1080p WEB-DL (h264)'' AND arr_type = ''sonarr'' AND score = 780000;',
  '{"custom_format_scores":[{"custom_format_name":"1080p WEB-DL (h264)","arr_type":"sonarr","from":780000,"to":844000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Raise 1080p WEB-DL (h264) above HEVC WEB (sonarr)","title":"Update sonarr score for \"1080p WEB-DL (h264)\" on \"2160p Efficient\"","changed_fields":["custom_format_score:1080p WEB-DL (h264):sonarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 7: Update description to mention 1080p Balanced fallback
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profiles SET description = ''2160p Efficient targets consistent & immutable 2160p **WEB-DLs w/ Lossy Audio**. Specialized Fallback to 1080p Balanced

- Average Movie Sizes ~ 15 to 30gb per Movie
- Movie Quality Ranking ~ 6/10
- Average TV Sizes ~ 4 to 12gb per Episode
- TV Ranking ~ 6/10'' WHERE name = ''2160p Efficient'' AND description LIKE ''%Fallback to 1080p Efficient%'';',
  '{"description":{"from":"2160p Efficient targets consistent & immutable 2160p **WEB-DLs w/ Lossy Audio**. Specialized Fallback to 1080p Efficient\n\n- Average Movie Sizes ~ 15 to 30gb per Movie\n- Movie Quality Ranking ~ 6/10\n- Average TV Sizes ~ 4 to 12gb per Episode\n- TV Ranking ~ 6/10","to":"2160p Efficient targets consistent & immutable 2160p **WEB-DLs w/ Lossy Audio**. Specialized Fallback to 1080p Balanced\n\n- Average Movie Sizes ~ 15 to 30gb per Movie\n- Movie Quality Ranking ~ 6/10\n- Average TV Sizes ~ 4 to 12gb per Episode\n- TV Ranking ~ 6/10"}}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Update description to reflect 1080p Balanced fallback","title":"Update description for quality profile \"2160p Efficient\"","changed_fields":["description"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 8: Add Banned Groups ban (all) -999999
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'INSERT OR REPLACE INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES (''2160p Efficient'', ''Banned Groups'', ''all'', -999999);',
  '{"custom_format_scores":[{"custom_format_name":"Banned Groups","arr_type":"all","from":null,"to":-999999}]}',
  '{"operation":"insert","entity":"quality_profile_custom_format","name":"2160p Efficient","summary":"Ban Banned Groups on 2160p Efficient","title":"Add \"Banned Groups\" ban to \"2160p Efficient\"","changed_fields":["custom_format_score:Banned Groups:all"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);

-- Op 9: Add Banned WEBRip ban (all) -999999
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'INSERT OR REPLACE INTO quality_profile_custom_formats (quality_profile_name, custom_format_name, arr_type, score) VALUES (''2160p Efficient'', ''Banned WEBRip'', ''all'', -999999);',
  '{"custom_format_scores":[{"custom_format_name":"Banned WEBRip","arr_type":"all","from":null,"to":-999999}]}',
  '{"operation":"insert","entity":"quality_profile_custom_format","name":"2160p Efficient","summary":"Ban Banned WEBRip on 2160p Efficient","title":"Add \"Banned WEBRip\" ban to \"2160p Efficient\"","changed_fields":["custom_format_score:Banned WEBRip:all"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"}}'
);
