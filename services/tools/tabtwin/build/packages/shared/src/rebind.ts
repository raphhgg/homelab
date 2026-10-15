import { brandCloudTabId, brandNativeTabId, type CloudTabId, type NativeTabId } from "./ids.ts";
import { storedBindingSchema } from "./schemas.ts";

export type StoredBinding = {
  cloudId: CloudTabId;
  nativeTabId: NativeTabId;
  url: string;
  title: string;
  windowId: number;
  index: number;
};

export type LiveNativeTab = {
  nativeTabId: NativeTabId;
  url: string;
  title: string;
  windowId: number;
  index: number;
};

export type ReboundTab = LiveNativeTab & { cloudId: CloudTabId };

export type RebindResult = {
  rebound: ReboundTab[];
  unmatchedLive: LiveNativeTab[];
  unmatchedStored: StoredBinding[];
};

function takeMatch(
  unused: StoredBinding[],
  predicate: (binding: StoredBinding) => boolean,
): StoredBinding | undefined {
  const index = unused.findIndex(predicate);
  if (index < 0) return undefined;
  const [match] = unused.splice(index, 1);
  return match;
}

/**
 * Recover cloud IDs after a service-worker restart or a Chrome restart.
 *
 * Native tab IDs recycle (and will recycle on iOS). Cloud UUIDs do not.
 * Exact native ID is only trusted when the URL still matches (same Chrome
 * session, worker woke up). After a full browser restart, match by
 * url+index, then by unique URL.
 */
export function rebindNativeTabs(args: {
  stored: StoredBinding[];
  live: LiveNativeTab[];
}): RebindResult {
  const unused = [...args.stored];
  const rebound: ReboundTab[] = [];
  const unmatchedLive: LiveNativeTab[] = [];

  for (const tab of args.live) {
    const exact = takeMatch(
      unused,
      (binding) => binding.nativeTabId === tab.nativeTabId && binding.url === tab.url,
    );
    if (exact) {
      rebound.push({ ...tab, cloudId: exact.cloudId });
      continue;
    }

    const byWindowIndex = takeMatch(
      unused,
      (binding) =>
        binding.url === tab.url &&
        binding.windowId === tab.windowId &&
        binding.index === tab.index,
    );
    if (byWindowIndex) {
      rebound.push({ ...tab, cloudId: byWindowIndex.cloudId });
      continue;
    }

    const byIndex = takeMatch(
      unused,
      (binding) => binding.url === tab.url && binding.index === tab.index,
    );
    if (byIndex) {
      rebound.push({ ...tab, cloudId: byIndex.cloudId });
      continue;
    }

    unmatchedLive.push(tab);
  }

  const stillUnmatched: LiveNativeTab[] = [];
  for (const tab of unmatchedLive) {
    const sameUrlStored = unused.filter((binding) => binding.url === tab.url);
    const sameUrlLive = unmatchedLive.filter((live) => live.url === tab.url);
    if (sameUrlStored.length === 1 && sameUrlLive.length === 1) {
      const match = takeMatch(unused, (binding) => binding.url === tab.url);
      if (match) {
        rebound.push({ ...tab, cloudId: match.cloudId });
        continue;
      }
    }
    stillUnmatched.push(tab);
  }

  return {
    rebound,
    unmatchedLive: stillUnmatched,
    unmatchedStored: unused,
  };
}

export function bindingFromLive(tab: ReboundTab): StoredBinding {
  return {
    cloudId: tab.cloudId,
    nativeTabId: tab.nativeTabId,
    url: tab.url,
    title: tab.title,
    windowId: tab.windowId,
    index: tab.index,
  };
}

export function parseStoredBinding(value: unknown): StoredBinding | null {
  const parsed = storedBindingSchema.safeParse(value);
  if (!parsed.success) return null;
  return {
    cloudId: brandCloudTabId(parsed.data.cloudId),
    nativeTabId: brandNativeTabId(parsed.data.nativeTabId),
    url: parsed.data.url,
    title: parsed.data.title,
    windowId: parsed.data.windowId,
    index: parsed.data.index,
  };
}
