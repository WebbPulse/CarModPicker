/**
 * OAuth sign in and account link operations in identity mode. A start must be a
 * real navigation rather than a fetch, since it redirects cross-origin to the
 * provider; the backend callback returns with a marker query parameter.
 */
import {
  describeOAuthCallbackError,
  readOAuthCallback,
  stripOAuthParams,
  type OAuthCallbackResult,
  type OAuthLink,
} from '@webbpulse/auth';
import { getIdentityClient } from './identityClient';

export { describeOAuthCallbackError, readOAuthCallback, stripOAuthParams };
export type { OAuthCallbackResult, OAuthLink };

/** What an unlink produced, in the one shape the panel renders. */
export type OAuthLinkResult =
  { status: 'ok' } | { status: 'failed'; error: string };

/**
 * What a link start produced. The success carries the provider's authorization
 * URL, because starting a link only begins when the caller navigates to it.
 */
export type OAuthLinkStartResult =
  | { status: 'ok'; authorizationUrl: string }
  | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Connected accounts are not available in this deployment.';

/** The sentence shown when the server accepted the start but named no URL. */
const NO_AUTHORIZATION_URL =
  'Could not start that connection. Please try again.';

/**
 * The URL a "Continue with X" button points at, or null in bearer mode.
 * `returnTo` is a path the server resolves against its own frontend base.
 */
export const oauthStartUrl = (
  provider: string,
  returnTo?: string
): string | null => {
  const identity = getIdentityClient();
  if (identity === null) return null;
  return identity.oauthStartUrl(provider, {
    mode: 'login',
    ...(returnTo === undefined ? {} : { returnTo }),
  });
};

/**
 * Starts attaching a provider to the signed in account. The route answers with
 * JSON rather than a redirect, since it is called with an `Authorization`
 * header a redirect would drop, so the caller has to navigate to the returned
 * URL for anything to happen. A refusal carries the server's wording.
 */
export const linkProvider = async (
  provider: string,
  returnTo?: string
): Promise<OAuthLinkStartResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.linkOAuthProvider(provider, {
      ...(returnTo === undefined ? {} : { returnTo }),
    });
    if (!outcome.ok) {
      return { status: 'failed', error: outcome.message };
    }
    if (outcome.authorizationUrl === '') {
      return { status: 'failed', error: NO_AUTHORIZATION_URL };
    }
    return { status: 'ok', authorizationUrl: outcome.authorizationUrl };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not connect that account.',
    };
  }
};

/**
 * Starts a link and leaves the page for the provider. Returns only when the
 * start was refused, since a success is a navigation away from here.
 */
export const startProviderLink = async (
  provider: string,
  returnTo?: string
): Promise<OAuthLinkStartResult> => {
  const result = await linkProvider(provider, returnTo);
  if (result.status === 'ok') {
    globalThis.location.assign(result.authorizationUrl);
  }
  return result;
};

/** The providers attached to the signed in account. */
export const listLinks = async (): Promise<
  { status: 'ok'; links: OAuthLink[] } | { status: 'failed'; error: string }
> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.listOAuthLinks();
    return outcome.ok
      ? { status: 'ok', links: outcome.links }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not load your connected accounts.',
    };
  }
};

/**
 * Detaches a provider from the signed in account. Refused when it is the last
 * way in, carrying the server's own explanation of what to do first.
 */
export const unlinkProvider = async (
  provider: string
): Promise<OAuthLinkResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.unlinkOAuthProvider(provider);
    return outcome.ok
      ? { status: 'ok' }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not disconnect that account.',
    };
  }
};
