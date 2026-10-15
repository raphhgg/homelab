import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

export function hashToken(token: string): string {
  return createHash("sha256").update(token, "utf8").digest("hex");
}

export function defaultArchiveTabsIdempotencyKey(tabIds: readonly string[]): string {
  const digest = createHash("sha256")
    .update([...new Set(tabIds)].sort().join(","))
    .digest("hex");
  return `archive_tabs:${digest}`;
}

export function generateToken(): string {
  return randomBytes(32).toString("base64url");
}

export function tokensEqual(left: string, right: string): boolean {
  const leftBuf = Buffer.from(left);
  const rightBuf = Buffer.from(right);
  if (leftBuf.length !== rightBuf.length) {
    return false;
  }
  return timingSafeEqual(leftBuf, rightBuf);
}

export function bearerFromHeader(header: string | undefined): string | undefined {
  if (!header) return undefined;
  const match = /^Bearer\s+(.+)$/i.exec(header.trim());
  return match?.[1]?.trim();
}
