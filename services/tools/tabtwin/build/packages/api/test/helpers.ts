import { createApp } from "../src/app.ts";
import type { AppConfig } from "../src/config.ts";
import { createSql, migrate, type Sql } from "../src/db.ts";
import { registerDevice } from "../src/services/devices.ts";

const databaseUrl =
  process.env.TEST_DATABASE_URL ??
  process.env.DATABASE_URL ??
  "postgres://tabtwin:tabtwin@127.0.0.1:5432/tabtwin_test";

export const testConfig: AppConfig = {
  port: 47821,
  bind: "127.0.0.1",
  databaseUrl,
  bootstrapToken: "test-bootstrap",
  devDeviceToken: undefined,
  allowedHosts: ["127.0.0.1", "localhost"],
};

export async function withApi<T>(fn: (ctx: TestCtx) => Promise<T>): Promise<T> {
  const sql = createSql(databaseUrl);
  await migrate(sql);
  await sql`TRUNCATE audit_events, commands, operation_receipts, tabs, workspaces, devices CASCADE`;
  const app = createApp(sql, testConfig);
  const ctx: TestCtx = { sql, app };
  try {
    return await fn(ctx);
  } finally {
    await sql.end({ timeout: 1 });
  }
}

export type TestCtx = {
  sql: Sql;
  app: ReturnType<typeof createApp>;
};

export async function seedDevice(sql: Sql, name = "Test Chrome") {
  return registerDevice(sql, {
    name,
    browserFamily: "chrome",
    platform: "macos",
  });
}

export function authHeaders(token: string): Record<string, string> {
  return {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
    accept: "application/json, text/event-stream",
  };
}

export async function json(app: TestCtx["app"], path: string, init: RequestInit) {
  const response = await app.request(path, init);
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  return { status: response.status, body, text };
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new Error(`expected object, got ${typeof value}`);
  }
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    out[key] = item;
  }
  return out;
}

export function asArray(value: unknown): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error("expected array");
  }
  return value;
}
