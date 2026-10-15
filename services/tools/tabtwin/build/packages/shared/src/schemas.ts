import { z } from "zod";
import {
  ACTOR_TYPES,
  ARCHIVE_CAUSES,
  BROWSER_FAMILIES,
  COMMAND_STATUSES,
  COMMAND_TYPES,
  PLATFORMS,
  TAB_EVENT_TYPES,
  TAB_STATES,
} from "./ids.ts";

export const uuidSchema = z.uuid();

export const browserFamilySchema = z.enum(BROWSER_FAMILIES);
export const platformSchema = z.enum(PLATFORMS);
export const tabStateSchema = z.enum(TAB_STATES);
export const archiveCauseSchema = z.enum(ARCHIVE_CAUSES);
export const commandTypeSchema = z.enum(COMMAND_TYPES);
export const commandStatusSchema = z.enum(COMMAND_STATUSES);
export const tabEventTypeSchema = z.enum(TAB_EVENT_TYPES);
export const actorTypeSchema = z.enum(ACTOR_TYPES);

export const registerDeviceBodySchema = z.object({
  name: z.string().trim().min(1).max(120),
  browserFamily: browserFamilySchema.default("chrome"),
  platform: platformSchema.default("macos"),
});

export const snapshotTabSchema = z.object({
  cloudId: uuidSchema.optional(),
  url: z.string().max(8192).default(""),
  title: z.string().max(2048).default(""),
  windowIndex: z.number().int().min(0).nullable().optional(),
  indexInWindow: z.number().int().min(0).nullable().optional(),
  pinned: z.boolean().optional(),
  active: z.boolean().optional(),
  audible: z.boolean().optional(),
  lastAccessedAt: z.string().datetime({ offset: true }).nullable().optional(),
  openedAt: z.string().datetime({ offset: true }).nullable().optional(),
});

export const snapshotBodySchema = z.object({
  tabs: z.array(snapshotTabSchema).max(500),
});

export const tabEventSchema = z.object({
  type: tabEventTypeSchema,
  cloudId: uuidSchema.optional(),
  url: z.string().max(8192).optional(),
  title: z.string().max(2048).optional(),
  windowIndex: z.number().int().min(0).nullable().optional(),
  indexInWindow: z.number().int().min(0).nullable().optional(),
  pinned: z.boolean().optional(),
  active: z.boolean().optional(),
  audible: z.boolean().optional(),
  lastAccessedAt: z.string().datetime({ offset: true }).nullable().optional(),
});

export const tabEventsBodySchema = z.object({
  events: z.array(tabEventSchema).min(1).max(200),
});

export const commandResultBodySchema = z.object({
  status: z.enum(["success", "fail", "unsupported", "stale"]),
  detail: z.record(z.string(), z.unknown()).optional(),
});

export const closeTabBodySchema = z.object({
  tabId: uuidSchema,
  idempotencyKey: z.string().min(1).max(200).optional(),
});

export const listTabsQuerySchema = z.object({
  state: z.enum(["open", "archived", "all"]).default("open"),
  workspaceId: uuidSchema.optional(),
});

export const createWorkspaceBodySchema = z.object({
  name: z.string().trim().min(1).max(120),
});

export const setTabWorkspaceBodySchema = z.object({
  tabId: uuidSchema,
  workspaceId: uuidSchema.nullable(),
});

export const archiveTabsBodySchema = z.object({
  tabIds: z.array(uuidSchema).min(1).max(200),
  idempotencyKey: z.string().min(1).max(200).optional(),
});

export const storedBindingSchema = z.object({
  cloudId: uuidSchema,
  nativeTabId: z.number().int(),
  url: z.string(),
  title: z.string(),
  windowId: z.number().int(),
  index: z.number().int().min(0),
});

export type SnapshotTabInput = z.infer<typeof snapshotTabSchema>;
export type SnapshotBody = z.infer<typeof snapshotBodySchema>;
export type TabEventInput = z.infer<typeof tabEventSchema>;
export type RegisterDeviceBody = z.infer<typeof registerDeviceBodySchema>;
export type CommandResultBody = z.infer<typeof commandResultBodySchema>;
export type CloseTabBody = z.infer<typeof closeTabBodySchema>;
export type StoredBindingInput = z.infer<typeof storedBindingSchema>;
