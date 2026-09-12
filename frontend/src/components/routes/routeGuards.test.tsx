/**
 * The three session guards read `{ isAuthenticated, isLoading }` (and `user`),
 * so adopting the `@webbpulse/auth` provider should leave them untouched. These
 * tests mount them unchanged over the real store to hold that.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
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

function mountGuard(
  guard: ReactNode,
  session: { status: AuthStatus; user?: UserRead | null },
  initialPath = '/private'
) {
  const { Wrapper } = authHarness(session);
  return render(
    <Wrapper>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={guard}>
            <Route path="/private" element={<div>private</div>} />
            <Route path="/guest" element={<div>guest</div>} />
          </Route>
          <Route path="/login" element={<div>login page</div>} />
          <Route path="/verify-email" element={<div>verify page</div>} />
          <Route path="/" element={<div>home</div>} />
        </Routes>
      </MemoryRouter>
    </Wrapper>
  );
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

  it('renders a spinner while a session call is in flight', () => {
    mountGuard(<GuestRoute />, { status: 'loading' }, '/guest');
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
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
});
