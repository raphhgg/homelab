import { describe, expect, it } from "vitest";
import { asArray, asRecord, authHeaders, json, seedDevice, withApi } from "./helpers.ts";
import { FakeExtension } from "./fake-extension.ts";

describe("workspaces", () => {
  it("creates a workspace and lists it for this device only", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql, "Owner");
      const other = await seedDevice(sql, "Other");
      const created = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ name: "  Research  " }),
      });
      expect(created.status).toBe(201);
      const workspace = asRecord(created.body);
      expect(workspace.name).toBe("Research");
      expect(workspace.id).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      );
      expect(workspace.createdAt).toBeTruthy();
      expect(workspace.updatedAt).toBeTruthy();

      const listed = await json(app, "/v1/workspaces", { headers: authHeaders(token) });
      expect(asArray(asRecord(listed.body).workspaces)).toHaveLength(1);
      expect(asRecord(asArray(asRecord(listed.body).workspaces)[0]).id).toBe(workspace.id);

      const otherList = await json(app, "/v1/workspaces", { headers: authHeaders(other.token) });
      expect(asArray(asRecord(otherList.body).workspaces)).toHaveLength(0);
    });
  });

  it("assigns a tab to a workspace and unassigns with null", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://member.example/",
        title: "Member",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const tabId = [...ext.nativeToCloud.values()][0];
      const created = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ name: "Inbox" }),
      });
      const workspaceId = asRecord(created.body).id;

      const assigned = await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabId, workspaceId }),
      });
      expect(assigned.status).toBe(200);
      expect(asRecord(assigned.body).workspaceId).toBe(workspaceId);

      const fetched = await json(app, `/v1/tabs/${tabId}`, { headers: authHeaders(token) });
      expect(asRecord(fetched.body).workspaceId).toBe(workspaceId);

      const cleared = await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabId, workspaceId: null }),
      });
      expect(asRecord(cleared.body).workspaceId).toBeNull();
    });
  });

  it("lists tabs by workspace and by archived state", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const ext = new FakeExtension({ app, sql }, token);
      ext.openTab({
        url: "https://in.example/",
        title: "In",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      ext.openTab({
        url: "https://out.example/",
        title: "Out",
        windowIndex: 0,
        indexInWindow: 1,
        pinned: false,
        active: false,
      });
      await ext.snapshot();
      const listed = await json(app, "/v1/tabs?state=all", { headers: authHeaders(token) });
      const allTabs = asArray(asRecord(listed.body).tabs).map(asRecord);
      const inTab = allTabs.find((tab) => tab.title === "In");
      const outTab = allTabs.find((tab) => tab.title === "Out");
      if (!inTab || !outTab) throw new Error("missing seeded tabs");

      const created = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ name: "Inbox" }),
      });
      const workspaceId = asRecord(created.body).id;
      await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabId: inTab.id, workspaceId }),
      });

      const byWorkspace = await json(app, `/v1/tabs?workspaceId=${workspaceId}`, {
        headers: authHeaders(token),
      });
      const workspaceTabs = asArray(asRecord(byWorkspace.body).tabs).map(asRecord);
      expect(workspaceTabs).toHaveLength(1);
      expect(workspaceTabs[0]?.id).toBe(inTab.id);

      await json(app, "/v1/tabs/archive", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ tabIds: [outTab.id] }),
      });
      const archived = await json(app, "/v1/tabs?state=archived", { headers: authHeaders(token) });
      const archivedTabs = asArray(asRecord(archived.body).tabs).map(asRecord);
      expect(archivedTabs.map((tab) => tab.id)).toContain(outTab.id);
      expect(archivedTabs.map((tab) => tab.id)).not.toContain(inTab.id);

      const open = await json(app, "/v1/tabs", { headers: authHeaders(token) });
      expect(asArray(asRecord(open.body).tabs).map((tab) => asRecord(tab).id)).toEqual([inTab.id]);
    });
  });

  it("returns 404 when the tab or workspace is not on this device", async () => {
    await withApi(async ({ app, sql }) => {
      const owner = await seedDevice(sql, "Owner");
      const other = await seedDevice(sql, "Other");
      const ext = new FakeExtension({ app, sql }, owner.token);
      ext.openTab({
        url: "https://mine.example/",
        title: "Mine",
        windowIndex: 0,
        indexInWindow: 0,
        pinned: false,
        active: true,
      });
      await ext.snapshot();
      const tabId = [...ext.nativeToCloud.values()][0];
      const workspace = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(owner.token),
        body: JSON.stringify({ name: "Owner box" }),
      });
      const workspaceId = asRecord(workspace.body).id;

      const wrongWorkspace = await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(other.token),
        body: JSON.stringify({ tabId, workspaceId }),
      });
      expect(wrongWorkspace.status).toBe(404);

      const otherWorkspace = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(other.token),
        body: JSON.stringify({ name: "Other box" }),
      });
      const stolen = await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(owner.token),
        body: JSON.stringify({
          tabId,
          workspaceId: asRecord(otherWorkspace.body).id,
        }),
      });
      expect(stolen.status).toBe(404);

      const missingTab = await json(app, "/v1/tabs/workspace", {
        method: "POST",
        headers: authHeaders(owner.token),
        body: JSON.stringify({
          tabId: "00000000-0000-4000-8000-000000000099",
          workspaceId,
        }),
      });
      expect(missingTab.status).toBe(404);
    });
  });

  it("rejects an empty workspace name", async () => {
    await withApi(async ({ app, sql }) => {
      const { token } = await seedDevice(sql);
      const empty = await json(app, "/v1/workspaces", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ name: "   " }),
      });
      expect(empty.status).toBe(400);
    });
  });
});
