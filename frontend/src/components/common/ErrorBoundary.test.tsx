import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

/**
 * OBS-05 ErrorBoundary → Sentry.captureException assertion (D-35).
 *
 * The existing styled fallback UI MUST still render (D-35: "Keep the existing
 * class component + styled fallback UI. 3-line change. No Sentry.ErrorBoundary
 * HOC swap.") — this test co-asserts the captureException call AND that the
 * children tree was replaced with the fallback / rendered normally.
 *
 * Noise suppression: React logs "uncaught error" messages during the throw
 * test. We silence console.error for those cases so test output stays clean.
 */

// vi.mock calls are hoisted to the top of the file, so the factory can't
// close over any variable declared below. Use vi.hoisted to declare the mock
// alongside the hoisted code.
const { mockedCapture } = vi.hoisted(() => ({
  mockedCapture: vi.fn(),
}));

vi.mock('@sentry/react', () => ({
  captureException: mockedCapture,
}));

// Import AFTER the vi.mock so ErrorBoundary picks up the mocked Sentry module.
import ErrorBoundary from './ErrorBoundary';

function Thrower(): ReactNode {
  throw new Error('boom');
}

function Safe(): ReactNode {
  return <div>all good</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error is thrown and does NOT call Sentry', () => {
    mockedCapture.mockClear();
    render(
      <ErrorBoundary>
        <Safe />
      </ErrorBoundary>
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
    expect(mockedCapture).not.toHaveBeenCalled();
  });

  it('renders fallback UI and reports to Sentry when a child throws', () => {
    mockedCapture.mockClear();

    // React logs the uncaught error through console.error; silence it so the
    // test runner output doesn't look failing when the test itself passes.
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Thrower />
      </ErrorBoundary>
    );

    // Sentry.captureException called exactly once with the thrown Error plus
    // { extra: { componentStack: <string from React> } }
    expect(mockedCapture).toHaveBeenCalledTimes(1);
    const call = mockedCapture.mock.calls[0] as [Error, { extra: { componentStack: string } }];
    const [errorArg, extraArg] = call;
    expect(errorArg).toBeInstanceOf(Error);
    expect(errorArg.message).toBe('boom');
    expect(typeof extraArg.extra.componentStack).toBe('string');
    expect(extraArg).toMatchObject({
      extra: { componentStack: expect.any(String) as unknown },
    });

    // Fallback UI rendered (D-35 invariant — we kept the existing UI, not a Sentry HOC).
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
