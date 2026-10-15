import { randomUUID } from "node:crypto";
import type { Actor, ArchiveCause, SnapshotTabInput, TabEventInput } from "@tabtwin/shared";
import { ARCHIVE_CAUSES, domainFromUrl, isAgentHeldArchive } from "@tabtwin/shared";
import { z } from "zod";
import { defaultArchiveTabsIdempotencyKey } from "../crypto.ts";
import type { Db, Sql } from "../db.ts";
import { toJson } from "../db.ts";
import { writeAudit } from "./audit.ts";
import type { ArchiveTabsResult, DeviceRow, OperationReceiptRow, TabRow } from "../types.ts";

const AGENT_HELD_CAUSES = ARCHIVE_CAUSES.filter((cause) => isAgentHeldArchive(cause));

function ts(value: string | null | undefined): Date | null {
  if (!value) return null;
  return new Date(value);
}

async function upgradeArchiveCause(
  sql: Db,
  args: { deviceId: string; tab: TabRow; reason: ArchiveCause },
): Promise<TabRow> {
  if (isAgentHeldArchive(args.tab.archived_cause) || !isAgentHeldArchive(args.reason)) {
    return args.tab;
  }
  const [row] = await sql<TabRow[]>`
    UPDATE tabs SET
      archived_cause = ${args.reason},
      updated_at = now()
    WHERE id = ${args.tab.id} AND device_id = ${args.deviceId} AND state = 'archived'
    RETURNING *
  `;
  return row ?? args.tab;
}

async function getTab(sql: Db, deviceId: string, tabId: string): Promise<TabRow | undefined> {
  const [row] = await sql<TabRow[]>`
    SELECT * FROM tabs WHERE id = ${tabId} AND device_id = ${deviceId} LIMIT 1
  `;
  return row;
}

async function insertTab(
  sql: Db,
  device: DeviceRow,
  input: SnapshotTabInput,
): Promise<TabRow> {
  const id = randomUUID();
  const [row] = await sql<TabRow[]>`
    INSERT INTO tabs (
      id, device_id, url, title, domain, state,
      window_index, index_in_window, browser_family,
      pinned, active, audible, last_accessed_at, opened_at
    ) VALUES (
      ${id},
      ${device.id},
      ${input.url},
      ${input.title},
      ${domainFromUrl(input.url)},
      'open',
      ${input.windowIndex ?? null},
      ${input.indexInWindow ?? null},
      ${device.browser_family},
      ${input.pinned ?? false},
      ${input.active ?? false},
      ${input.audible ?? false},
      ${ts(input.lastAccessedAt)},
      ${ts(input.openedAt) ?? new Date()}
    )
    RETURNING *
  `;
  if (!row) {
    throw new Error("tab insert returned no row");
  }
  return row;
}

async function updateOpenTab(
  sql: Db,
  deviceId: string,
  tabId: string,
  input: SnapshotTabInput,
): Promise<TabRow | undefined> {
  const [row] = await sql<TabRow[]>`
    UPDATE tabs SET
      url = ${input.url},
      title = ${input.title},
      domain = ${domainFromUrl(input.url)},
      state = CASE
        WHEN state = 'archived' AND archived_cause IN ${sql(AGENT_HELD_CAUSES)} THEN state
        ELSE 'open'
      END,
      window_index = ${input.windowIndex ?? null},
      index_in_window = ${input.indexInWindow ?? null},
      pinned = ${input.pinned ?? false},
      active = ${input.active ?? false},
      audible = ${input.audible ?? false},
      last_accessed_at = ${ts(input.lastAccessedAt)},
      archived_at = CASE
        WHEN state = 'archived' AND archived_cause IN ${sql(AGENT_HELD_CAUSES)} THEN archived_at
        ELSE NULL
      END,
      archived_cause = CASE
        WHEN state = 'archived' AND archived_cause IN ${sql(AGENT_HELD_CAUSES)} THEN archived_cause
        ELSE NULL
      END,
      opened_at = COALESCE(${ts(input.openedAt)}, opened_at),
      updated_at = now()
    WHERE id = ${tabId} AND device_id = ${deviceId}
    RETURNING *
  `;
  return row;
}

