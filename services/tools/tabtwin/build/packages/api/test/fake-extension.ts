import type { SnapshotTabInput } from "@tabtwin/shared";
import { authHeaders, json, type TestCtx } from "./helpers.ts";

export type FakeTab = {
  nativeId: number;
  url: string;
  title: string;
  windowIndex: number;
  indexInWindow: number;
  pinned: boolean;
  active: boolean;
};

/**
 * In-process stand-in for the Chrome MV3 worker.
 * Holds native-id → cloud-id mapping the same way the real extension does.
 * Used when CI has no Chrome.
 */
export class FakeExtension {
  readonly token: string;
  readonly nativeToCloud = new Map<number, string>();
  readonly cloudToNative = new Map<string, number>();
  tabs = new Map<number, FakeTab>();
  nextNativeId = 1;
  closeBehavior: "close" | "unsupported" | "fail" = "close";

  constructor(
    private readonly ctx: TestCtx,
    token: string,
  ) {
    this.token = token;
  }

  openTab(partial: Omit<FakeTab, "nativeId"> & { nativeId?: number }): FakeTab {
    const nativeId = partial.nativeId ?? this.nextNativeId++;
    const tab: FakeTab = {
      nativeId,
      url: partial.url,
      title: partial.title,
      windowIndex: partial.windowIndex,
      indexInWindow: partial.indexInWindow,
      pinned: partial.pinned,
      active: partial.active,
    };
    this.tabs.set(nativeId, tab);
    return tab;
  }

  snapshotPayload(): SnapshotTabInput[] {
    return [...this.tabs.values()].map((tab) => ({
      cloudId: this.nativeToCloud.get(tab.nativeId),
      url: tab.url,
      title: tab.title,
      windowIndex: tab.windowIndex,
      indexInWindow: tab.indexInWindow,
      pinned: tab.pinned,
      active: tab.active,
    }));
  }

  async snapshot() {
    const result = await json(this.ctx.app, "/v1/tabs/snapshot", {
      method: "POST",
      headers: authHeaders(this.token),
      body: JSON.stringify({ tabs: this.snapshotPayload() }),
    });
    const body = result.body as {
      mappings: Array<{ index: number; cloudId: string }>;
      archived: string[];
    };
    this.nativeToCloud.clear();
    this.cloudToNative.clear();
    const live = [...this.tabs.values()];
    for (const mapping of body.mappings) {
      const tab = live[mapping.index];
      if (!tab) continue;
      this.nativeToCloud.set(tab.nativeId, mapping.cloudId);
      this.cloudToNative.set(mapping.cloudId, tab.nativeId);
    }
    for (const cloudId of body.archived) {
      this.cloudToNative.delete(cloudId);
    }
    return result;
  }

  async event(event: Record<string, unknown>) {
    return json(this.ctx.app, "/v1/tabs/events", {
      method: "POST",
      headers: authHeaders(this.token),
      body: JSON.stringify({ events: [event] }),
    });
  }

  async pollAndExecute() {
    const listed = await json(this.ctx.app, "/v1/commands?status=queued", {
      method: "GET",
      headers: authHeaders(this.token),
    });
    const commands = (listed.body as { commands: Array<{ id: string; type: string; tabId: string | null }> })
      .commands;
    const reports = [];
    for (const command of commands) {
      reports.push(await this.execute(command));
    }
    return reports;
  }

  async execute(command: { id: string; type: string; tabId: string | null }) {
    if (command.type !== "close_tab") {
      return this.report(command.id, "unsupported", { reason: "unknown_type" });
    }
    if (this.closeBehavior === "unsupported") {
      return this.report(command.id, "unsupported", { reason: "browser_cannot_close" });
    }
    if (this.closeBehavior === "fail") {
      return this.report(command.id, "fail", { reason: "native_error" });
    }
    if (!command.tabId) {
      return this.report(command.id, "stale", { reason: "missing_tab_id" });
    }
    const nativeId = this.cloudToNative.get(command.tabId);
    if (nativeId === undefined || !this.tabs.has(nativeId)) {
      return this.report(command.id, "stale", { reason: "no_live_native_tab" });
    }
    this.tabs.delete(nativeId);
    this.nativeToCloud.delete(nativeId);
    this.cloudToNative.delete(command.tabId);
    return this.report(command.id, "success", { nativeClosed: true });
  }

  private async report(commandId: string, status: "success" | "fail" | "unsupported" | "stale", detail: Record<string, unknown>) {
    return json(this.ctx.app, `/v1/commands/${commandId}/result`, {
      method: "POST",
      headers: authHeaders(this.token),
      body: JSON.stringify({ status, detail }),
    });
  }
}
