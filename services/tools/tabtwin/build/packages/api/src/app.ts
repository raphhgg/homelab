import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Actor } from "@tabtwin/shared";
import {
  archiveTabsBodySchema,
  closeTabBodySchema,
  commandResultBodySchema,
  commandStatusSchema,
  createWorkspaceBodySchema,
  listTabsQuerySchema,
  registerDeviceBodySchema,
  setTabWorkspaceBodySchema,
  snapshotBodySchema,
  tabEventsBodySchema,
  uuidSchema,
} from "@tabtwin/shared";
import { z } from "zod";
import type { AppConfig } from "./config.ts";
import type { Sql } from "./db.ts";
import { ping } from "./db.ts";
import { ApiError } from "./errors.ts";
import {
  authenticateDevice,
  deviceActor,
  hostAllowed,
  mcpActor,
  verifyBootstrap,
} from "./auth.ts";
import { bearerFromHeader } from "./crypto.ts";
import { createTabtwinMcpHandler } from "./mcp.ts";
import { ensureDevDevice, getDevice, registerDevice } from "./services/devices.ts";
import { applyTabEvent, archiveTabs, getDeviceTab, listTabs, snapshotTabs } from "./services/tabs.ts";
import {
  enqueueCommand,
  getCommand,
  listCommands,
  reportCommandResult,
} from "./services/commands.ts";
import { listAudit } from "./services/audit.ts";
import { createWorkspace, listWorkspaces, setTabWorkspace } from "./services/workspaces.ts";
import { serializeArchiveTabs, serializeAudit, serializeCommand, serializeDevice, serializeTab, serializeWorkspace } from "./serialize.ts";
import type { DeviceRow } from "./types.ts";

type Variables = {
  device: DeviceRow;
  actor: Actor;
};

function httpStatus(n: number): 400 | 401 | 403 | 404 | 409 | 500 {
  if (n === 400 || n === 401 || n === 403 || n === 404 || n === 409) return n;
  return 500;
}

const openapiPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../contracts/openapi.yaml",
);

const enqueueBodySchema = z.object({
  type: z.literal("close_tab"),
  tabId: uuidSchema,
  idempotencyKey: z.string().min(1).max(200).optional(),
});