export async function archiveTab(
  sql: Db,
  args: { deviceId: string; tabId: string; actor: Actor; reason: ArchiveCause; commandId?: string },
): Promise<TabRow | undefined> {
  const existing = await getTab(sql, args.deviceId, args.tabId);
  if (!existing) return undefined;
  if (existing.state === "archived") {
    return upgradeArchiveCause(sql, { deviceId: args.deviceId, tab: existing, reason: args.reason });
  }
  const [row] = await sql<TabRow[]>`
    UPDATE tabs SET
      state = 'archived',
      archived_at = now(),
      archived_cause = ${args.reason},
      updated_at = now()
    WHERE id = ${args.tabId} AND device_id = ${args.deviceId} AND state = 'open'
    RETURNING *
  `;
  if (!row) {
    const current = await getTab(sql, args.deviceId, args.tabId);
    if (!current) return undefined;
    if (current.state === "archived") {
      return upgradeArchiveCause(sql, { deviceId: args.deviceId, tab: current, reason: args.reason });
    }
    return current;
  }
  await writeAudit(sql, {
    deviceId: args.deviceId,
    tabId: row.id,
    commandId: args.commandId,
    actor: args.actor,
    action: "tab.archive",
    detail: { reason: args.reason, url: row.url, previousState: existing.state },
  });
  return row;
}

export async function snapshotTabs(
  sql: Sql,
  args: { device: DeviceRow; tabs: SnapshotTabInput[]; actor: Actor },
): Promise<{ mappings: Array<{ index: number; cloudId: string; created: boolean }>; archived: string[] }> {
  return sql.begin(async (tx) => {
    const mappings: Array<{ index: number; cloudId: string; created: boolean }> = [];
    const seen = new Set<string>();

    for (const [index, input] of args.tabs.entries()) {
      if (input.cloudId) {
        const updated = await updateOpenTab(tx, args.device.id, input.cloudId, input);
        if (updated) {
          seen.add(updated.id);
          mappings.push({ index, cloudId: updated.id, created: false });
          continue;
        }
      }
      const created = await insertTab(tx, args.device, input);
      seen.add(created.id);
      mappings.push({ index, cloudId: created.id, created: true });
      await writeAudit(tx, {
        deviceId: args.device.id,
        tabId: created.id,
        actor: args.actor,
        action: "tab.upsert",
        detail: { via: "snapshot", created: true, url: created.url },
      });
    }

    const openRows = await tx<TabRow[]>`
      SELECT * FROM tabs
      WHERE device_id = ${args.device.id} AND state = 'open'
    `;
    const archived: string[] = [];
    for (const row of openRows) {
      if (seen.has(row.id)) continue;
      const archivedRow = await archiveTab(tx, {
        deviceId: args.device.id,
        tabId: row.id,
        actor: args.actor,
        reason: "snapshot_reconcile",
      });
      if (archivedRow) archived.push(archivedRow.id);
    }

    await writeAudit(tx, {
      deviceId: args.device.id,
      actor: args.actor,
      action: "tab.reconcile",
      detail: {
        openCount: seen.size,
        minted: mappings.filter((item) => item.created).length,
        archivedCount: archived.length,
      },
    });

    return { mappings, archived };
  });
}

