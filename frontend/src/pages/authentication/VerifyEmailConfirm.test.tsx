// Phase 8 Plan 10 (D-11 Wave 3) — VerifyEmailConfirm page coverage.
//
// Renders backend-driven verification outcomes from URL params:
//   - ?status=success&message=... → ConfirmationAlert
//   - ?status=error&message=...   → ErrorAlert
//   - (no status)                 → "Invalid or missing verification link"
//
// The page does NOT call the API — it just displays whatever the backend's
// redirect encoded in the query string. Mirrors the VerifyEmailConfirm.tsx
// source exactly (useEffect reads searchParams, sets state, render branches).
import { describe, it, expect } from 'vitest';
import { render, screen, testScenarios } from '../../test/utils/test-utils';
import VerifyEmailConfirm from './VerifyEmailConfirm';

describe('VerifyEmailConfirm page', () => {
  it('shows the success message when ?status=success is set via token=abc path', () => {
    // Backend redirects here with ?status=success&message=...; we simulate
    // by seeding a token=abc route alongside the status param.
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route:
        '/verify-email/confirm?token=abc&status=success&message=Email+verified',
    });
    expect(
      screen.getByText(/email verification result/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/email verified/i)).toBeInTheDocument();
  });

  it('shows the error message when ?status=error is set with a token in the URL', () => {
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route:
        '/verify-email/confirm?token=abc&status=error&message=Token+expired',
    });
    expect(screen.getByText(/token expired/i)).toBeInTheDocument();
  });

  it('shows the invalid-link fallback when no status param is provided', () => {
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route: '/verify-email/confirm',
    });
    expect(
      screen.getByText(
        /invalid or missing verification link|request a new verification email/i
      )
    ).toBeInTheDocument();
    // The fallback renders a "Verification Email" link to request a new one.
    expect(
      screen.getByRole('link', { name: /verification email/i })
    ).toBeInTheDocument();
  });
});
