import { partsApi } from '../../api/parts';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';

interface CacheEntry {
  history: PartPriceHistoryReadWithRetailer[];
  cachedAt: number;
}

// Module-level in-memory cache. Per the task plan: 5-minute TTL, keyed by
// partId. Survives re-renders within the SPA session; cleared when the tab
// reloads. Intentionally small — the window/retailer key is implicit '90d'/all.
const CACHE_TTL_MS = 5 * 60 * 1000;
const historyCache = new Map<string, CacheEntry>();

// Track in-flight requests so re-mounted rows for the same partId don't fan
// out into duplicate network calls.
const inflight = new Map<string, Promise<PartPriceHistoryReadWithRetailer[]>>();

export function getCachedHistory(
  partId: string,
): PartPriceHistoryReadWithRetailer[] | null {
  const entry = historyCache.get(partId);
  if (!entry) return null;
  if (Date.now() - entry.cachedAt > CACHE_TTL_MS) {
    historyCache.delete(partId);
    return null;
  }
  return entry.history;
}

export function fetchHistory(
  partId: string,
): Promise<PartPriceHistoryReadWithRetailer[]> {
  const existing = inflight.get(partId);
  if (existing) return existing;

  const p = partsApi
    .getPartPriceHistorySummary(partId, { window: '90d' })
    .then((res) => {
      const history = res.data?.history ?? [];
      historyCache.set(partId, { history, cachedAt: Date.now() });
      inflight.delete(partId);
      return history;
    })
    .catch((err: unknown) => {
      inflight.delete(partId);
      console.warn('[SparklineCell]', partId, err);
      return [];
    });

  inflight.set(partId, p);
  return p;
}

// Test seam — vitest can clear the cache between tests via this export.
export function __resetSparklineCellCache(): void {
  historyCache.clear();
  inflight.clear();
}