export async function applyTabEvent(
  sql: Db,
  args: { device: DeviceRow; event: TabEventInput; actor: Actor },
): Promise<{ cloudId?: string; tab?: TabRow; error?: string }> {
  switch (args.event.type) {
    case "created": {
      if (args.event.cloudId) {
        const updated = await updateOpenTab(sql, args.device.id, args.event.cloudId, {
          cloudId: args.event.cloudId,
          url: args.event.url ?? "",
          title: args.event.title ?? "",
          windowIndex: args.event.windowIndex,
          indexInWindow: args.event.indexInWindow,
          pinned: args.event.pinned,
          active: args.event.active,
          audible: args.event.audible,
          lastAccessedAt: args.event.lastAccessedAt,
        });
        if (updated) {
          await writeAudit(sql, {
            deviceId: args.device.id,
            tabId: updated.id,
            actor: args.actor,
            action: "tab.upsert",
            detail: { via: "created", url: updated.url },
          });
          return { cloudId: updated.id, tab: updated };
        }
      }
      const created = await insertTab(sql, args.device, {
        url: args.event.url ?? "",
        title: args.event.title ?? "",
        windowIndex: args.event.windowIndex,
        indexInWindow: args.event.indexInWindow,
        pinned: args.event.pinned,
        active: args.event.active,
        audible: args.event.audible,
        lastAccessedAt: args.event.lastAccessedAt,
      });
      await writeAudit(sql, {
        deviceId: args.device.id,
        tabId: created.id,
        actor: args.actor,
        action: "tab.upsert",
        detail: { via: "created", created: true, url: created.url },
      });
      return { cloudId: created.id, tab: created };
    }
    case "updated":
    case "moved": {
      if (!args.event.cloudId) {
        return { error: "cloudId_required" };
      }
      const existing = await getTab(sql, args.device.id, args.event.cloudId);
      if (!existing) return { error: "unknown_tab", cloudId: args.event.cloudId };
      const updated = await updateOpenTab(sql, args.device.id, args.event.cloudId, {
        cloudId: args.event.cloudId,
        url: args.event.url ?? existing.url,
        title: args.event.title ?? existing.title,
        windowIndex: args.event.windowIndex ?? existing.window_index,
        indexInWindow: args.event.indexInWindow ?? existing.index_in_window,
        pinned: args.event.pinned ?? existing.pinned,
        active: args.event.active ?? existing.active,
        audible: args.event.audible ?? existing.audible,
        lastAccessedAt: args.event.lastAccessedAt ?? existing.last_accessed_at?.toISOString(),
      });
      if (!updated) return { error: "unknown_tab", cloudId: args.event.cloudId };
      await writeAudit(sql, {
        deviceId: args.device.id,
        tabId: updated.id,
        actor: args.actor,
        action: "tab.upsert",
        detail: { via: args.event.type, url: updated.url },
      });
      return { cloudId: updated.id, tab: updated };
    }
    case "removed": {
      if (!args.event.cloudId) {
        return { error: "cloudId_required" };
      }
      const archived = await archiveTab(sql, {
        deviceId: args.device.id,
        tabId: args.event.cloudId,
        actor: args.actor,
        reason: "native_removed",
      });
      if (!archived) return { error: "unknown_tab", cloudId: args.event.cloudId };
      return { cloudId: archived.id, tab: archived };
    }
    default: {
      const _exhaustive: never = args.event.type;
      return { error: `unhandled_event:${_exhaustive}` };
    }
  }
}

export async function listTabs(
  sql: Db,
  args: { deviceId: string; state: "open" | "archived" | "all"; workspaceId?: string },
): Promise<TabRow[]> {
  const workspaceClause =
    args.workspaceId === undefined ? sql`` : sql`AND workspace_id = ${args.workspaceId}`;
  if (args.state === "all") {
    return sql<TabRow[]>`
      SELECT * FROM tabs
      WHERE device_id = ${args.deviceId}
      ${workspaceClause}
      ORDER BY state ASC, index_in_window ASC NULLS LAST, updated_at DESC
    `;
  }
  return sql<TabRow[]>`
    SELECT * FROM tabs
    WHERE device_id = ${args.deviceId} AND state = ${args.state}
    ${workspaceClause}
    ORDER BY window_index ASC NULLS LAST, index_in_window ASC NULLS LAST, updated_at DESC
  `;
}

