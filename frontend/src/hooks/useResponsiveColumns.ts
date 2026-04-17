import { useMemo, useRef } from 'react';

/**
 * Given a list of column keys, their drop priorities, and their minimum widths,
 * returns the subset of columns that fit within containerWidth.
 *
 * Columns with priority <= 1 are pinned and never dropped.
 * All others are dropped highest-priority-number-first until the total fits.
 * Returns all keys when containerWidth === 0 (not yet measured).
 *
 * visibleColumns preserves its array reference when the column set is unchanged,
 * so downstream memos that depend on it don't re-run on every resize.
 */
export function useResponsiveColumns<K extends string>(
  keys: K[],
  priority: Record<K, number>,
  minWidth: Record<K, number>,
  containerWidth: number
): { visibleColumns: K[]; totalMinWidth: number } {
  const prevRef = useRef<K[]>([]);

  const visibleColumns = useMemo(() => {
    let next: K[];
    if (containerWidth === 0) {
      next = keys;
    } else {
      const kept = new Set<K>(keys);
      const dropOrder = [...keys].sort((a, b) => priority[b] - priority[a]);
      let total = keys.reduce((s, k) => s + minWidth[k], 0);
      for (const k of dropOrder) {
        if (total <= containerWidth) break;
        if (priority[k] <= 1) break;
        kept.delete(k);
        total -= minWidth[k];
      }
      next = keys.filter((k) => kept.has(k));
    }
    const prev = prevRef.current;
    if (prev.length === next.length && next.every((k, i) => k === prev[i])) {
      return prev;
    }
    prevRef.current = next;
    return next;
  }, [keys, priority, minWidth, containerWidth]);

  const totalMinWidth = useMemo(
    () => visibleColumns.reduce((s, k) => s + minWidth[k], 0),
    [visibleColumns, minWidth]
  );

  return { visibleColumns, totalMinWidth };
}
