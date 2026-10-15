import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import { archiveTab } from "../src/services/tabs.ts";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi } from "./helpers.ts";
import { FakeExtension } from "./fake-extension.ts";

describe("tab upsert and snapshot reconcile", () => {
  it("mints cloud UUIDs and does not echo native tab ids", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://a.example/",
        title: "A",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      ext.openTab({
        url: "https://b.example/",
        title: "B",
        windowIndex: 0,
        indexInWindow: 1,
        pinned: false,
        active: false,
      });
      const snap = await ext.snapshot();
      expect(snap.status).toBe(200);
      const mappings = asArray(asRecord(snap.body).mappings);
      expect(mappings).toHaveLength(2);
      const cloudIds = mappings.map((item) => asRecord(item).cloudId);
      for (const id of cloudIds) {
        expect(id).toMatch(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
        );
      }
      const listed = await json(app, "/v1/tabs", { headers: authHeaders(token) });
      const tabs = asArray(asRecord(listed.body).tabs);
      expect(tabs).toHaveLength(2);
      for (const tab of tabs) {
        expect(asRecord(tab).id).toBeDefined();
        expect(asRecord(tab).nativeTabId).toBeUndefined();
        expect(asRecord(tab).state).toBe("open");
      }
    });
  });

  it("archives twins missing from a later snapshot", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://keep.example/",
        title: "Keep",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      ext.openTab({
        url: "https://drop.example/",
        title: "Drop",
        windowIndex: 0,
        indexInWindow: 1,
        pinned: false,
        active: false,
      });
      await ext.snapshot();
      const dropNative = [...ext.tabs.values()].find((tab) => tab.url.includes("drop"));
      if (!dropNative) throw new Error("missing drop tab");
      const dropCloud = ext.nativeToCloud.get(dropNative.nativeId);
      ext.tabs.delete(dropNative.nativeId);
      const second = await ext.snapshot();
      expect(asArray(asRecord(second.body).archived)).toContain(dropCloud);
      const listed = await json(app, `/v1/tabs/${dropCloud}`, { headers: authHeaders(token) });
      expect(asRecord(listed.body).state).toBe("archived");
      const open = await json(app, "/v1/tabs", { headers: authHeaders(token) });
      expect(asArray(asRecord(open.body).tabs)).toHaveLength(1);
    });
  });

  it("keeps the same cloud ID when the snapshot resends it", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://stable.example/",
        title: "Stable",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const firstId = [...ext.nativeToCloud.values()][0];
      ext.openTab({
        nativeId: 1,
        url: "https://stable.example/path",
        title: "Stable path",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      expect([...ext.nativeToCloud.values()][0]).toBe(firstId);
      const listed = await json(app, "/v1/tabs", { headers: authHeaders(token) });
      expect(asRecord(asArray(asRecord(listed.body).tabs)[0]).url).toBe("https://stable.example/path");
    });
  });

  it("applies created/updated/removed events", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      const created = await ext.event({
        type: "created",
        url: "https://evt.example/",
        title: "Evt",
        windowIndex: 0,
        indexInWindow: 0,
      });
      const cloudId = asRecord(asArray(asRecord(created.body).results)[0]).cloudId;
      expect(cloudId).toBeTruthy();
      await ext.event({
        type: "updated",
        cloudId,
        url: "https://evt.example/next",
        title: "Next",
      });
      const updated = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(updated.body).title).toBe("Next");
      await ext.event({ type: "removed", cloudId });
      const removed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(removed.body).state).toBe("archived");
    });
  });

  it("does not null workspace_id on snapshot upsert", async () => {
    await withApi(async ({ app, sql }) => {
      const { device, token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://keep-ws.example/",
        title: "Keep ws",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");
      const workspaceId = randomUUID();
      await sql`
        INSERT INTO workspaces (id, device_id, name)
        VALUES (${workspaceId}, ${device.id}, 'Inbox')
      `;
      await sql`
        UPDATE tabs SET workspace_id = ${workspaceId} WHERE id = ${cloudId} AND device_id = ${device.id}
      `;
      await ext.snapshot();
      const listed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      const body = asRecord(listed.body);
      expect(body.workspaceId).toBe(workspaceId);
      expect(body.state).toBe("open");
      expect(body.archivedCause).toBeUndefined();
    });
  });

  it("keeps an agent-held archive archived when the snapshot still lists that cloudId", async () => {
    await withApi(async ({ app, sql }) => {
      const { device, token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://held.example/",
        title: "Held",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");
      await archiveTab(sql, {
        deviceId: device.id,
        tabId: cloudId,
        actor: { type: "mcp", id: device.id },
        reason: "archive_tabs",
      });
      await ext.snapshot();
      const listed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(listed.body).state).toBe("archived");
      const [row] = await sql<{ archived_cause: string | null; workspace_id: string | null }[]>`
        SELECT archived_cause, workspace_id FROM tabs WHERE id = ${cloudId}
      `;
      expect(row?.archived_cause).toBe("archive_tabs");
      expect(row?.workspace_id).toBeNull();
    });
  });

  it("reopens a Phase 1 archived row (null cause) when the snapshot still lists that cloudId", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://phase1.example/",
        title: "Phase1",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");
      await sql`
        UPDATE tabs SET
          state = 'archived',
          archived_at = now(),
          archived_cause = NULL
        WHERE id = ${cloudId}
      `;
      await ext.snapshot();
      const listed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(listed.body).state).toBe("open");
      expect(asRecord(listed.body).archivedAt).toBeNull();
      expect(asRecord(listed.body).workspaceId).toBeNull();
    });
  });

  it("upgrades a device-lost archive to agent-held without a second tab.archive audit", async () => {
    await withApi(async ({ app, sql }) => {
      const { device, token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://upgrade.example/",
        title: "Upgrade",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const cloudId = [...ext.nativeToCloud.values()][0];
      if (!cloudId) throw new Error("no cloud id");
      ext.tabs.clear();
      await ext.snapshot();
      const [before] = await sql<{ archived_cause: string | null }[]>`
        SELECT archived_cause FROM tabs WHERE id = ${cloudId}
      `;
      expect(before?.archived_cause).toBe("snapshot_reconcile");
      const auditsBefore = await sql<{ count: string }[]>`
        SELECT count(*)::text AS count FROM audit_events
        WHERE tab_id = ${cloudId} AND action = 'tab.archive'
      `;
      await archiveTab(sql, {
        deviceId: device.id,
        tabId: cloudId,
        actor: { type: "mcp", id: device.id },
        reason: "archive_tabs",
      });
      const [after] = await sql<{ archived_cause: string | null; state: string }[]>`
        SELECT archived_cause, state FROM tabs WHERE id = ${cloudId}
      `;
      expect(after?.state).toBe("archived");
      expect(after?.archived_cause).toBe("archive_tabs");
      const auditsAfter = await sql<{ count: string }[]>`
        SELECT count(*)::text AS count FROM audit_events
        WHERE tab_id = ${cloudId} AND action = 'tab.archive'
      `;
      expect(auditsAfter[0]?.count).toBe(auditsBefore[0]?.count);
      ext.openTab({
        url: "https://upgrade.example/",
        title: "Upgrade",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      const rebound = [...ext.tabs.keys()][0];
      if (rebound === undefined) throw new Error("missing native tab");
      ext.nativeToCloud.set(rebound, cloudId);
      await ext.snapshot();
      const listed = await json(app, `/v1/tabs/${cloudId}`, { headers: authHeaders(token) });
      expect(asRecord(listed.body).state).toBe("archived");
    });
  });
});
