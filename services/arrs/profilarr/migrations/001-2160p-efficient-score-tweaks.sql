-- Migration 001: 2160p Efficient streaming service score tweaks
-- Migrated from profilarr v1 commit 134a653: "Deprioritize MA and iT in 2160p Efficient"
-- Changes: MA 6000→1000, DSNP 3000→6000, iT 3000→1000, AMZN radarr 1000→3000, AMZN sonarr 2000→3000, NF 1000→1500

-- Op 1: MA radarr 6000 → 1000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 1000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''MA'' AND arr_type = ''radarr'' AND score = 6000;',
  '{"custom_format_scores":[{"custom_format_name":"MA","arr_type":"radarr","from":6000,"to":1000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Deprioritize MA on radarr","title":"Update radarr score for \"MA\" on \"2160p Efficient\"","changed_fields":["custom_format_score:MA:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"MA"}]}'
);

-- Op 2: DSNP radarr 3000 → 6000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 6000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''DSNP'' AND arr_type = ''radarr'' AND score = 3000;',
  '{"custom_format_scores":[{"custom_format_name":"DSNP","arr_type":"radarr","from":3000,"to":6000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Prioritize DSNP on radarr","title":"Update radarr score for \"DSNP\" on \"2160p Efficient\"","changed_fields":["custom_format_score:DSNP:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"DSNP"}]}'
);

-- Op 3: iT radarr 3000 → 1000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 1000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''iT'' AND arr_type = ''radarr'' AND score = 3000;',
  '{"custom_format_scores":[{"custom_format_name":"iT","arr_type":"radarr","from":3000,"to":1000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Deprioritize iT on radarr","title":"Update radarr score for \"iT\" on \"2160p Efficient\"","changed_fields":["custom_format_score:iT:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"iT"}]}'
);

-- Op 4: AMZN radarr 1000 → 3000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 3000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''AMZN'' AND arr_type = ''radarr'' AND score = 1000;',
  '{"custom_format_scores":[{"custom_format_name":"AMZN","arr_type":"radarr","from":1000,"to":3000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Bump AMZN on radarr","title":"Update radarr score for \"AMZN\" on \"2160p Efficient\"","changed_fields":["custom_format_score:AMZN:radarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"AMZN"}]}'
);

-- Op 5: AMZN sonarr 2000 → 3000
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 3000 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''AMZN'' AND arr_type = ''sonarr'' AND score = 2000;',
  '{"custom_format_scores":[{"custom_format_name":"AMZN","arr_type":"sonarr","from":2000,"to":3000}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Bump AMZN on sonarr","title":"Update sonarr score for \"AMZN\" on \"2160p Efficient\"","changed_fields":["custom_format_score:AMZN:sonarr"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"AMZN"}]}'
);

-- Op 6: NF all 1000 → 1500
INSERT INTO pcd_ops (database_id, origin, source, state, sql, desired_state, metadata)
VALUES (
  1, 'user', 'local', 'published',
  'UPDATE quality_profile_custom_formats SET score = 1500 WHERE quality_profile_name = ''2160p Efficient'' AND custom_format_name = ''NF'' AND arr_type = ''all'' AND score = 1000;',
  '{"custom_format_scores":[{"custom_format_name":"NF","arr_type":"all","from":1000,"to":1500}]}',
  '{"operation":"update","entity":"quality_profile","name":"2160p Efficient","summary":"Bump NF score","title":"Update score for \"NF\" on \"2160p Efficient\"","changed_fields":["custom_format_score:NF:all"],"stable_key":{"key":"quality_profile_name","value":"2160p Efficient"},"depends_on":[{"entity":"custom_format","key":"custom_format_name","value":"NF"}]}'
);
