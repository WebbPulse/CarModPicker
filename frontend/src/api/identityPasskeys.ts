/**
 * Passwordless sign in with a passkey, giving the login page one shape to
 * render above `AuthClient`'s outcome union. Enrolment, rename and delete live
 * in `usePasskeyPanel`. Bearer mode keeps its own `@simplewebauthn/browser`
 * path in `./auth`.
 */
import { isPasskeyCancellation, type Passkey } from '@webbpulse/auth';
import { getIdentityClient } from './identityClient';

export type { Passkey };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Passkeys are not available in this deployment.';

/** What a passwordless sign in produced. */
export type PasskeySignInResult =
  | { status: 'authenticated' }
  | { status: 'mfa-required'; ticket: string; factors: string[] }
  | { status: 'cancelled' }
  | { status: 'failed'; error: string };

/**
 * Signs in with a passkey and no password. `mediation` is passed through so the
 * page can request `conditional` autofill. An `mfa-required` outcome is ordinary
 * for an account with TOTP on, and its ticket goes to the usual `completeMfa`.
 */
export const signInWithPasskey = async (
  input: {
    username?: string;
    mediation?: 'silent' | 'optional' | 'conditional' | 'required';
    signal?: AbortSignal;
  } = {}
): Promise<PasskeySignInResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.signInWithPasskey({
      ...(input.username === undefined || input.username.trim() === ''
        ? {}
        : { email: input.username.trim() }),
      ...(input.mediation === undefined ? {} : { mediation: input.mediation }),
      ...(input.signal === undefined ? {} : { signal: input.signal }),
    });
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
    if ('reason' in outcome && outcome.reason === 'cancelled') {
      return { status: 'cancelled' };
    }
    return { status: 'failed', error: outcome.message };
  } catch (error) {
    if (isPasskeyCancellation(error)) return { status: 'cancelled' };
    return {
      status: 'failed',
      error: error instanceof Error ? error.message : 'Passkey sign in failed.',
    };
  }
};
