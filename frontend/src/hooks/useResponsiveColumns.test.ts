import { renderHook } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { useResponsiveColumns } from './useResponsiveColumns';

// Phase 8 D-09 — useResponsiveColumns is a pure memo-heavy hook. It takes a
// column set, per-column priority, per-column minWidth, and a containerWidth,
// then drops columns highest-priority-first until the set fits. containerWidth
// is the driver — the hook itself does not read matchMedia, but consumers
// commonly feed it a matchMedia-derived width. We still install a matchMedia
// stub for completeness / defensive coverage (Gotcha scaffold).

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

type Col = 'name' | 'category' | 'part_manufacturer' | 'price';

const keys: Col[] = ['name', 'category', 'part_manufacturer', 'price'];
const priority: Record<Col, number> = {
  name: 1, // pinned (<=1 never drops)
  category: 3,
  part_manufacturer: 2,
  price: 4,
};
const minWidth: Record<Col, number> = {
  name: 200,
  category: 120,
  part_manufacturer: 150,
  price: 100,
};

describe('useResponsiveColumns', () => {
  it('returns every column when containerWidth is 0 (not yet measured)', () => {
    const { result } = renderHook(() =>
      useResponsiveColumns(keys, priority, minWidth, 0)
    );

    expect(result.current.visibleColumns).toEqual(keys);
    expect(result.current.totalMinWidth).toBe(200 + 120 + 150 + 100);
  });

  it('returns every column when containerWidth is wide enough to fit the total', () => {
    const wide = 200 + 120 + 150 + 100; // 570
    const { result } = renderHook(() =>
      useResponsiveColumns(keys, priority, minWidth, wide)
    );

    expect(result.current.visibleColumns).toEqual(keys);
    expect(result.current.totalMinWidth).toBe(wide);
  });

  it('drops highest-priority-number columns first when width is constrained', () => {
    // Width 400 < 570 → must drop priority 4 (price); still 470 > 400 → drop
    // priority 3 (category); now 320 < 400 stop. Kept: name(1) + part_manufacturer(2).
    const { result } = renderHook(() =>
      useResponsiveColumns(keys, priority, minWidth, 400)
    );

    expect(result.current.visibleColumns).toEqual(['name', 'part_manufacturer']);
    expect(result.current.totalMinWidth).toBe(350);
  });

  it('never drops pinned (priority<=1) columns even when width is tiny', () => {
    // Width 50 is smaller than even the pinned name column (200). The hook
    // breaks out of the drop loop once it hits priority <= 1, so name stays.
    const { result } = renderHook(() =>
      useResponsiveColumns(keys, priority, minWidth, 50)
    );

    expect(result.current.visibleColumns).toContain('name');
  });

  it('preserves reference equality when the visible set is unchanged', () => {
    const { result, rerender } = renderHook(
      ({ w }: { w: number }) =>
        useResponsiveColumns(keys, priority, minWidth, w),
      { initialProps: { w: 0 } }
    );

    const firstRef = result.current.visibleColumns;
    rerender({ w: 0 });
    expect(result.current.visibleColumns).toBe(firstRef);
  });
});
