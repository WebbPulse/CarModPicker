/**
 * Passwordless sign in with a passkey, giving the login page one shape to
 * render above `AuthClient`'s outcome union. The ceremony itself runs in
 * `usePasskeySignInButton`; enrolment, rename and delete live in
 * `usePasskeyPanel`. Bearer mode keeps its own `@simplewebauthn/browser` path
 * in `./auth`.
 */
import type { Passkey, PasskeySignInOutcome } from '@webbpulse/auth';

export type { Passkey };

/** What a passwordless sign in produced. */
export type PasskeySignInResult =
  | { status: 'authenticated' }
  | { status: 'mfa-required'; ticket: string; factors: string[] }
  | { status: 'cancelled' }
  | { status: 'failed'; error: string };

/**
 * Narrows the client's outcome union to the shape the login page renders. An
 * `mfa-required` outcome is ordinary for an account with TOTP on, and its
 * ticket goes to the usual `completeMfa`.
 */
export const toPasskeySignInResult = (
  outcome: PasskeySignInOutcome
): PasskeySignInResult => {
  if (outcome.ok) {
    if (outcome.kind === 'mfa-required') {
      return {
        status: 'mfa-required',
        ticket: outcome.ticket,
        factors: outcome.factors,
      };
    }
    return { status: 'authenticated' };
  }
  if (outcome.reason === 'cancelled') return { status: 'cancelled' };
  return { status: 'failed', error: outcome.message };
};

/**
 * A ceremony that threw rather than settled, which the client reserves for a
 * network failure or a server error it could not turn into an outcome.
 */
export const passkeySignInFailure = (error: unknown): PasskeySignInResult => ({
  status: 'failed',
  error: error instanceof Error ? error.message : 'Passkey sign in failed.',
});
