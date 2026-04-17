import { useMemo } from 'react';

/**
 * Given a list of column keys, their drop priorities, and their minimum widths,
 * returns the subset of columns that fit within containerWidth.
 *
 * Columns with priority <= 1 are pinned and never dropped.
 * All others are dropped highest-priority-number-first until the total fits.
 * Returns all keys when containerWidth === 0 (not yet measured).
 */
export function useResponsiveColumns<K extends string>(
  keys: K[],
  priority: Record<K, number>,
  minWidth: Record<K, number>,
  containerWidth: number
): { visibleColumns: K[]; totalMinWidth: number } {
  const visibleColumns = useMemo(() => {
    if (containerWidth === 0) return keys;
    const kept = new Set<K>(keys);
    const dropOrder = [...keys].sort((a, b) => priority[b] - priority[a]);
    let total = keys.reduce((s, k) => s + minWidth[k], 0);
    for (const k of dropOrder) {
      if (total <= containerWidth) break;
      if (priority[k] <= 1) break;
      kept.delete(k);
      total -= minWidth[k];
    }
    return keys.filter((k) => kept.has(k));
  }, [keys, priority, minWidth, containerWidth]);

  const totalMinWidth = useMemo(
    () => visibleColumns.reduce((s, k) => s + minWidth[k], 0),
    [visibleColumns, minWidth]
  );

  return { visibleColumns, totalMinWidth };
}
