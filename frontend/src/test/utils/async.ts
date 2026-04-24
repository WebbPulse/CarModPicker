import { act } from '@testing-library/react';
import { vi } from 'vitest';

/**
 * Phase 8 D-07: shared async helpers for admin-area polling tests (Wave 4).
 *
 * Research §1 verdict: CrawlerAdmin (the only admin page currently known to
 * poll) uses `setInterval` only — no server-sent-events streaming. This file
 * therefore ships fake-timer helpers ONLY; no streaming stub (a stub would
 * be dead code).
 */

/**
 * Enter fake-timer mode. Pair with `stopFakeTimers()` in afterEach.
 *
 * Uses an explicit `toFake` list (setInterval / setTimeout / Date) to leave
 * microtasks alone — research §Pitfall 5 + §Assumptions Log A4 flag that
 * full fake-timer mode can interact badly with async `waitFor` calls.
 */
export function startFakeTimers(): void {
  vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout', 'Date'] });
}

export function stopFakeTimers(): void {
  vi.useRealTimers();
}

/**
 * Advance timers and flush React state updates. ALWAYS await this wrapper in
 * polling tests — per research §Pitfall 5, a bare `vi.advanceTimersByTime()`
 * leaves React with an unflushed batch and assertions see stale DOM.
 *
 * Uses `vi.advanceTimersByTimeAsync(...)` so that any promise chains kicked
 * off by polling callbacks (e.g. `setInterval(() => apiClient.get(...))`)
 * get a chance to settle within the same `act(...)` batch.
 */
export async function advanceTimersAndFlush(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
