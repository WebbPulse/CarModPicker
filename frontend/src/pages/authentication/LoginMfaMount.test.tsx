/**
 * The regression this file exists for: an account with TOTP enabled never saw
 * the second step. `@webbpulse/auth` moves its store to `loading` for the whole
 * of a token call, GuestRoute rendered a spinner for that, and the unmounted
 * Login page came back with no challenge. The sign in below flips the session
 * to `loading` while `signIn` is in flight, exactly as the real client does.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { authHarness } from '../../test/utils/authHarness';
import type { StubAuthClient } from '../../test/utils/authHarness';
import GuestRoute from '../../components/routes/GuestRoute';

const navigate = vi.fn();

/** The stub the running test drives, set when its tree is mounted. */
let stub: StubAuthClient;

/**
 * Mirrors the package client: the store goes to `loading` for the duration of
 * the call and back to `anonymous` when the answer is an MFA challenge.
 */
const signIn = vi.fn(async () => {
  stub.setState({ status: 'loading' });
  await Promise.resolve();
  stub.setState({ status: 'anonymous' });
  return {
    status: 'mfa-required',
    challenge: { kind: 'identity-ticket', ticket: 'tick-1', factors: ['totp'] },
  };
});

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('../../api/identityAuth', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityAuth')>();
  return {
    ...actual,
    signIn: (...args: unknown[]) => signIn(...(args as [])),
    acceptsRecoveryCodes: () => true,
  };
});

vi.mock('../../api/identityClient', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityClient')>();
  return {
    ...actual,
    getIdentityClient: () => ({
      oauthStartUrl: () => 'https://api.test/start',
    }),
    identityUrl: (path: string) => `https://api.test${path}`,
    passkeyLoginAvailability: () => Promise.resolve('unavailable'),
    oauthProviders: () => Promise.resolve([]),
  };
});

vi.mock('../../api/identityPasskeys', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityPasskeys')>();
  return {
    ...actual,
    passkeysSupported: () => false,
    signInWithPasskey: () => new Promise(() => {}),
  };
});

/** Mounts Login behind the real GuestRoute, over the real session store. */
const renderGuardedLogin = async () => {
  const harness = authHarness({ status: 'anonymous' });
  stub = harness.stub;
  const { default: Login } = await import('./Login');
  return render(
    <harness.Wrapper>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<GuestRoute />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route path="/" element={<div>home</div>} />
        </Routes>
      </MemoryRouter>
    </harness.Wrapper>
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  globalThis.history.replaceState(null, '', '/login');
});

afterEach(() => {
  globalThis.history.replaceState(null, '', '/');
});

describe('a sign in that needs a second factor', () => {
  it('shows the TOTP step even though the session passed through loading', async () => {
    await renderGuardedLogin();

    fireEvent.change(
      screen.getByPlaceholderText(/enter your username or email/i),
      { target: { value: 'me' } }
    );
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'pw' },
    });
    fireEvent.submit(
      screen
        .getByPlaceholderText(/enter your username or email/i)
        .closest('form')!
    );

    await waitFor(() => {
      expect(screen.getByText(/two-factor authentication/i)).toBeTruthy();
    });
    expect(screen.getByLabelText(/authentication code/i)).toBeTruthy();
    expect(signIn).toHaveBeenCalledTimes(1);
  });
});
