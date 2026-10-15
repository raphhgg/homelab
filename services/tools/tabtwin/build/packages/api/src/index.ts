import { serve } from "@hono/node-server";
import { loadConfig } from "./config.ts";
import { createSql, migrate } from "./db.ts";
import { bootExtras, createApp } from "./app.ts";

const config = loadConfig();
const sql = createSql(config.databaseUrl);
await migrate(sql);
await bootExtras(sql, config);

const app = createApp(sql, config);

console.log(`Tabtwin API listening on http://${config.bind}:${config.port}`);
console.log(`MCP Streamable HTTP: POST /mcp`);
console.log(`OpenAPI: GET /openapi.yaml`);

const server = serve({
  fetch: app.fetch,
  port: config.port,
  hostname: config.bind,
});

const shutdown = async () => {
  server.close();
  await sql.end({ timeout: 2 });
  process.exit(0);
};

process.on("SIGTERM", () => {
  void shutdown();
});
process.on("SIGINT", () => {
  void shutdown();
});
