import { describe, expect, it } from "vitest";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi } from "./helpers.ts";
import { FakeExtension } from "./fake-extension.ts";

describe("close_tab command", () => {
  it("archives the twin before the device closes the native tab", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://close.example/",
        title: "Close me",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");

      const enqueued = await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ type: "close_tab", tabId: cloudId }),
      });
      expect(enqueued.status).toBe(201);
      const command = asRecord(enqueued.body);
      expect(command.status).toBe("queued");
      expect(command.safetyTier).toBe("confirm");
      expect(command.tabId).toBe(cloudId);

      const twin = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(twin.body).state).toBe("archived");
      const [cause] = await sql<{ archived_cause: string | null }[]>`
        SELECT archived_cause FROM tabs WHERE id = ${cloudId}
      `;
      expect(cause?.archived_cause).toBe("close_tab");
      expect(ext.tabs.size).toBe(1);

      const reports = await ext.pollAndExecute();
      expect(reports[0]?.status).toBe(200);
      expect(asRecord(reports[0]?.body).status).toBe("success");
      expect(ext.tabs.size).toBe(0);

      const done = await json(app, `/v1/commands/${command.id}`, { headers: authHeaders(token) });
      expect(asRecord(done.body).status).toBe("success");
    });
  });

  it("is idempotent for the same key", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://once.example/",
        title: "Once",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      const first = await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          type: "close_tab",
          tabId: cloudId,
          idempotencyKey: "close-once",
        }),
      });
      const second = await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          type: "close_tab",
          tabId: cloudId,
          idempotencyKey: "close-once",
        }),
      });
      expect(second.status).toBe(200);
      expect(asRecord(second.body).id).toBe(asRecord(first.body).id);
      const queued = await json(app, "/v1/commands?status=queued", { headers: authHeaders(token) });
      expect(asArray(asRecord(queued.body).commands)).toHaveLength(1);
    });
  });

  it("reports stale when the cloud ID no longer maps to a live native tab", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://gone.example/",
        title: "Gone",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");
      ext.tabs.clear();
      ext.nativeToCloud.clear();
      ext.cloudToNative.clear();
      await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ type: "close_tab", tabId: cloudId }),
      });
      const reports = await ext.pollAndExecute();
      expect(asRecord(reports[0]?.body).status).toBe("stale");
    });
  });

  it("returns stale immediately when the cloud ID is unknown", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const result = await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          type: "close_tab",
          tabId: "00000000-0000-4000-8000-000000000099",
        }),
      });
      expect(asRecord(result.body).status).toBe("stale");
      expect(asRecord(asRecord(result.body).result).reason).toBe("tab_not_found");
    });
  });

  it("accepts unsupported from a device that cannot close", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql, "Future iOS");
      const ext = new FakeExtension({ app, sql }, token);
      ext.closeBehavior = "unsupported";
      ext.openTab({
        url: "https://ios.example/",
        title: "iOS",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      await json(app, "/v1/commands", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ type: "close_tab", tabId: cloudId }),
      });
      const reports = await ext.pollAndExecute();
      expect(asRecord(reports[0]?.body).status).toBe("unsupported");
    });
  });
});
