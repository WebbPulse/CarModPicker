/**
 * Builds the `@webbpulse/auth` client, lazily. Kept out of `./client` so the
 * ninety modules importing that do not construct a network-capable object at
 * import time. The singleton itself is the package's; this module is
 * CarModPicker's settings plus the names the rest of `src` imports.
 */
import type { AuthClient } from '@webbpulse/auth';
import {
  DEFAULT_CURRENT_USER_PATH,
  createIdentityClientSingleton,
} from '@webbpulse/auth/browser';
import type { UserRead } from '../types/Api';
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
 * Where the signed in profile is read from, in the users domain. Carries the
 * `/api` prefix because the configured base URL is stripped back to a bare
 * origin, the same way the package's own `/api/auth/...` routes are.
 */
export const CURRENT_USER_PATH = DEFAULT_CURRENT_USER_PATH;

/** The identity client as the panels take it, with the user type applied. */
export type IdentityClient = AuthClient<UserRead>;

const identity = createIdentityClientSingleton<UserRead>({
  apiBaseUrl: () => appConfig.apiBaseUrl,
  currentUserPath: CURRENT_USER_PATH,
});

/**
 * The identity client, or null when it could not be built. Null rather than a
 * throw so a panel can render its own unavailable state from the same code path.
 */
export const getIdentityClient = identity.getClient;

/**
 * The origin the identity routes are mounted on, for the hooks that take the
 * origin rather than a built URL.
 */
export const identityOrigin = identity.identityOrigin;

/**
 * Prefixes the identity origin onto an already absolute route path, for the
 * discovery gates that fetch directly instead of through `AuthClient`.
 */
export const identityUrl = identity.identityUrl;

/** Installs a WebAuthn stub for the passkey tests, before the first build. */
export const setWebAuthnAdapterForTests = identity.setWebAuthnAdapterForTests;

/** Drops the cached instance. Tests only. */
export const resetIdentityClientForTests = identity.resetForTests;
