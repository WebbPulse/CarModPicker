/**
 * Which auth mechanism this bundle runs. There is only one left.
 *
 * Row 12 flipped every environment to `identity` and row 13 deleted the 24
 * routes the bearer path talked to, so `AUTH_MODE` is a constant rather than a
 * read of `import.meta.env` and `VITE_AUTH_MODE` is read by nothing.
 */

/** The one mechanism. */
export const AUTH_MODES = ['identity'] as const;

/** One of {@link AUTH_MODES}. */
export type AuthMode = (typeof AUTH_MODES)[number];

/** The mode this bundle holds for its lifetime. */
export const AUTH_MODE: AuthMode = 'identity';

/**
 * Which sign in affordances this bundle can serve at all. Whether a given
 * deployment has one switched on is a runtime question for the availability
 * modules, which is why components hide on that answer rather than on this one.
 */
export const identityAvailability = (): {
  password: boolean;
  totp: boolean;
  passkeys: boolean;
  googleOauth: boolean;
  recoveryCodes: boolean;
} => ({
  password: true,
  totp: true,
  passkeys: true,
  googleOauth: true,
  recoveryCodes: true,
});
