import { describe, expect, it } from "vitest";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi } from "./helpers.ts";
import { FakeExtension } from "./fake-extension.ts";

async function mcpCall(
  app: Parameters<typeof json>[0],
  token: string,
  name: string,
  args: Record<string, unknown>,
) {
  const response = await app.request("/mcp", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name, arguments: args },
    }),
  });
  const text = await response.text();
  const dataLine = text.startsWith("event:")
    ? text
        .split("\n")
        .find((line) => line.startsWith("data: "))
        ?.slice(6)
    : text;
  if (!dataLine) {
    throw new Error(`MCP empty body status=${response.status} text=${text}`);
  }
  return { status: response.status, rpc: asRecord(JSON.parse(dataLine)) };
}

function toolPayload(rpc: Record<string, unknown>): Record<string, unknown> {
  const result = asRecord(rpc.result);
  const content = asArray(result.content);
  const first = asRecord(content[0]);
  if (typeof first.text !== "string") {
    throw new Error("missing tool text");
  }
  return asRecord(JSON.parse(first.text));
}

describe("MCP list_tabs and close_tab", () => {
  it("lists cloud IDs and closes through the fake extension", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://one.example/",
        title: "One",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      ext.openTab({
        url: "https://two.example/",
        title: "Two",
        windowIndex: 0,
        indexInWindow: 1,
        pinned: false,
        active: false,
      });
      await ext.snapshot();

      const listed = await mcpCall(app, token, "list_tabs", {});
      expect(listed.status).toBe(200);
      const payload = toolPayload(listed.rpc);
      const tabs = asArray(payload.tabs);
      expect(tabs).toHaveLength(2);
      const closeTarget = asRecord(tabs.find((tab) => asRecord(tab).title === "Two"));
      expect(closeTarget.id).toMatch(/^[0-9a-f-]{36}$/i);

      const closed = await mcpCall(app, token, "close_tab", { tabId: closeTarget.id });
      const closePayload = toolPayload(closed.rpc);
      expect(asRecord(closePayload.command).status).toBe("queued");
      expect(asRecord(closePayload.command).safetyTier).toBe("confirm");

      const twin = await json(app, `/v1/tabs/${closeTarget.id}`, { headers: authHeaders(token) });
      expect(asRecord(twin.body).state).toBe("archived");

      await ext.pollAndExecute();
      expect(ext.tabs.size).toBe(1);

      const audit = await json(app, "/v1/audit?limit=20", { headers: authHeaders(token) });
      const actions = asArray(asRecord(audit.body).events).map((event) => asRecord(event).action);
      expect(actions).toContain("tab.archive");
      expect(actions).toContain("command.enqueue");
      expect(actions).toContain("command.result");
      const enqueue = asArray(asRecord(audit.body).events).find(
        (event) => asRecord(event).action === "command.enqueue",
      );
      expect(asRecord(enqueue).actorType).toBe("mcp");
      const resultEvent = asArray(asRecord(audit.body).events).find(
        (event) => asRecord(event).action === "command.result",
      );
      expect(asRecord(resultEvent).actorType).toBe("device");
    });
  });

  it("rejects MCP without a device token", async () => {
    await withApi(async ({ app }) => {
      const response = await app.request("/mcp", {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "tools/call",
          params: { name: "list_tabs", arguments: {} },
        }),
      });
      expect(response.status).toBe(401);
    });
  });
});

describe("MCP workspaces and archive_tabs", () => {
  it("creates a workspace, assigns a tab, lists by workspace, and archives without a command", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://mcp-ws.example/",
        title: "McpWs",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const tabId = [...ext.nativeToCloud.values()][0];

      const created = await mcpCall(app, token, "create_workspace", { name: "Reading" });
      const workspace = asRecord(toolPayload(created.rpc).workspace);
      expect(workspace.name).toBe("Reading");

      const assigned = await mcpCall(app, token, "set_tab_workspace", {
        tabId,
        workspaceId: workspace.id,
      });
      expect(asRecord(toolPayload(assigned.rpc).tab).workspaceId).toBe(workspace.id);

      const listedWs = await mcpCall(app, token, "list_workspaces", {});
      expect(asArray(toolPayload(listedWs.rpc).workspaces)).toHaveLength(1);

      const listed = await mcpCall(app, token, "list_tabs", {
        state: "open",
        workspaceId: workspace.id,
      });
      expect(asArray(toolPayload(listed.rpc).tabs)).toHaveLength(1);

      const archived = await mcpCall(app, token, "archive_tabs", { tabIds: [tabId] });
      const archivePayload = toolPayload(archived.rpc);
      expect(archivePayload.created).toBe(true);
      expect(asArray(archivePayload.newlyArchived)).toEqual([tabId]);

      const archivedList = await mcpCall(app, token, "list_tabs", { state: "archived" });
      expect(asArray(toolPayload(archivedList.rpc).tabs)).toHaveLength(1);

      const queued = await json(app, "/v1/commands?status=queued", { headers: authHeaders(token) });
      expect(asArray(asRecord(queued.body).commands)).toHaveLength(0);
    });
  });
});
