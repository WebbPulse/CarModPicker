import { type ComponentType, lazy } from 'react';

const RELOAD_KEY = 'cmp_chunk_reload_attempted';

function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const message = error.message || '';
  return (
    error.name === 'ChunkLoadError' ||
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /error loading dynamically imported module/i.test(message)
  );
}

/**
 * Wraps React.lazy so that a failed dynamic import (typically caused by a stale
 * index.html referencing chunk hashes that no longer exist after a deploy)
 * forces a one-time hard reload to fetch the fresh asset manifest. A
 * sessionStorage flag prevents an infinite reload loop if the failure is real.
 */
// Generic bound: `ComponentType<Record<string, unknown>>` (D-06 Option B).
// `ComponentType<unknown>` was tried first (Option A) but fails inference for
// route-component `FC<{}>` exports because `unknown` is not assignable to `{}`.
// `Record<string, unknown>` accepts both no-prop route components and any
// object-prop component while still removing `any` from the public API.
export function lazyWithReload<
  T extends ComponentType<Record<string, unknown>>,
>(factory: () => Promise<{ default: T }>) {
  return lazy<T>(async () => {
    try {
      const mod = await factory();
      sessionStorage.removeItem(RELOAD_KEY);
      return mod;
    } catch (error) {
      if (isChunkLoadError(error) && !sessionStorage.getItem(RELOAD_KEY)) {
        sessionStorage.setItem(RELOAD_KEY, '1');
        window.location.reload();
        return new Promise<{ default: T }>(() => {});
      }
      throw error;
    }
  });
}
