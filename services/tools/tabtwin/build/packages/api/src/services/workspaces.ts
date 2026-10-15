import { randomUUID } from "node:crypto";
import type { Db } from "../db.ts";
import { getDeviceTab } from "./tabs.ts";
import type { TabRow, WorkspaceRow } from "../types.ts";

export async function listWorkspaces(sql: Db, args: { deviceId: string }): Promise<WorkspaceRow[]> {
  return sql<WorkspaceRow[]>`
    SELECT * FROM workspaces
    WHERE device_id = ${args.deviceId}
    ORDER BY created_at DESC
  `;
}

export async function getWorkspace(
  sql: Db,
  args: { deviceId: string; workspaceId: string },
): Promise<WorkspaceRow | undefined> {
  const [row] = await sql<WorkspaceRow[]>`
    SELECT * FROM workspaces
    WHERE id = ${args.workspaceId} AND device_id = ${args.deviceId}
    LIMIT 1
  `;
  return row;
}

export async function createWorkspace(
  sql: Db,
  args: { deviceId: string; name: string },
): Promise<WorkspaceRow> {
  const id = randomUUID();
  const [row] = await sql<WorkspaceRow[]>`
    INSERT INTO workspaces (id, device_id, name)
    VALUES (${id}, ${args.deviceId}, ${args.name})
    RETURNING *
  `;
  if (!row) {
    throw new Error("workspace insert returned no row");
  }
  return row;
}

export type SetTabWorkspaceResult =
  | { ok: true; tab: TabRow }
  | { ok: false; reason: "unknown_tab" | "unknown_workspace" };

export async function setTabWorkspace(
  sql: Db,
  args: { deviceId: string; tabId: string; workspaceId: string | null },
): Promise<SetTabWorkspaceResult> {
  const tab = await getDeviceTab(sql, { deviceId: args.deviceId, tabId: args.tabId });
  if (!tab) return { ok: false, reason: "unknown_tab" };
  if (args.workspaceId !== null) {
    const workspace = await getWorkspace(sql, {
      deviceId: args.deviceId,
      workspaceId: args.workspaceId,
    });
    if (!workspace) return { ok: false, reason: "unknown_workspace" };
  }
  const [row] = await sql<TabRow[]>`
    UPDATE tabs SET
      workspace_id = ${args.workspaceId},
      updated_at = now()
    WHERE id = ${args.tabId} AND device_id = ${args.deviceId}
    RETURNING *
  `;
  if (!row) return { ok: false, reason: "unknown_tab" };
  return { ok: true, tab: row };
}
