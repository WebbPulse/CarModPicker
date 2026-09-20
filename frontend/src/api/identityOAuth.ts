/**
 * The OAuth callback readers for identity mode. The start URL a "Continue with
 * X" button navigates to comes from `useOAuthProviderLinks`; the backend
 * callback returns with a marker query parameter, read here. Account linking
 * lives in `useConnectedAccountsPanel`.
 */
import {
  describeOAuthCallbackError,
  readOAuthCallback,
  stripOAuthParams,
  type OAuthCallbackResult,
  type OAuthLink,
} from '@webbpulse/auth';

export { describeOAuthCallbackError, readOAuthCallback, stripOAuthParams };
export type { OAuthCallbackResult, OAuthLink };
