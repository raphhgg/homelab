import { randomUUID } from "node:crypto";
import type { Actor } from "@tabtwin/shared";
import type { Db } from "../db.ts";
import { toJson } from "../db.ts";
import type { AuditRow } from "../types.ts";

export type AuditWrite = {
  deviceId?: string | null;
  tabId?: string | null;
  commandId?: string | null;
  actor: Actor;
  action: string;
  detail?: Record<string, unknown>;
};

export async function writeAudit(sql: Db, event: AuditWrite): Promise<AuditRow> {
  const id = randomUUID();
  const [row] = await sql<AuditRow[]>`
    INSERT INTO audit_events (
      id, device_id, tab_id, command_id, actor_type, actor_id, action, detail, created_at
    ) VALUES (
      ${id},
      ${event.deviceId ?? null},
      ${event.tabId ?? null},
      ${event.commandId ?? null},
      ${event.actor.type},
      ${event.actor.id},
      ${event.action},
      ${sql.json(toJson(event.detail ?? {}))},
      clock_timestamp()
    )
    RETURNING *
  `;
  if (!row) {
    throw new Error("audit insert returned no row");
  }
  return row;
}

export async function listAudit(sql: Db, args: { deviceId: string; limit: number }): Promise<AuditRow[]> {
  return sql<AuditRow[]>`
    SELECT * FROM audit_events
    WHERE device_id = ${args.deviceId}
    ORDER BY created_at DESC, id DESC
    LIMIT ${args.limit}
  `;
}
