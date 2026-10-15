import { describe, expect, it } from "vitest";
import { brandCloudTabId, brandNativeTabId } from "../src/ids.ts";
import { rebindNativeTabs, type LiveNativeTab, type StoredBinding } from "../src/rebind.ts";

function binding(partial: Partial<StoredBinding> & Pick<StoredBinding, "cloudId" | "nativeTabId">): StoredBinding {
  return {
    url: "https://example.com",
    title: "Example",
    windowId: 1,
    index: 0,
    ...partial,
  };
}

function live(partial: Partial<LiveNativeTab> & Pick<LiveNativeTab, "nativeTabId">): LiveNativeTab {
  return {
    url: "https://example.com",
    title: "Example",
    windowId: 1,
    index: 0,
    ...partial,
  };
}

describe("rebindNativeTabs", () => {
  it("keeps the cloud ID when the native tab id and URL still match", () => {
    const cloudId = brandCloudTabId("11111111-1111-4111-8111-111111111111");
    const nativeTabId = brandNativeTabId(42);
    const result = rebindNativeTabs({
      stored: [binding({ cloudId, nativeTabId })],
      live: [live({ nativeTabId })],
    });
    expect(result.rebound).toEqual([
      expect.objectContaining({ cloudId, nativeTabId }),
    ]);
    expect(result.unmatchedLive).toEqual([]);
  });

  it("does not trust a recycled native id when the URL changed", () => {
    const cloudId = brandCloudTabId("11111111-1111-4111-8111-111111111111");
    const result = rebindNativeTabs({
      stored: [
        binding({
          cloudId,
          nativeTabId: brandNativeTabId(42),
          url: "https://old.example",
        }),
      ],
      live: [
        live({
          nativeTabId: brandNativeTabId(42),
          url: "https://new.example",
        }),
      ],
    });
    expect(result.rebound).toEqual([]);
    expect(result.unmatchedLive).toHaveLength(1);
    expect(result.unmatchedStored[0]?.cloudId).toBe(cloudId);
  });

  it("recovers cloud IDs after a Chrome restart that issued new native ids", () => {
    const first = brandCloudTabId("11111111-1111-4111-8111-111111111111");
    const second = brandCloudTabId("22222222-2222-4222-8222-222222222222");
    const result = rebindNativeTabs({
      stored: [
        binding({
          cloudId: first,
          nativeTabId: brandNativeTabId(10),
          url: "https://a.example",
          index: 0,
          windowId: 1,
        }),
        binding({
          cloudId: second,
          nativeTabId: brandNativeTabId(11),
          url: "https://b.example",
          index: 1,
          windowId: 1,
        }),
      ],
      live: [
        live({
          nativeTabId: brandNativeTabId(90),
          url: "https://a.example",
          index: 0,
          windowId: 7,
        }),
        live({
          nativeTabId: brandNativeTabId(91),
          url: "https://b.example",
          index: 1,
          windowId: 7,
        }),
      ],
    });
    expect(result.rebound.map((tab) => [tab.url, tab.cloudId])).toEqual([
      ["https://a.example", first],
      ["https://b.example", second],
    ]);
    expect(result.unmatchedLive).toEqual([]);
    expect(result.unmatchedStored).toEqual([]);
  });

  it("does not reuse a cloud ID when two live tabs share a URL", () => {
    const cloudId = brandCloudTabId("11111111-1111-4111-8111-111111111111");
    const result = rebindNativeTabs({
      stored: [
        binding({
          cloudId,
          nativeTabId: brandNativeTabId(1),
          url: "https://dup.example",
          index: 5,
        }),
      ],
      live: [
        live({
          nativeTabId: brandNativeTabId(20),
          url: "https://dup.example",
          index: 0,
        }),
        live({
          nativeTabId: brandNativeTabId(21),
          url: "https://dup.example",
          index: 1,
        }),
      ],
    });
    expect(result.rebound).toEqual([]);
    expect(result.unmatchedLive).toHaveLength(2);
  });

  it("matches a unique URL when index and window both changed", () => {
    const cloudId = brandCloudTabId("11111111-1111-4111-8111-111111111111");
    const result = rebindNativeTabs({
      stored: [
        binding({
          cloudId,
          nativeTabId: brandNativeTabId(1),
          url: "https://only.example",
          index: 3,
          windowId: 1,
        }),
      ],
      live: [
        live({
          nativeTabId: brandNativeTabId(99),
          url: "https://only.example",
          index: 0,
          windowId: 8,
        }),
      ],
    });
    expect(result.rebound[0]?.cloudId).toBe(cloudId);
  });
});
