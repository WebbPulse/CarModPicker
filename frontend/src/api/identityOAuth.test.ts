/**
 * Tests for the identity mode OAuth start URL, which a "Continue with X" button
 * navigates to rather than fetching, since it redirects cross-origin.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Stub = Record<string, ReturnType<typeof vi.fn>>;

/** Loads the module with `getIdentityClient` returning `stub`, or null. */
const loadWith = async (stub: Stub | null) => {
  vi.resetModules();
  vi.doMock('./identityClient', () => ({
    getIdentityClient: () => stub,
    identityUrl: (path: string) => `https://api.test${path}`,
  }));
  return import('./identityOAuth');
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.resetModules();
});

describe('oauthStartUrl', () => {
  it('asks the client for a login mode start URL', async () => {
    const stub = vi
      .fn()
      .mockReturnValue('https://api.test/api/auth/oauth/google/start');
    const { oauthStartUrl } = await loadWith({ oauthStartUrl: stub });

    expect(oauthStartUrl('google', '/profile')).toBe(
      'https://api.test/api/auth/oauth/google/start'
    );
    expect(stub).toHaveBeenCalledWith('google', {
      mode: 'login',
      returnTo: '/profile',
    });
  });

  it('omits returnTo when the caller named none', async () => {
    const stub = vi.fn().mockReturnValue('https://api.test/start');
    const { oauthStartUrl } = await loadWith({ oauthStartUrl: stub });

    oauthStartUrl('github');

    expect(stub).toHaveBeenCalledWith('github', { mode: 'login' });
  });

  it('is null in bearer mode', async () => {
    const { oauthStartUrl } = await loadWith(null);
    expect(oauthStartUrl('google')).toBeNull();
  });
});