export function createApp(sql: Sql, config: AppConfig) {
  const app = new Hono<{ Variables: Variables }>();
  const mcpHandler = createTabtwinMcpHandler(sql);

  app.use("*", cors());

  app.use("*", async (c, next) => {
    if (!hostAllowed(c.req.header("host"), config.allowedHosts)) {
      return c.json({ error: { code: "forbidden_host", message: "Host header is not allowed" } }, 403);
    }
    await next();
  });

  app.onError((err, c) => {
    if (err instanceof ApiError) {
      return c.json({ error: { code: err.code, message: err.message } }, httpStatus(err.status));
    }
    if (err instanceof z.ZodError) {
      return c.json(
        { error: { code: "bad_request", message: err.issues.map((issue) => issue.message).join("; ") } },
        400,
      );
    }
    console.error(err);
    return c.json({ error: { code: "internal", message: "Internal error" } }, 500);
  });

  app.get("/healthz", async (c) => {
    const ok = await ping(sql);
    return c.json({ ok, db: ok ? "up" : "down" }, ok ? 200 : 503);
  });

  app.get("/openapi.yaml", (c) => {
    const body = readFileSync(openapiPath, "utf8");
    return c.body(body, 200, { "content-type": "application/yaml; charset=utf-8" });
  });

  app.post("/v1/devices/register", async (c) => {
    verifyBootstrap(config, c);
    const body = registerDeviceBodySchema.parse(await c.req.json());
    const { device, token } = await registerDevice(sql, {
      name: body.name,
      browserFamily: body.browserFamily,
      platform: body.platform,
    });
    return c.json({ device: serializeDevice(device), token }, 201);
  });

  app.use("/v1/*", async (c, next) => {
    if (c.req.path === "/v1/devices/register") {
      await next();
      return;
    }
    const device = await authenticateDevice(sql, c.req.header("authorization"));
    c.set("device", device);
    c.set("actor", deviceActor(device));
    await next();
  });

  app.get("/v1/devices/me", async (c) => {
    const fresh = await getDevice(sql, c.get("device").id);
    if (!fresh) {
      throw new ApiError(401, "unauthorized", "Device is gone");
    }
    return c.json(serializeDevice(fresh));
  });

  app.get("/v1/tabs", async (c) => {
    const query = listTabsQuerySchema.parse({
      state: c.req.query("state") ?? "open",
      workspaceId: c.req.query("workspaceId"),
    });
    const rows = await listTabs(sql, {
      deviceId: c.get("device").id,
      state: query.state,
      workspaceId: query.workspaceId,
    });
    return c.json({ tabs: rows.map(serializeTab) });
  });

  app.get("/v1/tabs/:tabId", async (c) => {
    const tabId = uuidSchema.parse(c.req.param("tabId"));
    const row = await getDeviceTab(sql, { deviceId: c.get("device").id, tabId });
    if (!row) {
      return c.json({ error: { code: "not_found", message: "Unknown tab" } }, 404);
    }
    return c.json(serializeTab(row));
  });

  app.get("/v1/workspaces", async (c) => {
    const rows = await listWorkspaces(sql, { deviceId: c.get("device").id });
    return c.json({ workspaces: rows.map(serializeWorkspace) });
  });

  app.post("/v1/workspaces", async (c) => {
    const body = createWorkspaceBodySchema.parse(await c.req.json());
    const row = await createWorkspace(sql, { deviceId: c.get("device").id, name: body.name });
    return c.json(serializeWorkspace(row), 201);
  });

  app.post("/v1/tabs/workspace", async (c) => {
    const body = setTabWorkspaceBodySchema.parse(await c.req.json());
    const result = await setTabWorkspace(sql, {
      deviceId: c.get("device").id,
      tabId: body.tabId,
      workspaceId: body.workspaceId,
    });
    if (!result.ok) {
      const message = result.reason === "unknown_workspace" ? "Unknown workspace" : "Unknown tab";
      return c.json({ error: { code: "not_found", message } }, 404);
    }
    return c.json(serializeTab(result.tab));
  });

  app.post("/v1/tabs/archive", async (c) => {
    const body = archiveTabsBodySchema.parse(await c.req.json());
    const result = await archiveTabs(sql, {
      deviceId: c.get("device").id,
      tabIds: body.tabIds,
      idempotencyKey: body.idempotencyKey,
      actor: c.get("actor"),
    });
    return c.json(serializeArchiveTabs(result), result.created ? 201 : 200);
  });

  app.post("/v1/tabs/snapshot", async (c) => {
    const body = snapshotBodySchema.parse(await c.req.json());
    const result = await snapshotTabs(sql, {
      device: c.get("device"),
      tabs: body.tabs,
      actor: c.get("actor"),
    });
    return c.json(result);
  });

  app.post("/v1/tabs/events", async (c) => {
    const body = tabEventsBodySchema.parse(await c.req.json());
    const results = [];
    for (const [index, event] of body.events.entries()) {
      const applied = await applyTabEvent(sql, {
        device: c.get("device"),
        event,
        actor: c.get("actor"),
      });
      results.push({
        index,
        type: event.type,
        cloudId: applied.cloudId,
        tab: applied.tab ? serializeTab(applied.tab) : undefined,
        error: applied.error,
      });
    }
    return c.json({ results });
  });

  app.get("/v1/commands", async (c) => {
    const status = commandStatusSchema.parse(c.req.query("status") ?? "queued");
    const rows = await listCommands(sql, { deviceId: c.get("device").id, status });
    return c.json({ commands: rows.map(serializeCommand) });
  });

  app.post("/v1/commands", async (c) => {
    const body = enqueueBodySchema.parse(await c.req.json());
    const { command, created } = await enqueueCommand(sql, {
      device: c.get("device"),
      type: body.type,
      tabId: body.tabId,
      idempotencyKey: body.idempotencyKey,
      actor: c.get("actor"),
    });
    return c.json(serializeCommand(command), created ? 201 : 200);
  });

  app.get("/v1/commands/:commandId", async (c) => {
    const commandId = uuidSchema.parse(c.req.param("commandId"));
    const row = await getCommand(sql, { deviceId: c.get("device").id, commandId });
    if (!row) {
      return c.json({ error: { code: "not_found", message: "Unknown command" } }, 404);
    }
    return c.json(serializeCommand(row));
  });

  app.post("/v1/commands/:commandId/result", async (c) => {
    const commandId = uuidSchema.parse(c.req.param("commandId"));
    const body = commandResultBodySchema.parse(await c.req.json());
    const row = await reportCommandResult(sql, {
      device: c.get("device"),
      commandId,
      status: body.status,
      detail: body.detail,
      actor: c.get("actor"),
    });
    if (!row) {
      return c.json({ error: { code: "not_found", message: "Unknown command" } }, 404);
    }
    return c.json(serializeCommand(row));
  });

  app.get("/v1/audit", async (c) => {
    const limit = z.coerce.number().int().min(1).max(200).default(50).parse(c.req.query("limit") ?? "50");
    const rows = await listAudit(sql, { deviceId: c.get("device").id, limit });
    return c.json({ events: rows.map(serializeAudit) });
  });

  app.post("/v1/mcp/close_tab", async (c) => {
    const body = closeTabBodySchema.parse(await c.req.json());
    const { command, created } = await enqueueCommand(sql, {
      device: c.get("device"),
      type: "close_tab",
      tabId: body.tabId,
      idempotencyKey: body.idempotencyKey,
      actor: mcpActor(c.get("device")),
    });
    return c.json({ command: serializeCommand(command), created }, created ? 201 : 200);
  });

  app.post("/v1/mcp/archive_tabs", async (c) => {
    const body = archiveTabsBodySchema.parse(await c.req.json());
    const result = await archiveTabs(sql, {
      deviceId: c.get("device").id,
      tabIds: body.tabIds,
      idempotencyKey: body.idempotencyKey,
      actor: mcpActor(c.get("device")),
    });
    return c.json(serializeArchiveTabs(result), result.created ? 201 : 200);
  });

  app.all("/mcp", async (c) => {
    const device = await authenticateDevice(sql, c.req.header("authorization"));
    let parsedBody: unknown;
    const contentType = c.req.header("content-type") ?? "";
    if (c.req.method === "POST" && contentType.includes("application/json")) {
      parsedBody = await c.req.json();
    }
    const authInfo = {
      token: bearerFromHeader(c.req.header("authorization")) ?? "",
      clientId: device.id,
      scopes: ["tabtwin"],
    };
    return mcpHandler.fetch(c.req.raw, { authInfo, parsedBody });
  });

  return app;
}

export async function bootExtras(sql: Sql, config: AppConfig): Promise<void> {
  if (config.devDeviceToken) {
    await ensureDevDevice(sql, {
      token: config.devDeviceToken,
      name: "Local Chrome (dev token)",
    });
  }
}
