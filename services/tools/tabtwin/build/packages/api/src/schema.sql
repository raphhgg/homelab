CREATE TABLE IF NOT EXISTS devices (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  browser_family TEXT NOT NULL,
  platform TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY,
  device_id UUID NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS workspaces_device_created_idx ON workspaces (device_id, created_at DESC);

CREATE TABLE IF NOT EXISTS tabs (
  id UUID PRIMARY KEY,
  device_id UUID NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  url TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  domain TEXT,
  state TEXT NOT NULL,
  window_index INTEGER,
  index_in_window INTEGER,
  browser_family TEXT NOT NULL,
  pinned BOOLEAN NOT NULL DEFAULT false,
  active BOOLEAN NOT NULL DEFAULT false,
  audible BOOLEAN NOT NULL DEFAULT false,
  last_accessed_at TIMESTAMPTZ,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ,
  workspace_id UUID REFERENCES workspaces (id) ON DELETE SET NULL,
  archived_cause TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT tabs_state_check CHECK (state IN ('open', 'archived')),
  CONSTRAINT tabs_archived_cause_check CHECK (
    archived_cause IS NULL OR archived_cause IN (
      'snapshot_reconcile',
      'native_removed',
      'close_tab',
      'archive_tabs'
    )
  )
);

CREATE INDEX IF NOT EXISTS tabs_device_state_idx ON tabs (device_id, state);
CREATE INDEX IF NOT EXISTS tabs_device_updated_idx ON tabs (device_id, updated_at DESC);

ALTER TABLE tabs ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE tabs ADD COLUMN IF NOT EXISTS archived_cause TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tabs_workspace_id_fkey'
  ) THEN
    ALTER TABLE tabs
      ADD CONSTRAINT tabs_workspace_id_fkey
      FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tabs_archived_cause_check'
  ) THEN
    ALTER TABLE tabs ADD CONSTRAINT tabs_archived_cause_check CHECK (
      archived_cause IS NULL OR archived_cause IN (
        'snapshot_reconcile',
        'native_removed',
        'close_tab',
        'archive_tabs'
      )
    );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS tabs_device_workspace_idx ON tabs (device_id, workspace_id);

CREATE TABLE IF NOT EXISTS commands (
  id UUID PRIMARY KEY,
  device_id UUID NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  tab_id UUID REFERENCES tabs (id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT commands_status_check CHECK (
    status IN ('queued', 'success', 'fail', 'unsupported', 'stale')
  ),
  CONSTRAINT commands_type_check CHECK (type IN ('close_tab')),
  CONSTRAINT commands_device_idempotency UNIQUE (device_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS commands_device_status_idx ON commands (device_id, status, created_at);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY,
  device_id UUID REFERENCES devices (id) ON DELETE SET NULL,
  tab_id UUID,
  command_id UUID,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  action TEXT NOT NULL,
  detail JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT audit_actor_type_check CHECK (actor_type IN ('device', 'mcp', 'system'))
);

CREATE INDEX IF NOT EXISTS audit_device_created_idx ON audit_events (device_id, created_at DESC);

CREATE TABLE IF NOT EXISTS operation_receipts (
  device_id UUID NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  idempotency_key TEXT NOT NULL,
  result jsonb NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (device_id, idempotency_key)
);
