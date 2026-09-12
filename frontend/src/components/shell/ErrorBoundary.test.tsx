import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

/**
 * Covers ErrorBoundary: the styled fallback replaces the children tree on a
 * throw and the error is logged with its component stack.
 */

import ErrorBoundary from './ErrorBoundary';

function Thrower(): ReactNode {
  throw new Error('boom');
}

function Safe(): ReactNode {
  return <div>all good</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error is thrown', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Safe />
      </ErrorBoundary>
    );

    expect(screen.getByText('all good')).toBeInTheDocument();
    expect(errorSpy).not.toHaveBeenCalled();

    errorSpy.mockRestore();
  });

  it('renders fallback UI and logs the error when a child throws', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Thrower />
      </ErrorBoundary>
    );

    const logged = errorSpy.mock.calls.find(
      (call) => call[0] === 'ErrorBoundary caught an error:'
    ) as [string, Error, { componentStack?: string | null }] | undefined;
    expect(logged).toBeDefined();
    expect(logged?.[1]).toBeInstanceOf(Error);
    expect(logged?.[1].message).toBe('boom');
    expect(typeof logged?.[2].componentStack).toBe('string');

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
