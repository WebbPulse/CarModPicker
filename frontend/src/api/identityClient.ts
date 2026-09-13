/**
 * Builds the `@webbpulse/auth` client, lazily. Kept out of `./client` so the
 * ninety modules importing that do not construct a network-capable object at
 * import time.
 */
import {
  createAuthClient,
  type AuthClient,
  type WebAuthnAdapter,
} from '@webbpulse/auth';
import type { UserRead } from '../types/Api';
import {
  identityOriginFrom,
  identityUrl as joinIdentityUrl,
} from '@webbpulse/discovery';
import { appConfig } from '../config/app';

export {
  OAUTH_PROVIDERS_PATH,
  PASSKEY_AVAILABILITY_PATH,
  identityOriginFrom,
  oauthProviders,
  passkeyEnrolmentAvailability,
  passkeyLoginAvailability,
  providerLabel,
  resetAvailabilityCache,
  type Availability,
  type OAuthProviderInfo,
  type PasskeyCapabilities,
} from '@webbpulse/discovery';

/**
 * Prefixes the identity origin onto an already absolute route path, for the
 * discovery gates that fetch directly instead of through `AuthClient`.
 */
export const identityUrl = (path: string): string =>
  joinIdentityUrl(identityOriginFrom(appConfig.apiBaseUrl), path);

/**
 * Where the signed in profile is read from, in the users domain. Carries the
 * `/api` prefix because `identityOriginFrom` strips the configured base URL back
 * to a bare origin, the same way the package's own `/api/auth/...` routes do.
 */
export const CURRENT_USER_PATH = '/api/users/me';

/**
 * The one instance, or null when it could not be built. Built on first request
 * so that importing this module stays free.
 */
let client: AuthClient<UserRead> | null = null;
let built = false;

/**
 * Test seam for the WebAuthn surface, since `AuthClient` fixes the adapter at
 * construction. Null in every real bundle, leaving the package default.
 */
let webAuthnAdapter: WebAuthnAdapter | null = null;

/**
 * Installs a WebAuthn stub for the passkey tests. Tests only, and must run
 * before the first `getIdentityClient()`.
 */
export const setWebAuthnAdapterForTests = (
  adapter: WebAuthnAdapter | null
): void => {
  webAuthnAdapter = adapter;
};

/**
 * The identity client, or null when it could not be built. Null rather than a
 * throw so a panel can render its own unavailable state from the same code path.
 */
export const getIdentityClient = (): AuthClient<UserRead> | null => {
  if (built) return client;
  built = true;
  const origin = identityOriginFrom(appConfig.apiBaseUrl);
  client = createAuthClient<UserRead>({
    baseUrl: origin === '' ? globalThis.location.origin : origin,
    loadUser: (apiClient) =>
      apiClient
        .get<UserRead>(CURRENT_USER_PATH)
        .then((response) => response.data ?? null),
    clientOptions: {
      credentials: 'include',
      timeoutMs: 30000,
    },
    ...(webAuthnAdapter === null ? {} : { webAuthn: webAuthnAdapter }),
  });
  return client;
};

/**
 * Drops the cached instance. Tests only, and exported rather than done with
 * `vi.resetModules`, which would also drop `./client`'s shared client.
 */
export const resetIdentityClientForTests = (): void => {
  client?.dispose();
  client = null;
  built = false;
  webAuthnAdapter = null;
};
