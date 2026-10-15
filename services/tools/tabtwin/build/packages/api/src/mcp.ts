import { createMcpHandler, McpServer } from "@modelcontextprotocol/server";
import * as z from "zod/v4";
import type { Sql } from "./db.ts";
import { mcpActor } from "./auth.ts";
import { getDevice } from "./services/devices.ts";
import { archiveTabs, listTabs } from "./services/tabs.ts";
import { closeTabCommand } from "./services/commands.ts";
import { createWorkspace, listWorkspaces, setTabWorkspace } from "./services/workspaces.ts";
import { serializeArchiveTabs, serializeCommand, serializeTab, serializeWorkspace } from "./serialize.ts";
import type { DeviceRow } from "./types.ts";

const MCP_INSTRUCTIONS = [
  "Tabtwin holds cloud twins of browser tabs. Cloud UUIDs are the only tab IDs.",
  "Never use a chrome.tabs id (or any native tab id) as an argument.",
  "list_tabs is a read. Filter with state (open, archived, all; default open) and optional workspaceId.",
  "list_workspaces and create_workspace manage device-scoped named groups. Membership is set_tab_workspace.",
  "close_tab is confirm-tier. Calling it is the confirmation. Do not auto-close.",
  "close_tab archives the twin, then queues a device command. The browser closes later.",
  "archive_tabs is confirm-tier. Calling it is the confirmation. Do not auto-archive. Do not auto-close.",
  "archive_tabs archives twins in the cloud only. It does not enqueue a device command and does not close the browser tab.",
  "Statuses: queued, success, fail, unsupported, stale.",
  "Do not implement purchase, message, account, or auth actions. Those are explicit-tier.",
  "get_page_content is out of scope. No cookies, passwords, or page HTML.",
].join(" ");

function textResult(payload: unknown, isError = false) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
    structuredContent: payload,
    isError,
  };
}

async function deviceFromAuth(
  sql: Sql,
  authInfo: { clientId?: string } | undefined,
): Promise<DeviceRow | undefined> {
  const id = authInfo?.clientId;
  if (!id) return undefined;
  return getDevice(sql, id);
}

