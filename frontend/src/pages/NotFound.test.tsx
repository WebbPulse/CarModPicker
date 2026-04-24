// Phase 8 plan 08-14 (D-11) — static 404 page test for NotFound.
//
// Smallest page in the plan (27 lines). Covers the 404 render + "Go Home"
// link that App.tsx routes the catch-all `*` route to (Phase 6 FE-03).

import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import NotFound from './NotFound';

describe('NotFound page', () => {
  it('renders the 404 heading and "Page not found" message', () => {
    render(<NotFound />, testScenarios.unauthenticated);
    expect(screen.getByRole('heading', { name: /404/i })).toBeInTheDocument();
    expect(screen.getByText(/page not found/i)).toBeInTheDocument();
  });

  it('renders a Go Home link pointing at the root route', () => {
    render(<NotFound />, testScenarios.unauthenticated);
    const homeLink = screen.getByRole('link', { name: /go home/i });
    expect(homeLink).toBeInTheDocument();
    expect(homeLink).toHaveAttribute('href', '/');
  });
});
