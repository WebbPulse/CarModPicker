import type { ReactElement } from 'react';

/**
 * Phase 6 FE-03 — extracted from inline 404 element in App.tsx so the catch-all
 * `*` route can be lazy-loaded like every other page. This lets
 * frontend/src/App.coverage.test.tsx force the same throwing-stub mock to
 * apply to the 404 path, which in turn lets the parametrized coverage test
 * verify the catch-all <Route> is wrapped in RouteGroupBoundary("public") via
 * the same mechanism as every other route (D-10 / D-24).
 *
 * No visual change vs the previous inline JSX (App.tsx pre-06-03 lines 285-309).
 */
function NotFound(): ReactElement {
  return (
    <div className="container mx-auto px-4 py-20 text-center">
      <div className="glass-card rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">
        <h1 className="text-4xl font-bold text-gradient mb-4">404</h1>
        <p className="text-neutral-400 mb-6">Page not found</p>
        <a href="/" className="btn-primary inline-flex items-center">
          Go Home
        </a>
      </div>
    </div>
  );
}

export default NotFound;
