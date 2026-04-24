// Phase 8 plan 08-14 (D-11) — Checkout page authenticated-render test.
//
// Checkout has no auth gate — it relies on `useAuth().user` to show the
// "billed to" email row. Cover: auth render (order summary + disabled
// subscribe CTA), email visible in billed-to row, back-to-pricing link.
//
// NOTE: bypasses test-utils.tsx's customRender for the same reason as
// Pricing.test.tsx (createMockUser returns incomplete UserRead).

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Checkout from './Checkout';

describe('Checkout page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the Go Premium heading, order summary, and disabled subscribe CTA', () => {
    render(
      <BrowserRouter>
        <Checkout />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /go premium/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /order summary/i })
    ).toBeInTheDocument();
    const subscribeBtn = screen.getByRole('button', { name: /subscribe for/i });
    expect(subscribeBtn).toBeDisabled();
  });

  it('displays the authenticated user\'s email in the "billed to" row', () => {
    render(
      <BrowserRouter>
        <Checkout />
      </BrowserRouter>
    );
    // mockUser.email is 'test@example.com'.
    expect(screen.getByText(/test@example\.com/i)).toBeInTheDocument();
  });

  it('links back to /pricing via the back-arrow', () => {
    render(
      <BrowserRouter>
        <Checkout />
      </BrowserRouter>
    );
    const backLink = screen.getByRole('link', { name: /back to pricing/i });
    expect(backLink).toHaveAttribute('href', '/pricing');
  });
});
