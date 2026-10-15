import type { Actor } from "@tabtwin/shared";
import type { Sql } from "./db.ts";
import { bearerFromHeader, hashToken, tokensEqual } from "./crypto.ts";
import { unauthorized } from "./errors.ts";
import { findDeviceByTokenHash, touchDevice } from "./services/devices.ts";
import type { DeviceRow } from "./types.ts";
import type { AppConfig } from "./config.ts";

export async function authenticateDevice(
  sql: Sql,
  header: string | undefined,
): Promise<DeviceRow> {
  const token = bearerFromHeader(header);
  if (!token) {
    throw unauthorized();
  }
  const device = await findDeviceByTokenHash(sql, hashToken(token));
  if (!device) {
    throw unauthorized("Unknown device token");
  }
  await touchDevice(sql, device.id);
  return device;
}

export function verifyBootstrap(config: AppConfig, c: {
  req: { header: (name: string) => string | undefined };
}): void {
  const headerToken = bearerFromHeader(c.req.header("authorization"));
  const alt = c.req.header("x-bootstrap-token")?.trim();
  const token = headerToken ?? alt;
  if (!token || !tokensEqual(token, config.bootstrapToken)) {
    throw unauthorized("Invalid bootstrap token");
  }
}

export function deviceActor(device: DeviceRow): Actor {
  return { type: "device", id: device.id };
}

export function mcpActor(device: DeviceRow): Actor {
  return { type: "mcp", id: device.id };
}

export function hostAllowed(hostHeader: string | undefined, allowedHosts: string[]): boolean {
  if (!hostHeader) return true;
  const hostname = hostHeader.split(":")[0]?.toLowerCase();
  if (!hostname) return true;
  return allowedHosts.some((allowed) => allowed.toLowerCase() === hostname);
}
