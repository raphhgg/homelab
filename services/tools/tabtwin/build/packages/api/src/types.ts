import type {
  ActorType,
  ArchiveCause,
  BrowserFamily,
  CommandStatus,
  CommandType,
  Platform,
  TabState,
} from "@tabtwin/shared";

export type DeviceRow = {
  id: string;
  name: string;
  browser_family: BrowserFamily;
  platform: Platform;
  token_hash: string;
  last_seen_at: Date | null;
  created_at: Date;
  updated_at: Date;
};

export type TabRow = {
  id: string;
  device_id: string;
  url: string;
  title: string;
  domain: string | null;
  state: TabState;
  window_index: number | null;
  index_in_window: number | null;
  browser_family: BrowserFamily;
  pinned: boolean;
  active: boolean;
  audible: boolean;
  last_accessed_at: Date | null;
  opened_at: Date;
  archived_at: Date | null;
  workspace_id: string | null;
  archived_cause: ArchiveCause | null;
  created_at: Date;
  updated_at: Date;
};

export type WorkspaceRow = {
  id: string;
  device_id: string;
  name: string;
  created_at: Date;
  updated_at: Date;
};

export type CommandRow = {
  id: string;
  device_id: string;
  tab_id: string | null;
  type: CommandType;
  status: CommandStatus;
  idempotency_key: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  created_at: Date;
  updated_at: Date;
};

export type AuditRow = {
  id: string;
  device_id: string | null;
  tab_id: string | null;
  command_id: string | null;
  actor_type: ActorType;
  actor_id: string | null;
  action: string;
  detail: Record<string, unknown>;
  created_at: Date;
};

export type Device = {
  id: string;
  name: string;
  browserFamily: BrowserFamily;
  platform: Platform;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Tab = {
  id: string;
  deviceId: string;
  url: string;
  title: string;
  domain: string | null;
  state: TabState;
  windowIndex: number | null;
  indexInWindow: number | null;
  browserFamily: BrowserFamily;
  pinned: boolean;
  active: boolean;
  audible: boolean;
  lastAccessedAt: string | null;
  openedAt: string;
  archivedAt: string | null;
  workspaceId: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Workspace = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
};

export type OperationReceiptRow = {
  device_id: string;
  idempotency_key: string;
  result: unknown;
  created_at: Date;
};

export type ArchiveTabsClassification = {
  newlyArchived: string[];
  alreadyArchived: string[];
  missing: string[];
};

export type ArchiveTabsResult = ArchiveTabsClassification & {
  tabs: TabRow[];
  created: boolean;
};

export type Command = {
  id: string;
  deviceId: string;
  tabId: string | null;
  type: CommandType;
  status: CommandStatus;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  safetyTier: "auto" | "confirm" | "explicit";
  createdAt: string;
  updatedAt: string;
};

export type AuditEvent = {
  id: string;
  deviceId: string | null;
  tabId: string | null;
  commandId: string | null;
  actorType: ActorType;
  actorId: string | null;
  action: string;
  detail: Record<string, unknown>;
  createdAt: string;
};
