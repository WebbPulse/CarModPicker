/**
 * The latch a route guard leans on: false only until the first settle, true
 * for every later in-flight transition.
 */

import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useSessionSettled } from './useSessionSettled';

describe('useSessionSettled', () => {
  it('is false while the first resolution is in flight', () => {
    const { result } = renderHook(({ loading }) => useSessionSettled(loading), {
      initialProps: { loading: true },
    });
    expect(result.current).toBe(false);
  });

  it('latches true on the first settle and stays true', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useSessionSettled(loading),
      { initialProps: { loading: true } }
    );
    expect(result.current).toBe(false);

    rerender({ loading: false });
    expect(result.current).toBe(true);

    rerender({ loading: true });
    expect(result.current).toBe(true);
  });

  it('is true immediately when the session never loaded', () => {
    const { result } = renderHook(({ loading }) => useSessionSettled(loading), {
      initialProps: { loading: false },
    });
    expect(result.current).toBe(true);
  });
});
