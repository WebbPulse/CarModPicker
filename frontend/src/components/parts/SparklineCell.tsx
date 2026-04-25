import { useEffect, useRef, useState } from 'react';
import { partsApi } from '../../api/parts';
import type {
  PartPriceHistoryReadWithRetailer,
  PriceHistorySummary,
} from '../../types/Api';
import Sparkline from '../charts/Sparkline';

interface SparklineCellProps {
  partId: string;
  summary: PriceHistorySummary | null | undefined;
  width?: number;
  height?: number;
  ariaLabel?: string;
}

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

function getCachedHistory(
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

function fetchHistory(
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

const DEFAULT_WIDTH = 60;
const DEFAULT_HEIGHT = 16;

export default function SparklineCell({
  partId,
  summary,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  ariaLabel,
}: SparklineCellProps) {
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const [history, setHistory] = useState<
    PartPriceHistoryReadWithRetailer[] | null
  >(() => getCachedHistory(partId));
  const [shouldFetch, setShouldFetch] = useState(false);

  const observationCount = summary?.observation_count ?? 0;
  const hasMulti = observationCount >= 2;

  // Set up IntersectionObserver only when the summary indicates multiple
  // observations (zero/single observations don't need a per-part fetch — the
  // summary itself drives the rendering). Re-runs if partId/hasMulti change.
  useEffect(() => {
    if (!hasMulti) return;
    if (history !== null) return; // already populated from cache

    const node = wrapperRef.current;
    if (!node) return;

    // Fallback: environments without IntersectionObserver (older jsdom in
    // some test setups) — fetch eagerly.
    if (typeof IntersectionObserver === 'undefined') {
      setShouldFetch(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShouldFetch(true);
            observer.disconnect();
            observerRef.current = null;
            break;
          }
        }
      },
      { rootMargin: '100px' },
    );
    observer.observe(node);
    observerRef.current = observer;

    return () => {
      observer.disconnect();
      observerRef.current = null;
    };
  }, [partId, hasMulti, history]);

  // Trigger the actual fetch when shouldFetch flips true.
  useEffect(() => {
    if (!shouldFetch) return;
    if (history !== null) return;
    let cancelled = false;
    void fetchHistory(partId).then((h) => {
      if (cancelled) return;
      setHistory(h);
    });
    return () => {
      cancelled = true;
    };
  }, [shouldFetch, partId, history]);

  // Zero observations → render nothing (caller controls layout spacing).
  if (observationCount === 0 || !summary) {
    return null;
  }

  // Single observation → render the centered dot directly off the summary,
  // no fetch needed. Synthesize a one-element history from the summary.
  if (observationCount === 1) {
    const synthetic: PartPriceHistoryReadWithRetailer[] =
      summary.last_cents !== null && summary.last_observed_at !== null
        ? [
            {
              id: `synthetic-${partId}`,
              part_listing_id: `synthetic-${partId}`,
              price_cents: summary.last_cents,
              observed_at: summary.last_observed_at,
              retailer_id: 'synthetic',
              retailer_name: 'synthetic',
            },
          ]
        : [];
    return (
      <span
        ref={wrapperRef}
        data-testid="sparkline-cell"
        data-part-id={partId}
      >
        <Sparkline
          history={synthetic}
          width={width}
          height={height}
          ariaLabel={ariaLabel ?? 'Price history sparkline'}
        />
      </span>
    );
  }

  // Multi-observation: wait for lazy-loaded history. Until then, reserve
  // the slot with an empty span so layout doesn't jump.
  return (
    <span
      ref={wrapperRef}
      data-testid="sparkline-cell"
      data-part-id={partId}
      style={{ display: 'inline-block', width, height }}
    >
      {history && history.length > 0 ? (
        <Sparkline
          history={history}
          width={width}
          height={height}
          ariaLabel={ariaLabel ?? 'Price history sparkline'}
        />
      ) : null}
    </span>
  );
}
