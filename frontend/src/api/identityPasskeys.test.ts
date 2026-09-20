/**
 * Tests for the shape identity mode passwordless sign in hands the login page.
 */

import { describe, expect, it } from 'vitest';
import type { PasskeySignInOutcome } from '@webbpulse/auth';
import {
  passkeySignInFailure,
  toPasskeySignInResult,
} from './identityPasskeys';

/** An outcome as the client would settle it, with the fields a test cares about. */
const outcome = (value: Record<string, unknown>): PasskeySignInOutcome =>
  value as unknown as PasskeySignInOutcome;

describe('toPasskeySignInResult', () => {
  it('reports a completed sign in', () => {
    expect(
      toPasskeySignInResult(outcome({ ok: true, kind: 'signed-in' }))
    ).toEqual({ status: 'authenticated' });
  });

  it('carries an MFA ticket through to the second leg', () => {
    expect(
      toPasskeySignInResult(
        outcome({
          ok: true,
          kind: 'mfa-required',
          ticket: 'tick-1',
          factors: ['totp'],
        })
      )
    ).toEqual({ status: 'mfa-required', ticket: 'tick-1', factors: ['totp'] });
  });

  it('reports a cancellation as cancelled', () => {
    expect(
      toPasskeySignInResult(
        outcome({ ok: false, reason: 'cancelled', message: 'x' })
      )
    ).toEqual({ status: 'cancelled' });
  });

  it('reports a refusal with the server sentence', () => {
    expect(
      toPasskeySignInResult(
        outcome({
          ok: false,
          reason: 'rejected',
          message: 'That passkey is not registered.',
        })
      )
    ).toEqual({ status: 'failed', error: 'That passkey is not registered.' });
  });
});

describe('passkeySignInFailure', () => {
  it('reports a thrown error as a failure with its message', () => {
    expect(passkeySignInFailure(new Error('network down'))).toEqual({
      status: 'failed',
      error: 'network down',
    });
  });

  it('falls back to a fixed sentence when the throw was not an Error', () => {
    expect(passkeySignInFailure('boom')).toEqual({
      status: 'failed',
      error: 'Passkey sign in failed.',
    });
  });
});
