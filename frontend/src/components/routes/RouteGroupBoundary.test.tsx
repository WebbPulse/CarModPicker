import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RouteGroupBoundary } from './RouteGroupBoundary';

/**
 * Phase 6 FE-03 / D-07 / D-08:
 *  - RouteGroupBoundary wraps a route-group's children with a Sentry-backed
 *    ErrorBoundary that surfaces eventId + Retry + Go Home in the fallback UI.
 *  - data-route-group attribute is load-bearing — App.coverage.test.tsx queries
 *    it to confirm the right wrapper caught a thrown component.
 *
 * Note: We do NOT mock @sentry/react here (unlike ErrorBoundary.test.tsx).
 *   The real Sentry.ErrorBoundary runs cleanly under jsdom; mocking it would
 *   defeat the purpose of asserting eventId surfaces in the fallback render.
 *   PATTERNS.md §Wave 0 RouteGroupBoundary.test.tsx documents this deviation.
 */

function Thrower(): ReactNode {
  throw new Error('kaboom');
}

function Safe(): ReactNode {
  return <div>safe content</div>;
}

describe('RouteGroupBoundary', () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs the thrown error to console.error via its error-boundary
    // machinery; silence it so passing tests do not look noisy.
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it('renders children when no error is thrown', () => {
    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="admin">
          <Safe />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText('safe content')).toBeInTheDocument();
    expect(document.querySelector('[data-route-group]')).toBeNull();
  });

  it('renders the fallback with event ID when a child throws', () => {
    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="builder">
          <Thrower />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    const section = document.querySelector('[data-route-group="builder"]');
    expect(section).not.toBeNull();
    expect(
      screen.getByText(/something went wrong in the builder section/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/kaboom/)).toBeInTheDocument();
    expect(screen.getByText(/event id:/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /go home/i })
    ).toBeInTheDocument();
  });

  it('Retry button calls resetError and re-renders non-throwing children', () => {
    // Stateful Thrower that can be flipped to non-throwing — proves Retry
    // actually resets the boundary (without the flip, resetError would just
    // re-throw the same error and the fallback would re-render).
    let shouldThrow = true;
    function ConditionalThrower(): ReactNode {
      if (shouldThrow) throw new Error('boom');
      return <div>recovered</div>;
    }

    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="public">
          <ConditionalThrower />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    expect(
      document.querySelector('[data-route-group="public"]')
    ).not.toBeNull();

    shouldThrow = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(screen.getByText('recovered')).toBeInTheDocument();
  });
});
