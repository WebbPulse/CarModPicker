/**
 * The OAuth sign in start URL and the callback readers for identity mode. A
 * start must be a real navigation rather than a fetch, since it redirects
 * cross-origin to the provider; the backend callback returns with a marker
 * query parameter. Account linking lives in `useConnectedAccountsPanel`.
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
