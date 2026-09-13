/**
 * The three session guards read `{ isAuthenticated, isLoading }` (and `user`,
 * and `isBusy` in GuestRoute) from the `@webbpulse/auth` store. `isLoading` is
 * true only until the session first settles, so it gates the spinner, and
 * `isAuthenticated` holds through an in-flight call on a live session, so the
 * redirect does not fire on the loading status a token call passes through.
 * These tests mount the guards over the real store to hold both halves.
 */

import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { useState, type ReactNode } from 'react';
import type { AuthStatus } from '@webbpulse/auth';
import EmailVerifiedRoute from './EmailVerifiedRoute';
import GuestRoute from './GuestRoute';
import ProtectedRoute from './ProtectedRoute';
import { authHarness } from '../../test/utils/authHarness';
import { mockUser } from '../../test/mocks/api';
import type { UserRead } from '../../types/Api';

vi.mock('../ui/spinner', () => ({
  default: () => <div data-testid="spinner">loading</div>,
}));

/**
 * A child that stamps a fresh number into state on every mount, so a test can
 * tell a surviving element from a remounted replacement.
 */
function MountCounter({ label }: { label: string }) {
  const [instance] = useState(() => {
    mountCount += 1;
    return mountCount;
  });
  return (
    <div data-testid="counted" data-instance={instance}>
      {label}
    </div>
  );
}

let mountCount = 0;

function mountGuard(
  guard: ReactNode,
  session: { status: AuthStatus; user?: UserRead | null },
  initialPath = '/private'
) {
  const { Wrapper, stub } = authHarness(session);
  const view = render(
    <Wrapper>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={guard}>
            <Route path="/private" element={<MountCounter label="private" />} />
            <Route path="/guest" element={<MountCounter label="guest" />} />
          </Route>
          <Route path="/login" element={<div>login page</div>} />
          <Route path="/verify-email" element={<div>verify page</div>} />
          <Route path="/" element={<div>home</div>} />
        </Routes>
      </MemoryRouter>
    </Wrapper>
  );
  return { ...view, stub };
}

describe('ProtectedRoute', () => {
  it('renders a spinner until the first refresh settles', () => {
    mountGuard(<ProtectedRoute />, { status: 'unknown' });
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('renders the outlet for a signed in user', () => {
    mountGuard(<ProtectedRoute />, { status: 'authenticated', user: mockUser });
    expect(screen.getByText('private')).toBeInTheDocument();
  });

  it('redirects a signed out user to login', () => {
    mountGuard(<ProtectedRoute />, { status: 'anonymous' });
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('keeps the page mounted when a later call goes back to loading', () => {
    const { stub } = mountGuard(<ProtectedRoute />, {
      status: 'authenticated',
      user: mockUser,
    });
    const before = screen.getByTestId('counted');

    act(() => stub.setState({ status: 'loading' }));

    expect(screen.queryByTestId('spinner')).toBeNull();
    expect(screen.getByTestId('counted')).toBe(before);
  });

  it('does not redirect on the anonymous status a token call passes through', () => {
    const { stub } = mountGuard(<ProtectedRoute />, {
      status: 'authenticated',
      user: mockUser,
    });

    act(() => stub.setState({ status: 'loading' }));

    expect(screen.queryByText('login page')).toBeNull();
    expect(screen.getByTestId('counted')).toBeInTheDocument();
  });
});

describe('GuestRoute', () => {
  it('renders the outlet for a signed out user', () => {
    mountGuard(<GuestRoute />, { status: 'anonymous' }, '/guest');
    expect(screen.getByText('guest')).toBeInTheDocument();
  });

  it('redirects a signed in user home', () => {
    mountGuard(
      <GuestRoute />,
      { status: 'authenticated', user: mockUser },
      '/guest'
    );
    expect(screen.getByText('home')).toBeInTheDocument();
  });

  it('renders a spinner while the first session call is in flight', () => {
    mountGuard(<GuestRoute />, { status: 'loading' }, '/guest');
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('keeps the page mounted when a later call goes back to loading', () => {
    const { stub } = mountGuard(
      <GuestRoute />,
      { status: 'anonymous' },
      '/guest'
    );
    const before = screen.getByTestId('counted');
    const instance = before.getAttribute('data-instance');

    act(() => stub.setState({ status: 'loading' }));

    expect(screen.queryByTestId('spinner')).toBeNull();
    const after = screen.getByTestId('counted');
    expect(after).toBe(before);
    expect(after.getAttribute('data-instance')).toBe(instance);
  });

  it('still redirects a signed in user once the call settles', () => {
    const { stub } = mountGuard(
      <GuestRoute />,
      { status: 'anonymous' },
      '/guest'
    );
    act(() => stub.setState({ status: 'loading' }));
    act(() =>
      stub.setState({
        status: 'authenticated',
        user: mockUser,
        hasAccessToken: true,
      })
    );
    expect(screen.getByText('home')).toBeInTheDocument();
  });
});

describe('EmailVerifiedRoute', () => {
  it('renders the outlet for a verified user', () => {
    mountGuard(<EmailVerifiedRoute />, {
      status: 'authenticated',
      user: mockUser,
    });
    expect(screen.getByText('private')).toBeInTheDocument();
  });

  it('redirects an unverified user to the verify page', () => {
    mountGuard(<EmailVerifiedRoute />, {
      status: 'authenticated',
      user: { ...mockUser, email_verified: false },
    });
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('redirects a signed out user to login', () => {
    mountGuard(<EmailVerifiedRoute />, { status: 'anonymous' });
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('keeps the page mounted when a later call goes back to loading', () => {
    const { stub } = mountGuard(<EmailVerifiedRoute />, {
      status: 'authenticated',
      user: mockUser,
    });
    const before = screen.getByTestId('counted');

    act(() => stub.setState({ status: 'loading' }));

    expect(screen.queryByTestId('spinner')).toBeNull();
    expect(screen.getByTestId('counted')).toBe(before);
  });
});
