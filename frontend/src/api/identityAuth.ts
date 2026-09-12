/**
 * Sign in and sign out in the shape the pages render, over `AuthClient` since
 * row 13 removed the legacy mechanism. An MFA challenge is a successful outcome
 * here rather than a thrown error, and a null client is a refusal to show.
 */
import { describeAuthError, getAuthErrorCode } from '@webbpulse/auth';
import { apiClient } from './client';
import { getIdentityClient } from './identityClient';
import { getApiErrorMessage } from '../utils/apiError';
import type { UserRead } from '../types/Api';

/** Shown when the identity client could not be built. One wording, one cause. */
const CLIENT_UNAVAILABLE = 'Sign in is unavailable in this deployment.';

/**
 * What the second leg of a sign in needs. The `kind` discriminator is kept so a
 * second challenge type can be added without every construction site becoming
 * ambiguous.
 */
export type LoginChallenge = {
  kind: 'identity-ticket';
  ticket: string;
  factors: string[];
};

/** What a sign in attempt produced. */
export type LoginResult =
  | { status: 'authenticated'; user: UserRead | null }
  | { status: 'mfa-required'; challenge: LoginChallenge }
  | { status: 'failed'; error: string };

/**
 * True when the code field should also accept a recovery code. A function, not
 * an inlined `true`, so a deployment that answers differently changes one place.
 */
export const acceptsRecoveryCodes = (): boolean => true;

/**
 * Runs the first leg of a sign in. Returns no user, so the caller follows a
 * success with `checkAuthStatus()`.
 */
export const signIn = async (
  username: string,
  password: string
): Promise<LoginResult> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { status: 'failed', error: CLIENT_UNAVAILABLE };
  }
  try {
    const outcome = await identity.login({ email: username, password });
    if (outcome.mfaRequired) {
      return {
        status: 'mfa-required',
        challenge: {
          kind: 'identity-ticket',
          ticket: outcome.ticket,
          factors: outcome.factors,
        },
      };
    }
    return { status: 'authenticated', user: null };
  } catch (error) {
    return { status: 'failed', error: describeIdentityFailure(error) };
  }
};

/**
 * Runs the second leg with a TOTP code or a recovery code. The server tells the
 * two apart, so the form needs one field rather than a choice.
 */
export const completeMfa = async (
  challenge: LoginChallenge,
  code: string
): Promise<LoginResult> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { status: 'failed', error: 'Two factor sign in is unavailable.' };
  }
  try {
    const outcome = await identity.completeTotp({
      ticket: challenge.ticket,
      code,
    });
    if (outcome.mfaRequired) {
      return { status: 'failed', error: 'That code was not accepted.' };
    }
    return { status: 'authenticated', user: null };
  } catch (error) {
    return { status: 'failed', error: describeIdentityFailure(error) };
  }
};

/**
 * Ends the session. A server call, since the httpOnly refresh cookie is what
 * holds it; a null client resolves rather than refusing.
 */
export const signOut = async (): Promise<void> => {
  const identity = getIdentityClient();
  if (identity === null) return;
  await identity.logout();
};

/**
 * Spends the refresh cookie for an access token at startup. Resolves false
 * rather than throwing, since arriving signed out is normal.
 */
export const restoreSession = async (): Promise<boolean> => {
  const identity = getIdentityClient();
  if (identity === null) return false;
  try {
    await identity.initialize();
    return identity.getAccessToken() !== null;
  } catch {
    return false;
  }
};

/**
 * Turns a thrown identity error into a sentence for a form. The two named codes
 * are the ones whose server wording is deliberately vague.
 */
export const describeIdentityFailure = (error: unknown): string => {
  switch (getAuthErrorCode(error)) {
    case 'INVALID_CREDENTIALS':
      return 'Incorrect email or password.';
    case 'EMAIL_NOT_VERIFIED':
      return 'Verify your email address before signing in.';
    default:
      return describeAuthError(error, 'Sign in failed. Please try again.');
  }
};

/**
 * Requests a verification email. Answers identically whether or not the address
 * has an account, so the caller gets no way to tell.
 */
export const requestVerificationEmail = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { ok: false, message: CLIENT_UNAVAILABLE };
  }
  const outcome = await identity.requestEmailVerification({ email });
  return outcome.ok
    ? { ok: true, message: outcome.detail ?? 'Verification email sent.' }
    : { ok: false, message: outcome.message };
};

/**
 * Requests a password reset email. The mail points at `RESET_PASSWORD_PATH`,
 * and the answer is identical whether or not the address has an account.
 */
export const requestPasswordReset = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { ok: false, message: CLIENT_UNAVAILABLE };
  }
  const outcome = await identity.requestPasswordReset({ email });
  return outcome.ok
    ? {
        ok: true,
        message:
          outcome.detail ??
          'If an account with that email exists, a password reset link has been sent.',
      }
    : { ok: false, message: outcome.message };
};

/** What a registration attempt produced. */
export type RegisterResult =
  { status: 'registered' } | { status: 'failed'; error: string };

/**
 * Registers an account through the identity service, which creates the
 * credential and, through this product's `create_user` hook, the users-domain
 * profile row in the same call. `attributes` carries the product fields the
 * hook reads; `username` is the only one CarModPicker sets.
 */
export const register = async (
  username: string,
  email: string,
  password: string
): Promise<RegisterResult> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { status: 'failed', error: CLIENT_UNAVAILABLE };
  }
  try {
    await identity.register({ email, password, attributes: { username } });
    return { status: 'registered' };
  } catch (error) {
    return { status: 'failed', error: describeRegistrationFailure(error) };
  }
};

/**
 * Turns a thrown registration error into a sentence for a form. A taken address
 * is answered identically to a fresh one by design, so it never reaches here.
 */
export const describeRegistrationFailure = (error: unknown): string => {
  switch (getAuthErrorCode(error)) {
    case 'PASSWORD_TOO_SHORT':
    case 'PASSWORD_TOO_LONG':
    case 'PASSWORD_REJECTED':
    case 'WEAK_PASSWORD':
      return describeAuthError(error, 'Choose a stronger password.');
    default:
      return describeAuthError(
        error,
        'Could not create the account. Please try again.'
      );
  }
};

/** What a password change produced. */
export type PasswordChangeResult =
  { status: 'changed' } | { status: 'failed'; error: string };

/**
 * Changes the signed-in account's password through the identity service, which
 * owns the credential. Posted over `apiClient` rather than `AuthClient`, which
 * exposes no method for this route; the shared client already carries the
 * access token and refreshes it, so the subject comes from the verified claims.
 */
export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<PasswordChangeResult> => {
  try {
    await apiClient.post('/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return { status: 'changed' };
  } catch (error) {
    return {
      status: 'failed',
      error: getApiErrorMessage(error, 'Failed to change password'),
    };
  }
};
