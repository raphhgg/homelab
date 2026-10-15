import { randomUUID } from "node:crypto";
import {
  defaultCloseIdempotencyKey,
  type Actor,
  type CommandStatus,
  type CommandType,
} from "@tabtwin/shared";
import type { Db, Sql } from "../db.ts";
import { toJson } from "../db.ts";
import { writeAudit } from "./audit.ts";
import { archiveTab, getDeviceTab } from "./tabs.ts";
import type { CommandRow, DeviceRow } from "../types.ts";

const TERMINAL: ReadonlySet<CommandStatus> = new Set(["success", "fail", "unsupported", "stale"]);

export async function getCommand(
  sql: Db,
  args: { deviceId: string; commandId: string },
): Promise<CommandRow | undefined> {
  const [row] = await sql<CommandRow[]>`
    SELECT * FROM commands
    WHERE id = ${args.commandId} AND device_id = ${args.deviceId}
    LIMIT 1
  `;
  return row;
}

export async function listCommands(
  sql: Db,
  args: { deviceId: string; status: CommandStatus },
): Promise<CommandRow[]> {
  return sql<CommandRow[]>`
    SELECT * FROM commands
    WHERE device_id = ${args.deviceId} AND status = ${args.status}
    ORDER BY created_at ASC
  `;
}

export async function closeTabCommand(
  sql: Sql,
  args: {
    device: DeviceRow;
    tabId: string;
    idempotencyKey?: string;
    actor: Actor;
  },
): Promise<{ command: CommandRow; created: boolean }> {
  const idempotencyKey = args.idempotencyKey ?? defaultCloseIdempotencyKey(args.tabId);

  return sql.begin(async (tx) => {
    const existing = await tx<CommandRow[]>`
      SELECT * FROM commands
      WHERE device_id = ${args.device.id} AND idempotency_key = ${idempotencyKey}
      LIMIT 1
    `;
    const prior = existing[0];
    if (prior) {
      return { command: prior, created: false };
    }

    const tab = await getDeviceTab(tx, { deviceId: args.device.id, tabId: args.tabId });
    const commandId = randomUUID();

    if (!tab) {
      const [stale] = await tx<CommandRow[]>`
        INSERT INTO commands (
          id, device_id, tab_id, type, status, idempotency_key, payload, result
        ) VALUES (
          ${commandId},
          ${args.device.id},
          ${null},
          'close_tab',
          'stale',
          ${idempotencyKey},
          ${tx.json({ tabId: args.tabId })},
          ${tx.json({ reason: "tab_not_found" })}
        )
        RETURNING *
      `;
      if (!stale) throw new Error("command insert returned no row");
      await writeAudit(tx, {
        deviceId: args.device.id,
        tabId: args.tabId,
        commandId: stale.id,
        actor: args.actor,
        action: "command.enqueue",
        detail: { type: "close_tab", status: "stale", reason: "tab_not_found" },
      });
      await writeAudit(tx, {
        deviceId: args.device.id,
        tabId: args.tabId,
        commandId: stale.id,
        actor: args.actor,
        action: "command.result",
        detail: { status: "stale", reason: "tab_not_found" },
      });
      return { command: stale, created: true };
    }

    await archiveTab(tx, {
      deviceId: args.device.id,
      tabId: tab.id,
      actor: args.actor,
      reason: "close_tab",
      commandId,
    });

    const [queued] = await tx<CommandRow[]>`
      INSERT INTO commands (
        id, device_id, tab_id, type, status, idempotency_key, payload
      ) VALUES (
        ${commandId},
        ${args.device.id},
        ${tab.id},
        'close_tab',
        'queued',
        ${idempotencyKey},
        ${tx.json({ tabId: tab.id })}
      )
      RETURNING *
    `;
    if (!queued) throw new Error("command insert returned no row");
    await writeAudit(tx, {
      deviceId: args.device.id,
      tabId: tab.id,
      commandId: queued.id,
      actor: args.actor,
      action: "command.enqueue",
      detail: { type: "close_tab", status: "queued", safetyTier: "confirm" },
    });
    return { command: queued, created: true };
  });
}

export async function reportCommandResult(
  sql: Db,
  args: {
    device: DeviceRow;
    commandId: string;
    status: Exclude<CommandStatus, "queued">;
    detail: Record<string, unknown> | undefined;
    actor: Actor;
  },
): Promise<CommandRow | undefined> {
  const current = await getCommand(sql, { deviceId: args.device.id, commandId: args.commandId });
  if (!current) return undefined;
  if (TERMINAL.has(current.status)) {
    return current;
  }

  const [updated] = await sql<CommandRow[]>`
    UPDATE commands SET
      status = ${args.status},
      result = ${sql.json(toJson(args.detail ?? {}))},
      updated_at = now()
    WHERE id = ${args.commandId} AND device_id = ${args.device.id} AND status = 'queued'
    RETURNING *
  `;
  const row = updated ?? (await getCommand(sql, { deviceId: args.device.id, commandId: args.commandId }));
  if (!row) return undefined;
  await writeAudit(sql, {
    deviceId: args.device.id,
    tabId: row.tab_id,
    commandId: row.id,
    actor: args.actor,
    action: "command.result",
    detail: { status: row.status, type: row.type, result: toJson(row.result) },
  });
  return row;
}

export async function enqueueCommand(
  sql: Sql,
  args: {
    device: DeviceRow;
    type: CommandType;
    tabId: string;
    idempotencyKey?: string;
    actor: Actor;
  },
): Promise<{ command: CommandRow; created: boolean }> {
  switch (args.type) {
    case "close_tab":
      return closeTabCommand(sql, args);
    default: {
      const _exhaustive: never = args.type;
      throw new Error(`unhandled command type ${_exhaustive}`);
    }
  }
}
