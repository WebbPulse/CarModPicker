import { useEffect, useMemo, useRef, useState } from 'react';
import { partsApi } from '../api/parts';
import type {
  PriceHistoryBatchRequest,
  PriceHistorySummary,
} from '../types/Api';

interface UsePartPriceSummariesResult {
  summaries: Record<string, PriceHistorySummary>;
  isLoading: boolean;
  error: string | null;
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return 'Failed to load price history summaries';
}

const EMPTY_SUMMARIES: Record<string, PriceHistorySummary> = Object.freeze({});

export function usePartPriceSummaries(
  partIds: string[],
  window: PriceHistoryBatchRequest['window'] = '90d'
): UsePartPriceSummariesResult {
  // Sorted-stable ID join — used both as memo dep and dedupe key. Computing
  // a primitive string lets the effect's deps array be primitive-only, which
  // sidesteps the new-array-each-render re-render loop.
  const sortedKey = useMemo(
    () => (partIds.length === 0 ? '' : [...partIds].sort().join(',')),
    [partIds]
  );
  const sortedIds = useMemo(
    () => (sortedKey === '' ? [] : sortedKey.split(',')),
    [sortedKey]
  );
  const stableKey = sortedKey === '' ? '' : `${sortedKey}|${window ?? '90d'}`;

  const lastKeyRef = useRef<string | null>(null);
  const [summaries, setSummaries] =
    useState<Record<string, PriceHistorySummary>>(EMPTY_SUMMARIES);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Debounce: skip when nothing has changed since the last effect run.
    if (lastKeyRef.current === stableKey) return;
    lastKeyRef.current = stableKey;

    if (stableKey === '') {
      // Empty-IDs short-circuit. Use the stable EMPTY_SUMMARIES singleton so
      // consumers don't see a new object reference each render.
      setSummaries(EMPTY_SUMMARIES);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    partsApi
      .getBatchPriceHistorySummary({
        part_ids: sortedIds,
        ...(window !== undefined ? { window } : {}),
      })
      .then((res) => {
        if (cancelled) return;
        setSummaries(res.data.summaries);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        console.warn('[usePartPriceSummaries]', err);
        setError(errorMessage(err));
        setSummaries(EMPTY_SUMMARIES);
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [stableKey, sortedIds, window]);

  return { summaries, isLoading, error };
}
