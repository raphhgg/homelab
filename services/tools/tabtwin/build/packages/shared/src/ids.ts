export type Brand<T, B extends string> = T & { readonly __brand: B };

export type DeviceId = Brand<string, "DeviceId">;
export type CloudTabId = Brand<string, "CloudTabId">;
export type CommandId = Brand<string, "CommandId">;
export type NativeTabId = Brand<number, "NativeTabId">;
export type WorkspaceId = Brand<string, "WorkspaceId">;

export function brandDeviceId(value: string): DeviceId {
  return value as DeviceId;
}

export function brandCloudTabId(value: string): CloudTabId {
  return value as CloudTabId;
}

export function brandCommandId(value: string): CommandId {
  return value as CommandId;
}

export function brandNativeTabId(value: number): NativeTabId {
  return value as NativeTabId;
}

export function brandWorkspaceId(value: string): WorkspaceId {
  return value as WorkspaceId;
}

export const BROWSER_FAMILIES = ["chrome", "safari"] as const;
export type BrowserFamily = (typeof BROWSER_FAMILIES)[number];

export const PLATFORMS = ["macos", "ios"] as const;
export type Platform = (typeof PLATFORMS)[number];

export const TAB_STATES = ["open", "archived"] as const;
export type TabState = (typeof TAB_STATES)[number];

export const ARCHIVE_CAUSES = [
  "snapshot_reconcile",
  "native_removed",
  "close_tab",
  "archive_tabs",
] as const;
export type ArchiveCause = (typeof ARCHIVE_CAUSES)[number];

export function isAgentHeldArchive(cause: ArchiveCause | null): boolean {
  switch (cause) {
    case "archive_tabs":
    case "close_tab":
      return true;
    case "snapshot_reconcile":
    case "native_removed":
    case null:
      return false;
    default: {
      const _exhaustive: never = cause;
      return _exhaustive;
    }
  }
}

export const COMMAND_TYPES = ["close_tab"] as const;
export type CommandType = (typeof COMMAND_TYPES)[number];

export const COMMAND_STATUSES = [
  "queued",
  "success",
  "fail",
  "unsupported",
  "stale",
] as const;
export type CommandStatus = (typeof COMMAND_STATUSES)[number];

export const TAB_EVENT_TYPES = ["created", "updated", "removed", "moved"] as const;
export type TabEventType = (typeof TAB_EVENT_TYPES)[number];

export const ACTOR_TYPES = ["device", "mcp", "system"] as const;
export type ActorType = (typeof ACTOR_TYPES)[number];

export const SAFETY_TIERS = ["auto", "confirm", "explicit"] as const;
export type SafetyTier = (typeof SAFETY_TIERS)[number];

export const COMMAND_SAFETY: Record<CommandType, SafetyTier> = {
  close_tab: "confirm",
};

export type Actor = {
  type: ActorType;
  id: string;
};
