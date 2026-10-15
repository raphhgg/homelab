import { COMMAND_SAFETY } from "@tabtwin/shared";
import type {
  ArchiveTabsResult,
  AuditEvent,
  AuditRow,
  Command,
  CommandRow,
  Device,
  DeviceRow,
  Tab,
  TabRow,
  Workspace,
  WorkspaceRow,
} from "./types.ts";

function iso(value: Date | null): string | null {
  return value ? value.toISOString() : null;
}

function isoRequired(value: Date): string {
  return value.toISOString();
}

export function serializeDevice(row: DeviceRow): Device {
  return {
    id: row.id,
    name: row.name,
    browserFamily: row.browser_family,
    platform: row.platform,
    lastSeenAt: iso(row.last_seen_at),
    createdAt: isoRequired(row.created_at),
    updatedAt: isoRequired(row.updated_at),
  };
}

export function serializeTab(row: TabRow): Tab {
  return {
    id: row.id,
    deviceId: row.device_id,
    url: row.url,
    title: row.title,
    domain: row.domain,
    state: row.state,
    windowIndex: row.window_index,
    indexInWindow: row.index_in_window,
    browserFamily: row.browser_family,
    pinned: row.pinned,
    active: row.active,
    audible: row.audible,
    lastAccessedAt: iso(row.last_accessed_at),
    openedAt: isoRequired(row.opened_at),
    archivedAt: iso(row.archived_at),
    workspaceId: row.workspace_id,
    createdAt: isoRequired(row.created_at),
    updatedAt: isoRequired(row.updated_at),
  };
}

export function serializeWorkspace(row: WorkspaceRow): Workspace {
  return {
    id: row.id,
    name: row.name,
    createdAt: isoRequired(row.created_at),
    updatedAt: isoRequired(row.updated_at),
  };
}

export function serializeArchiveTabs(result: ArchiveTabsResult) {
  return {
    tabs: result.tabs.map(serializeTab),
    newlyArchived: result.newlyArchived,
    alreadyArchived: result.alreadyArchived,
    missing: result.missing,
    created: result.created,
  };
}

export function serializeCommand(row: CommandRow): Command {
  return {
    id: row.id,
    deviceId: row.device_id,
    tabId: row.tab_id,
    type: row.type,
    status: row.status,
    idempotencyKey: row.idempotency_key,
    payload: row.payload,
    result: row.result,
    safetyTier: COMMAND_SAFETY[row.type],
    createdAt: isoRequired(row.created_at),
    updatedAt: isoRequired(row.updated_at),
  };
}

export function serializeAudit(row: AuditRow): AuditEvent {
  return {
    id: row.id,
    deviceId: row.device_id,
    tabId: row.tab_id,
    commandId: row.command_id,
    actorType: row.actor_type,
    actorId: row.actor_id,
    action: row.action,
    detail: row.detail,
    createdAt: isoRequired(row.created_at),
  };
}
