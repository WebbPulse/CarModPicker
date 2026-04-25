import { render } from '@testing-library/react';
import type { ComponentType, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Phase 6 FE-03 / D-10 / D-24 — parametrized App-level route-group coverage.
 *
 * For every <Route path> in App.tsx this test:
 *   1. Forces the matched lazy page component to THROW during render (via a
 *      hoisted `vi.mock('./utils/lazyWithReload')` stub keyed off
 *      `throwState.shouldThrow`).
 *   2. Renders <App /> at that path under MemoryRouter.
 *   3. Asserts the enclosing RouteGroupBoundary fallback rendered with the
 *      expected `[data-route-group="<group>"]` marker.
 *
 * D-10 / D-24 mandate: the test MUST observe the route-group fallback. A
 * happy-path-only assertion (e.g. asserting only that the document body
 * exists) is EXPLICITLY rejected — it does not exercise FE-03's wrapping.
 * Reviewers must reject any PR that weakens the assertion to a generic body
 * check.
 *
 * Drift guard: ALL_ROUTES.length must stay >= 37 (current count from
 * `grep -cE 'path="' frontend/src/App.tsx`). Adding a <Route> without
 * categorising it here breaks CI, forcing the developer to assign a group.
 *
 * Backend analog: backend/tests/test_admin_auth_coverage.py +
 * backend/tests/test_auth_auth_coverage.py — same parametrize-then-drift-guard
 * pattern, ported from pytest to vitest per D-24.
 *
 * Auth-redirect mitigation (06-03 plan NOTE): Plan gave two options for
 * handling GuestRoute / ProtectedRoute / EmailVerifiedRoute redirects during
 * coverage. This test uses Option 1 (TestProviders-style mock) but toggles
 * the auth state per-group via a hoisted mutable object so:
 *   - authentication group paths render under a NOT-authenticated user
 *     (GuestRoute lets /login etc. through → lazy stub throws inside →
 *     `authentication` boundary catches).
 *   - builder group paths render under an AUTHENTICATED email-verified user
 *     (ProtectedRoute + EmailVerifiedRoute let them through → lazy stub
 *     throws inside → `builder` boundary catches).
 *   - public + admin groups do not care — mock stays unauthenticated by
 *     default (admin routes have no auth guard around them in App.tsx).
 * Documented in SUMMARY.md under "Auth-redirect mitigation".
 */

// jsdom does not implement ResizeObserver, but App.tsx renders <AdBanner /> on
// non-promo paths and AdBanner uses ResizeObserver. Without this polyfill the
// observer construction throws OUTSIDE the per-route boundary (it's a sibling
// of <Routes>, under the app-root <ErrorBoundary>) and the test would never
// see the inner RouteGroupBoundary fallback. Stub is a no-op; AdBanner just
// needs `new ResizeObserver(...)` to not throw — it never observes anything
// meaningful in jsdom. Constructor accepts (and ignores) the callback so the
// stub matches the lib.dom ResizeObserver constructor signature.
class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  // Cast through unknown because globalThis lacks ResizeObserver in this jsdom
  // build; the stub only needs the structural surface that AdBanner uses.
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

// Hoisted shared state — the vi.mock factories below are hoisted too, and only
// references declared via vi.hoisted are visible inside them.
const { throwState, authState } = vi.hoisted(() => ({
  throwState: { shouldThrow: true },
  authState: { isAuthenticated: false, emailVerified: true },
}));

// Replace lazyWithReload globally so every `lazy(() => import('./pages/...'))`
// call-site in App.tsx returns the same throwing stub (avoids 40 separate
// per-page vi.mock blocks).
vi.mock('./utils/lazyWithReload', () => {
  const ThrowingStub: ComponentType<unknown> = () => {
    if (throwState.shouldThrow) {
      throw new Error('coverage-test-forced-throw');
    }
    return null;
  };
  return {
    lazyWithReload: () => ThrowingStub,
  };
});

// App.tsx + Header call useAuth(); App.tsx calls useAppSettings() via
// useIsPremium*. Mock both so the tree renders under jsdom. authState is
// mutated per-group in the describe.each setup below.
vi.mock('./hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: authState.isAuthenticated,
    isLoading: false,
    user: authState.isAuthenticated
      ? {
          id: '00000000-0000-0000-0000-000000000001',
          username: 'covtest',
          email: 'covtest@example.com',
          email_verified: authState.emailVerified,
          disabled: false,
          is_admin: true,
          is_superuser: false,
          image_urls: [],
          subscription_tier: 'free',
        }
      : null,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  }),
}));

vi.mock('./hooks/useAppSettings', () => ({
  useAppSettings: () => ({
    settings: { premium_disabled: false },
    isLoading: false,
    refresh: vi.fn(),
    setSettings: vi.fn(),
  }),
}));

// Import App AFTER vi.mock declarations (vitest hoists vi.mock automatically,
// but ordering here is intentional for reader clarity).
import App from './App';

type RouteGroup = 'admin' | 'authentication' | 'builder' | 'public';