export async function getDeviceTab(
  sql: Db,
  args: { deviceId: string; tabId: string },
): Promise<TabRow | undefined> {
  return getTab(sql, args.deviceId, args.tabId);
}

const archiveTabsClassificationSchema = z.object({
  newlyArchived: z.array(z.string()),
  alreadyArchived: z.array(z.string()),
  missing: z.array(z.string()),
});

function uniqueIds(ids: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of ids) {
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

function isUniqueViolation(error: unknown): boolean {
  return typeof error === "object" && error !== null && "code" in error && error.code === "23505";
}

async function tabsByIds(sql: Db, deviceId: string, ids: string[]): Promise<TabRow[]> {
  if (ids.length === 0) return [];
  const rows = await sql<TabRow[]>`
    SELECT * FROM tabs WHERE device_id = ${deviceId} AND id IN ${sql(ids)}
  `;
  const byId = new Map(rows.map((row) => [row.id, row]));
  return ids.flatMap((id) => {
    const row = byId.get(id);
    return row ? [row] : [];
  });
}

async function replayArchiveTabs(
  sql: Db,
  args: { deviceId: string; ids: string[]; receipt: OperationReceiptRow },
): Promise<ArchiveTabsResult> {
  const classification = archiveTabsClassificationSchema.parse(args.receipt.result);
  const tabs = await tabsByIds(sql, args.deviceId, args.ids);
  return { tabs, ...classification, created: false };
}

export async function archiveTabs(
  sql: Sql,
  args: {
    deviceId: string;
    tabIds: string[];
    idempotencyKey?: string;
    actor: Actor;
  },
): Promise<ArchiveTabsResult> {
  const ids = uniqueIds(args.tabIds);
  const idempotencyKey = args.idempotencyKey ?? defaultArchiveTabsIdempotencyKey(ids);

  try {
    return await sql.begin(async (tx) => {
      const [receipt] = await tx<OperationReceiptRow[]>`
        SELECT * FROM operation_receipts
        WHERE device_id = ${args.deviceId} AND idempotency_key = ${idempotencyKey}
        LIMIT 1
      `;
      if (receipt) {
        return replayArchiveTabs(tx, { deviceId: args.deviceId, ids, receipt });
      }

      const newlyArchived: string[] = [];
      const alreadyArchived: string[] = [];
      const missing: string[] = [];

      for (const tabId of ids) {
        const existing = await getTab(tx, args.deviceId, tabId);
        if (!existing) {
          missing.push(tabId);
          continue;
        }
        const wasArchived = existing.state === "archived";
        const archived = await archiveTab(tx, {
          deviceId: args.deviceId,
          tabId,
          actor: args.actor,
          reason: "archive_tabs",
        });
        if (!archived) {
          missing.push(tabId);
          continue;
        }
        if (wasArchived) alreadyArchived.push(tabId);
        else newlyArchived.push(tabId);
      }

      const classification = { newlyArchived, alreadyArchived, missing };
      await tx`
        INSERT INTO operation_receipts (device_id, idempotency_key, result)
        VALUES (
          ${args.deviceId},
          ${idempotencyKey},
          ${tx.json(toJson(classification))}
        )
      `;
      const tabs = await tabsByIds(tx, args.deviceId, ids);
      return { tabs, ...classification, created: true };
    });
  } catch (error) {
    if (!isUniqueViolation(error)) throw error;
    const [receipt] = await sql<OperationReceiptRow[]>`
      SELECT * FROM operation_receipts
      WHERE device_id = ${args.deviceId} AND idempotency_key = ${idempotencyKey}
      LIMIT 1
    `;
    if (!receipt) throw error;
    return replayArchiveTabs(sql, { deviceId: args.deviceId, ids, receipt });
  }
}
