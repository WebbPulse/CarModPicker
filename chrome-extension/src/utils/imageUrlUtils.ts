/**
 * Normalize image URLs for deduplication across size variants.
 * Handles common CDN patterns: Shopify (width=, height=), imgix (w=, h=), etc.
 */

const SIZE_PARAMS = new Set([
  "width",
  "height",
  "w",
  "h",
  "size",
  "resize",
  "dpr",
  "q",
  "quality",
  "format",
  "fit",
  "crop",
]);

const PREFERRED_WIDTH = 5760;

/**
 * Normalize URL to canonical form for dedup (strips size params).
 * e.g. ...?v=123&width=416 and ...?v=123&width=3000 → same canonical
 */
export function getCanonicalImageUrl(url: string): string {
  if (!url?.trim()) return "";
  try {
    const u = new URL(url.trim());
    const params = new URLSearchParams(u.search);
    for (const key of Array.from(params.keys())) {
      if (SIZE_PARAMS.has(key.toLowerCase())) {
        params.delete(key);
      }
    }
    const newSearch = params.toString();
    u.search = newSearch;
    u.protocol = "https:";
    u.hostname = u.hostname.toLowerCase().replace(/^www\./, "");
    return u.toString();
  } catch {
    return url;
  }
}

/**
 * Transform URL to request high resolution (adds/replaces width=).
 * Use when fetching to store best quality.
 */
export function getHighResImageUrl(url: string): string {
  if (!url?.trim()) return url;
  try {
    const u = new URL(url.trim());
    const params = new URLSearchParams(u.search);
    for (const key of Array.from(params.keys())) {
      if (SIZE_PARAMS.has(key.toLowerCase())) {
        params.delete(key);
      }
    }
    params.set("width", String(PREFERRED_WIDTH));
    u.search = params.toString();
    u.protocol = "https:";
    return u.toString();
  } catch {
    return url;
  }
}
