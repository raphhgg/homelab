import { describe, expect, it } from "vitest";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi, testConfig } from "./helpers.ts";

describe("auth and audit", () => {
  it("registers with the bootstrap token and refuses a bad one", async () => {
    await withApi(async ({ app }) => {
      const bad = await json(app, "/v1/devices/register", {
        method: "POST",
        headers: {
          authorization: "Bearer nope",
          "content-type": "application/json",
        },
        body: JSON.stringify({ name: "Nope" }),
      });
      expect(bad.status).toBe(401);

      const good = await json(app, "/v1/devices/register", {
        method: "POST",
        headers: {
          authorization: `Bearer ${testConfig.bootstrapToken}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({ name: "Mac Chrome", browserFamily: "chrome", platform: "macos" }),
      });
      expect(good.status).toBe(201);
      const body = asRecord(good.body);
      expect(typeof body.token).toBe("string");
      expect(asRecord(body.device).browserFamily).toBe("chrome");

      const me = await json(app, "/v1/devices/me", {
        headers: authHeaders(String(body.token)),
      });
      expect(me.status).toBe(200);
    });
  });

  it("writes an audit chain for snapshot plus close", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      await json(app, "/v1/tabs/snapshot", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          tabs: [{ url: "https://aud.example/", title: "Aud", windowIndex: 0, indexInWindow: 0 }],
        }),
      });
      const listed = await json(app, "/v1/tabs", { headers: authHeaders(token) });
      const tabId = asRecord(asArray(asRecord(listed.body).tabs)[0]).id;
      await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ type: "close_tab", tabId }),
      });
      const audit = await json(app, "/v1/audit", { headers: authHeaders(token) });
      const events = asArray(asRecord(audit.body).events).map((event) => asRecord(event));
      expect(events.some((event) => event.action === "tab.reconcile")).toBe(true);
      expect(events.some((event) => event.action === "tab.archive")).toBe(true);
      expect(events.some((event) => event.action === "command.enqueue")).toBe(true);
      for (const event of events) {
        expect(event.actorType).toMatch(/device|mcp|system/);
      }
    });
  });
});
