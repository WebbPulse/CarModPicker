import * as Sentry from '@sentry/react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Phase 6 FE-03 — per-route-group ErrorBoundary (D-07).
 *
 * Wraps a route-group's children in @sentry/react's ErrorBoundary so that:
 *   1. A render-time throw inside one of the four groups (admin, authentication,
 *      builder, public) is contained — the other three groups keep rendering,
 *      Header + Footer stay usable, and the whole app does not blank-screen.
 *   2. The fallback UI exposes the Sentry `eventId` to the user as a copyable
 *      correlation token (D-08), plus a Retry button (calls `resetError`) and
 *      a Go Home navigation (`useNavigate('/')`).
 *   3. `beforeCapture` tags the captured Sentry event with `route_group` so
 *      crashes can be sliced by route-group in the Sentry dashboard.
 *
 * Lives INSIDE the existing app-root <ErrorBoundary> + top-level <Suspense>;
 * D-09 keeps both intact as the last-resort outer catch.
 */
export type RouteGroupName = 'admin' | 'authentication' | 'builder' | 'public';

export function RouteGroupBoundary({
  groupName,
  children,
}: {
  groupName: RouteGroupName;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sentry.ErrorBoundary
      beforeCapture={(scope) => scope.setTag('route_group', groupName)}
      fallback={(errorData) => {
        // Destructure inside the body so the strict
        // @typescript-eslint/unbound-method rule does not flag `resetError`
        // (typed as a method on FallbackRender's errorData arg) at the
        // destructure site (FE-01 D-01).
        const { error, eventId } = errorData;
        const handleRetry = () => {
          errorData.resetError();
        };
        const handleGoHome = () => {
          // react-router-dom v7 `navigate` returns a Promise; the strict
          // @typescript-eslint/no-floating-promises rule (FE-01 D-01)
          // requires either `await` or an explicit `void`. The fallback UI
          // does not need to await navigation completion, so mark it ignored.
          void navigate('/');
        };
        return (
          <section
            data-route-group={groupName}
            className="container mx-auto px-4 py-16"
          >
            <div className="mx-auto max-w-lg p-8 bg-neutral-800/50 rounded-xl text-neutral-200">
              <h2 className="text-2xl font-semibold text-neutral-100 mb-3">
                Something went wrong in the {groupName} section
              </h2>
              <p className="text-sm text-neutral-400 mb-2">
                {error instanceof Error ? error.message : 'Unknown error'}
              </p>
              <p className="text-xs text-neutral-500 mb-6">
                Event ID: <code className="font-mono">{eventId}</code>
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleRetry}
                  className="btn-primary"
                >
                  Retry
                </button>
                <button
                  type="button"
                  onClick={handleGoHome}
                  className="btn-secondary"
                >
                  Go Home
                </button>
              </div>
            </div>
          </section>
        );
      }}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}

export default RouteGroupBoundary;
