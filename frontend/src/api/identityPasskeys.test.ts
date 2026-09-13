/**
 * Tests for identity mode passwordless sign in with a passkey.
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
  return import('./identityPasskeys');
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.resetModules();
});

describe('signInWithPasskey', () => {
  it('reports a completed sign in', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'authenticated',
    });
  });

  it('carries an MFA ticket through to the second leg', async () => {
    const signIn = vi.fn().mockResolvedValue({
      ok: true,
      kind: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    });
  });

  it('passes the mediation through so the page can ask for conditional', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await signInWithPasskey({ mediation: 'conditional' });
    expect(signIn).toHaveBeenCalledWith({ mediation: 'conditional' });
  });

  it('sends a username as an email when one was typed', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await signInWithPasskey({ username: '  me@example.com  ' });
    expect(signIn).toHaveBeenCalledWith({ email: 'me@example.com' });
  });

  it('reports a cancellation as cancelled', async () => {
    const signIn = vi
      .fn()
      .mockResolvedValue({ ok: false, reason: 'cancelled', message: 'x' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'cancelled',
    });
  });

  it('reports a refusal with the server sentence', async () => {
    const signIn = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'unknown-credential',
      message: 'That passkey is not registered.',
    });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'failed',
      error: 'That passkey is not registered.',
    });
  });

  it('reports a thrown error as a failure', async () => {
    const signIn = vi.fn().mockRejectedValue(new Error('network down'));
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'failed',
      error: 'network down',
    });
  });
});
