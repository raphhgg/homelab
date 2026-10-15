const base = process.env.TABTWIN_URL ?? "http://127.0.0.1:47821";
const token = process.env.DEVICE_TOKEN ?? process.env.DEV_DEVICE_TOKEN;

if (!token) {
  console.error("Set DEVICE_TOKEN (or DEV_DEVICE_TOKEN) to the device bearer token.");
  process.exit(1);
}

const [tool, ...rest] = process.argv.slice(2);
if (!tool) {
  console.error("Usage: pnpm mcp list_tabs [--state open|archived|all] [--workspace <uuid>]");
  console.error("       pnpm mcp close_tab <cloud-tab-uuid> [idempotency-key]");
  console.error("       pnpm mcp list_workspaces");
  console.error("       pnpm mcp create_workspace <name>");
  console.error("       pnpm mcp set_tab_workspace <tab-uuid> <workspace-uuid|null>");
  console.error("       pnpm mcp archive_tabs <tab-uuid> [tab-uuid...] [--key <idempotency-key>]");
  process.exit(1);
}

function flagValue(argv: string[], name: string): string | undefined {
  const index = argv.indexOf(name);
  if (index === -1) return undefined;
  return argv[index + 1];
}

function argsForTool(): Record<string, unknown> {
  if (tool === "list_tabs") {
    const args: Record<string, unknown> = {};
    const state = flagValue(rest, "--state");
    const workspaceId = flagValue(rest, "--workspace");
    if (state) args.state = state;
    if (workspaceId) args.workspaceId = workspaceId;
    return args;
  }
  if (tool === "close_tab") {
    const tabId = rest[0];
    if (!tabId) {
      throw new Error("close_tab needs a cloud tab UUID");
    }
    const idempotencyKey = rest[1];
    return idempotencyKey ? { tabId, idempotencyKey } : { tabId };
  }
  if (tool === "list_workspaces") {
    return {};
  }
  if (tool === "create_workspace") {
    const name = rest.join(" ").trim();
    if (!name) {
      throw new Error("create_workspace needs a name");
    }
    return { name };
  }
  if (tool === "set_tab_workspace") {
    const tabId = rest[0];
    const workspaceRaw = rest[1];
    if (!tabId || workspaceRaw === undefined) {
      throw new Error("set_tab_workspace needs a tab UUID and a workspace UUID or null");
    }
    return { tabId, workspaceId: workspaceRaw === "null" ? null : workspaceRaw };
  }
  if (tool === "archive_tabs") {
    const key = flagValue(rest, "--key");
    const tabIds = rest.filter((item, index, all) => {
      if (item === "--key") return false;
      if (index > 0 && all[index - 1] === "--key") return false;
      return true;
    });
    if (tabIds.length === 0) {
      throw new Error("archive_tabs needs at least one cloud tab UUID");
    }
    return key ? { tabIds, idempotencyKey: key } : { tabIds };
  }
  throw new Error(`Unknown tool ${tool}`);
}

const rpc = {
  jsonrpc: "2.0",
  id: 1,
  method: "tools/call",
  params: { name: tool, arguments: argsForTool() },
};

const response = await fetch(`${base}/mcp`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
    accept: "application/json, text/event-stream",
  },
  body: JSON.stringify(rpc),
});

const raw = await response.text();
if (!response.ok) {
  console.error(response.status, raw);
  process.exit(1);
}

const jsonLine = raw.startsWith("event:")
  ? raw
      .split("\n")
      .find((line) => line.startsWith("data: "))
      ?.slice(6)
  : raw;

if (!jsonLine) {
  console.log(raw);
  process.exit(0);
}

const parsed: unknown = JSON.parse(jsonLine);
console.log(JSON.stringify(parsed, null, 2));
