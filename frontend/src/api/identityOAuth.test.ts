/**
 * Tests for identity mode OAuth link starts, which answer with JSON rather than
 * a redirect and so only begin when the caller navigates.
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

let assign: ReturnType<typeof vi.fn<(url: string | URL) => void>>;

beforeEach(() => {
  vi.clearAllMocks();
  assign = vi.fn<(url: string | URL) => void>();
  vi.stubGlobal('location', {
    ...globalThis.location,
    pathname: '/profile',
    search: '',
    assign,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.doUnmock('./identityClient');
  vi.resetModules();
});

describe('linkProvider', () => {
  it('carries the authorization URL the server named', async () => {
    const linkOAuthProvider = vi.fn().mockResolvedValue({
      ok: true,
      authorizationUrl: 'https://accounts.google.test/authorize?x=1',
    });
    const { linkProvider } = await loadWith({ linkOAuthProvider });
    await expect(linkProvider('google', '/profile')).resolves.toEqual({
      status: 'ok',
      authorizationUrl: 'https://accounts.google.test/authorize?x=1',
    });
    expect(linkOAuthProvider).toHaveBeenCalledWith('google', {
      returnTo: '/profile',
    });
  });

  it('fails when the start was accepted but named no URL', async () => {
    const linkOAuthProvider = vi
      .fn()
      .mockResolvedValue({ ok: true, authorizationUrl: '' });
    const { linkProvider } = await loadWith({ linkOAuthProvider });
    const result = await linkProvider('github');
    expect(result.status).toBe('failed');
  });

  it("passes the server's refusal wording through", async () => {
    const linkOAuthProvider = vi
      .fn()
      .mockResolvedValue({ ok: false, message: 'Already connected.' });
    const { linkProvider } = await loadWith({ linkOAuthProvider });
    await expect(linkProvider('github')).resolves.toEqual({
      status: 'failed',
      error: 'Already connected.',
    });
  });

  it('reports the unavailable deployment rather than throwing', async () => {
    const { linkProvider } = await loadWith(null);
    const result = await linkProvider('google');
    expect(result.status).toBe('failed');
    expect(assign).not.toHaveBeenCalled();
  });
});

describe('startProviderLink', () => {
  it('navigates to the provider on a successful start', async () => {
    const linkOAuthProvider = vi.fn().mockResolvedValue({
      ok: true,
      authorizationUrl: 'https://github.test/login/oauth/authorize',
    });
    const { startProviderLink } = await loadWith({ linkOAuthProvider });
    await startProviderLink('github', '/profile');
    expect(assign).toHaveBeenCalledWith(
      'https://github.test/login/oauth/authorize'
    );
  });

  it('stays on the page and reports a refusal', async () => {
    const linkOAuthProvider = vi
      .fn()
      .mockResolvedValue({ ok: false, message: 'Provider is off.' });
    const { startProviderLink } = await loadWith({ linkOAuthProvider });
    await expect(startProviderLink('github')).resolves.toEqual({
      status: 'failed',
      error: 'Provider is off.',
    });
    expect(assign).not.toHaveBeenCalled();
  });
});