export function createTabtwinMcpHandler(sql: Sql) {
  return createMcpHandler(
    ({ authInfo }) => {
      const server = new McpServer(
        { name: "tabtwin", version: "0.1.0" },
        { instructions: MCP_INSTRUCTIONS },
      );

      server.registerTool(
        "list_tabs",
        {
          title: "List tab twins",
          description:
            "List cloud tab twins for the authenticated device. IDs are cloud UUIDs, never native browser tab IDs. Filter by state (open, archived, all; default open) and optional workspaceId. Read-only / auto-tier. Do not close or archive tabs from this list without an explicit close_tab or archive_tabs call.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: z.object({
            state: z
              .enum(["open", "archived", "all"])
              .optional()
              .describe("open, archived, or all. Default open."),
            workspaceId: z
              .string()
              .uuid()
              .optional()
              .describe("If set, only twins in this workspace."),
          }),
          outputSchema: z.object({
            tabs: z.array(z.record(z.string(), z.unknown())),
          }),
        },
        async ({ state, workspaceId }) => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const rows = await listTabs(sql, {
            deviceId: device.id,
            state: state ?? "open",
            workspaceId,
          });
          return textResult({ tabs: rows.map(serializeTab) });
        },
      );

      server.registerTool(
        "close_tab",
        {
          title: "Close a tab",
          description:
            "Confirm-tier close. The MCP call is the confirmation; do not auto-close. Archives the cloud twin first, then enqueues an idempotent close_tab command for the device. Pass a cloud tab UUID from list_tabs. Statuses: queued, success, fail, unsupported, stale. Stale means the twin is gone or the device no longer has a live native tab for that cloud ID.",
          annotations: {
            readOnlyHint: false,
            destructiveHint: true,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: z.object({
            tabId: z
              .string()
              .uuid()
              .describe("Cloud tab UUID from list_tabs. Not a chrome.tabs id."),
            idempotencyKey: z
              .string()
              .min(1)
              .max(200)
              .optional()
              .describe("Defaults to close_tab:<tabId>. Repeating the same key returns the original command."),
          }),
          outputSchema: z.object({
            command: z.record(z.string(), z.unknown()),
            created: z.boolean(),
          }),
        },
        async ({ tabId, idempotencyKey }) => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const { command, created } = await closeTabCommand(sql, {
            device,
            tabId,
            idempotencyKey,
            actor: mcpActor(device),
          });
          return textResult({ command: serializeCommand(command), created });
        },
      );

      server.registerTool(
        "list_workspaces",
        {
          title: "List workspaces",
          description:
            "List named workspaces for this device. Read-only / auto-tier. A tab belongs to zero or one workspace.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: z.object({}),
          outputSchema: z.object({
            workspaces: z.array(z.record(z.string(), z.unknown())),
          }),
        },
        async () => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const rows = await listWorkspaces(sql, { deviceId: device.id });
          return textResult({ workspaces: rows.map(serializeWorkspace) });
        },
      );

      server.registerTool(
        "create_workspace",
        {
          title: "Create a workspace",
          description:
            "Create a device-scoped workspace. Name is required, 1 to 120 characters after trim. Returns the new workspace UUID.",
          annotations: {
            readOnlyHint: false,
            destructiveHint: false,
            idempotentHint: false,
            openWorldHint: false,
          },
          inputSchema: z.object({
            name: z.string().trim().min(1).max(120).describe("Workspace name."),
          }),
          outputSchema: z.object({
            workspace: z.record(z.string(), z.unknown()),
          }),
        },
        async ({ name }) => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const row = await createWorkspace(sql, { deviceId: device.id, name });
          return textResult({ workspace: serializeWorkspace(row) });
        },
      );

      server.registerTool(
        "set_tab_workspace",
        {
          title: "Set tab workspace",
          description:
            "Assign a tab twin to a workspace, or pass workspaceId null to unassign. Tab and workspace must belong to this device.",
          annotations: {
            readOnlyHint: false,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: z.object({
            tabId: z.string().uuid().describe("Cloud tab UUID from list_tabs."),
            workspaceId: z
              .string()
              .uuid()
              .nullable()
              .describe("Workspace UUID, or null to unassign."),
          }),
          outputSchema: z.object({
            tab: z.record(z.string(), z.unknown()),
          }),
        },
        async ({ tabId, workspaceId }) => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const result = await setTabWorkspace(sql, {
            deviceId: device.id,
            tabId,
            workspaceId,
          });
          if (!result.ok) {
            return textResult({ error: "not_found", reason: result.reason }, true);
          }
          return textResult({ tab: serializeTab(result.tab) });
        },
      );

      server.registerTool(
        "archive_tabs",
        {
          title: "Archive tab twins",
          description:
            "Confirm-tier archive. The MCP call is the confirmation; do not auto-archive; do not auto-close. Archives cloud twins only. Does not enqueue a device command and does not close the browser tab. Unknown ids are listed in missing. Repeating the same idempotency key returns the original classification and current tab rows.",
          annotations: {
            readOnlyHint: false,
            destructiveHint: true,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: z.object({
            tabIds: z
              .array(z.string().uuid())
              .min(1)
              .max(200)
              .describe("Cloud tab UUIDs from list_tabs."),
            idempotencyKey: z
              .string()
              .min(1)
              .max(200)
              .optional()
              .describe("Defaults to archive_tabs:<sha256 of sorted unique ids>."),
          }),
          outputSchema: z.object({
            tabs: z.array(z.record(z.string(), z.unknown())),
            newlyArchived: z.array(z.string()),
            alreadyArchived: z.array(z.string()),
            missing: z.array(z.string()),
            created: z.boolean(),
          }),
        },
        async ({ tabIds, idempotencyKey }) => {
          const device = await deviceFromAuth(sql, authInfo);
          if (!device) {
            return textResult({ error: "unauthorized" }, true);
          }
          const result = await archiveTabs(sql, {
            deviceId: device.id,
            tabIds,
            idempotencyKey,
            actor: mcpActor(device),
          });
          return textResult(serializeArchiveTabs(result));
        },
      );

      return server;
    },
    { responseMode: "json" },
  );
}
