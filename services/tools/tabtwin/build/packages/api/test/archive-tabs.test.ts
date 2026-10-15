import { describe, expect, it } from "vitest";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi } from "./helpers.ts";
import { FakeExtension } from "./fake-extension.ts";

describe("archive_tabs", () => {
  it("archives without queuing a device command and is idempotent for the same key", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://keep-open.example/",
        title: "Keep",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      ext.openTab({
        url: "https://park.example/",
        title: "Park",
        windowIndex: 0,
        indexInWindow: 1,
        pinned: false,
        active: false,
      });
      await ext.snapshot();
      const all = asArray(
        asRecord((await json(app, "/v1/tabs?state=all", { headers: authHeaders(token) })).body).tabs,
      ).map(asRecord);
      const park = all.find((tab) => tab.title === "Park");
      if (!park || typeof park.id !== "string") throw new Error("missing park tab");

      const first = await json(app, "/v1/tabs/archive", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [park.id], idempotencyKey: "archive-park" }),
      });
      expect(first.status).toBe(201);
      const firstBody = asRecord(first.body);
      expect(firstBody.created).toBe(true);
      expect(asArray(firstBody.newlyArchived)).toEqual([park.id]);
      expect(asArray(firstBody.alreadyArchived)).toEqual([]);
      expect(asArray(firstBody.missing)).toEqual([]);
      expect(asRecord(asArray(firstBody.tabs)[0]).state).toBe("archived");
      expect(asRecord(asArray(firstBody.tabs)[0]).archivedCause).toBeUndefined();

      const second = await json(app, "/v1/tabs/archive", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [park.id], idempotencyKey: "archive-park" }),
      });
      expect(second.status).toBe(200);
      expect(asRecord(second.body).created).toBe(false);
      expect(asArray(asRecord(second.body).newlyArchived)).toEqual([park.id]);
      expect(asRecord(asArray(asRecord(second.body).tabs)[0]).state).toBe("archived");

      const queued = await json(app, "/v1/commands?status=queued", { headers: authHeaders(token) });
      expect(asArray(asRecord(queued.body).commands)).toHaveLength(0);
      expect(ext.tabs.size).toBe(2);

      const [cause] = await sql<{ archived_cause: string | null }[]>`
        SELECT archived_cause FROM tabs WHERE id = ${park.id}
      `;
      expect(cause?.archived_cause).toBe("archive_tabs");
    });
  });

  it("lists unknown ids in missing and does not fail the batch", async () => {
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
      await ext.snapshot();
      const tabId = [...ext.nativeToCloud.values()][0];
      const ghost = "00000000-0000-4000-8000-000000000099";
      const result = await json(app, "/v1/tabs/archive", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [tabId, ghost] }),
      });
      expect(result.status).toBe(201);
      const body = asRecord(result.body);
      expect(asArray(body.newlyArchived)).toEqual([tabId]);
      expect(asArray(body.missing)).toEqual([ghost]);
      expect(asArray(body.tabs)).toHaveLength(1);
    });
  });

  it("stays archived when a later snapshot still includes that cloudId", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://held-live.example/",
        title: "Held live",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      await json(app, "/v1/tabs/archive", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [cloudId] }),
      });
      await ext.snapshot();
      const listed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(listed.body).state).toBe("archived");
      const queued = await json(app, "/v1/commands?status=queued", { headers: authHeaders(token) });
      expect(asArray(asRecord(queued.body).commands)).toHaveLength(0);
    });
  });

  it("uses the MCP alias with the mcp actor", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://alias.example/",
        title: "Alias",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      const result = await json(app, "/v1/mcp/archive_tabs", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [cloudId] }),
      });
      expect(result.status).toBe(201);
      const audit = await json(app, "/v1/audit?limit=20", { headers: authHeaders(token) });
      const archiveEvent = asArray(asRecord(audit.body).events).find(
        (event) => asRecord(event).action === "tab.archive",
      );
      expect(asRecord(archiveEvent).actorType).toBe("mcp");
    });
  });
});
