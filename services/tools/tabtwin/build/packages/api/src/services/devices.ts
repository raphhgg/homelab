import { randomUUID } from "node:crypto";
import type { BrowserFamily, Platform } from "@tabtwin/shared";
import type { Db } from "../db.ts";
import { generateToken, hashToken } from "../crypto.ts";
import { writeAudit } from "./audit.ts";
import type { DeviceRow } from "../types.ts";

export async function registerDevice(
  sql: Db,
  args: { name: string; browserFamily: BrowserFamily; platform: Platform },
): Promise<{ device: DeviceRow; token: string }> {
  const id = randomUUID();
  const token = generateToken();
  const tokenHash = hashToken(token);
  const [device] = await sql<DeviceRow[]>`
    INSERT INTO devices (id, name, browser_family, platform, token_hash)
    VALUES (${id}, ${args.name}, ${args.browserFamily}, ${args.platform}, ${tokenHash})
    RETURNING *
  `;
  if (!device) {
    throw new Error("device insert returned no row");
  }
  await writeAudit(sql, {
    deviceId: device.id,
    actor: { type: "system", id: "register" },
    action: "device.register",
    detail: { browserFamily: args.browserFamily, platform: args.platform },
  });
  return { device, token };
}

export async function findDeviceByTokenHash(sql: Db, tokenHash: string): Promise<DeviceRow | undefined> {
  const [device] = await sql<DeviceRow[]>`
    SELECT * FROM devices WHERE token_hash = ${tokenHash} LIMIT 1
  `;
  return device;
}

export async function touchDevice(sql: Db, deviceId: string): Promise<void> {
  await sql`
    UPDATE devices
    SET last_seen_at = now(), updated_at = now()
    WHERE id = ${deviceId}
  `;
}

export async function ensureDevDevice(
  sql: Db,
  args: { token: string; name: string },
): Promise<DeviceRow> {
  const tokenHash = hashToken(args.token);
  const existing = await findDeviceByTokenHash(sql, tokenHash);
  if (existing) return existing;
  const id = randomUUID();
  const [device] = await sql<DeviceRow[]>`
    INSERT INTO devices (id, name, browser_family, platform, token_hash)
    VALUES (${id}, ${args.name}, 'chrome', 'macos', ${tokenHash})
    ON CONFLICT (token_hash) DO UPDATE SET name = EXCLUDED.name
    RETURNING *
  `;
  if (!device) {
    throw new Error("dev device insert returned no row");
  }
  await writeAudit(sql, {
    deviceId: device.id,
    actor: { type: "system", id: "boot" },
    action: "device.seed_dev",
    detail: { name: args.name },
  });
  return device;
}

export async function getDevice(sql: Db, deviceId: string): Promise<DeviceRow | undefined> {
  const [device] = await sql<DeviceRow[]>`
    SELECT * FROM devices WHERE id = ${deviceId} LIMIT 1
  `;
  return device;
}