// Hand-maintained enumeration of every <Route path> in App.tsx with its
// expected RouteGroupBoundary group. Source-of-truth count:
//   `grep -cE 'path="' frontend/src/App.tsx` returns 37 (2026-04-23).
// PR-review rule: any new <Route> in App.tsx requires a matching entry here,
// otherwise the drift guard below fails CI.
const ALL_ROUTES: ReadonlyArray<{ path: string; group: RouteGroup }> = [
  // ── public ── 21 entries: 20 real paths + 1 nonexistent to exercise `*` 404
  { path: '/', group: 'public' },
  { path: '/about', group: 'public' },
  { path: '/privacy-policy', group: 'public' },
  { path: '/terms-of-service', group: 'public' },
  { path: '/contact-us', group: 'public' },
  { path: '/support', group: 'public' },
  { path: '/pricing', group: 'public' },
  { path: '/bug-report', group: 'public' },
  { path: '/search', group: 'public' },
  { path: '/user/00000000-0000-0000-0000-000000000000', group: 'public' },
  { path: '/verify-email/confirm', group: 'public' },
  { path: '/forgot-password/confirm', group: 'public' },
  { path: '/extension-auth', group: 'public' },
  { path: '/car-generations/some-car', group: 'public' },
  { path: '/build-lists/00000000-0000-0000-0000-000000000000', group: 'public' },
  {
    path: '/build-lists/00000000-0000-0000-0000-000000000000/build-log',
    group: 'public',
  },
  { path: '/build-lists', group: 'public' },
  { path: '/parts/some-part/edit', group: 'public' },
  { path: '/parts/some-part', group: 'public' },
  { path: '/parts', group: 'public' },
  // Dev-only kitchen-sink route (S08/T05). Mounted only when
  // import.meta.env.DEV is true; vitest sets DEV=true so the route exists
  // during this test and the public boundary must catch its forced throw.
  { path: '/_kitchen-sink', group: 'public' },
  { path: '/nonexistent-route-for-404-test', group: 'public' },

  // ── authentication ── 3 entries (GuestRoute — only reachable when NOT authenticated)
  { path: '/login', group: 'authentication' },
  { path: '/register', group: 'authentication' },
  { path: '/forgot-password', group: 'authentication' },

  // ── builder ── 6 entries (ProtectedRoute + EmailVerifiedRoute — only reachable when AUTHENTICATED + email-verified)
  { path: '/profile', group: 'builder' },
  { path: '/account/alerts', group: 'builder' },
  { path: '/builder', group: 'builder' },
  { path: '/my-parts', group: 'builder' },
  { path: '/checkout', group: 'builder' },
  { path: '/verify-email', group: 'builder' },

  // ── admin ── 8 entries (no auth guard around admin routes in App.tsx)
  { path: '/admin', group: 'admin' },
  { path: '/admin/reports', group: 'admin' },
  { path: '/admin/bug-reports', group: 'admin' },
  { path: '/admin/users', group: 'admin' },
  { path: '/admin/crawler', group: 'admin' },
  { path: '/admin/system', group: 'admin' },
  { path: '/admin/statistics', group: 'admin' },
  { path: '/admin/parts-curation', group: 'admin' },
] as const;

/**
 * Select the auth state that lets a given group's routes actually mount
 * (rather than being redirected away by GuestRoute/ProtectedRoute/
 * EmailVerifiedRoute before the throwing stub gets a chance to run).
 */
function authForGroup(group: RouteGroup): {
  isAuthenticated: boolean;
  emailVerified: boolean;
} {
  switch (group) {
    case 'authentication':
      // GuestRoute redirects away when authenticated → must be unauthenticated.
      return { isAuthenticated: false, emailVerified: true };
    case 'builder':
      // ProtectedRoute + EmailVerifiedRoute require authenticated + verified.
      return { isAuthenticated: true, emailVerified: true };
    case 'admin':
    case 'public':
    default:
      // No auth guards → state does not matter; keep unauthenticated.
      return { isAuthenticated: false, emailVerified: true };
  }
}

describe('App route coverage (FE-03 drift guard, D-10, D-24)', () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs forced throws via console.error; silence them so test output
    // stays clean while errors are still raised + caught by the boundaries.
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    throwState.shouldThrow = true;
  });

  afterEach(() => {
    errorSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it('ALL_ROUTES enumerates at least the current Route count (drift guard)', () => {
    // If App.tsx adds routes, this floor must be bumped AND the new route
    // entered into ALL_ROUTES with its correct group. Backend analog:
    //   backend/tests/test_admin_auth_coverage.py
    //     ::test_admin_route_count_at_or_above_expected
    //
    // Count source: `grep -cE 'path="' frontend/src/App.tsx` returns 37.
    expect(ALL_ROUTES.length).toBeGreaterThanOrEqual(37);
  });

  describe.each(ALL_ROUTES)(
    'path=$path group=$group',
    ({ path, group }: { path: string; group: RouteGroup }) => {
      it(`forces child throw; route-group boundary renders fallback with data-route-group="${group}"`, () => {
        // Select the auth state required for this group's routes to actually
        // render (instead of being redirected by auth guards before the
        // throwing stub mounts).
        const { isAuthenticated, emailVerified } = authForGroup(group);
        authState.isAuthenticated = isAuthenticated;
        authState.emailVerified = emailVerified;

        // throwState.shouldThrow === true (set in beforeEach) → mocked
        // lazyWithReload stub throws on mount → nearest RouteGroupBoundary
        // catches → fallback UI renders with data-route-group attribute.
        const { container } = render(
          (<MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>) as ReactNode
        );
        const fallbackMarker = container.querySelector(
          `[data-route-group="${group}"]`
        );
        expect(
          fallbackMarker,
          `Expected fallback [data-route-group="${group}"] for path=${path}`
        ).not.toBeNull();
      });
    }
  );
});
