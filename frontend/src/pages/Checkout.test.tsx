import userEvent from '@testing-library/user-event';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockUser } from '../test/mocks/api';
import { billingError, mockPremiumUser } from '../test/mocks/billing';
import { mockUseAuth } from '../test/utils/test-mocks';
import type { UserRead } from '../types/Api';

const billingMocks = vi.hoisted(() => ({
  createCheckoutSession: vi.fn(),
  createPortalSession: vi.fn(),
  redirectToBilling: vi.fn(),
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../api/billing', () => billingMocks);

import Checkout from './Checkout';

const checkAuthStatus = vi.fn<() => Promise<void>>();

/** Sets the signed in user the page reads through useAuth. */
const setUser = (user: UserRead) => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    user,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus,
  });
};

/** Renders the checkout page at the given URL. */
const renderAt = (url = '/checkout') =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Checkout />
    </MemoryRouter>
  );

describe('Checkout page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    checkAuthStatus.mockResolvedValue(undefined);
    setUser(mockUser);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the heading, order summary, and an enabled subscribe button', () => {
    renderAt();

    expect(
      screen.getByRole('heading', { name: /go premium/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /order summary/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /subscribe for/i })
    ).toBeEnabled();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('displays the authenticated user\'s email in the "billed to" row', () => {
    renderAt();
    expect(screen.getByText(/test@example\.com/i)).toBeInTheDocument();
  });

  it('links back to /pricing via the back-arrow', () => {
    renderAt();
    const backLink = screen.getByRole('link', { name: /back to pricing/i });
    expect(backLink).toHaveAttribute('href', '/pricing');
  });

  it('starts checkout and redirects to the Stripe URL', async () => {
    let resolve: (url: string) => void = () => undefined;
    billingMocks.createCheckoutSession.mockReturnValueOnce(
      new Promise<string>((r) => {
        resolve = r;
      })
    );
    const user = userEvent.setup();
    renderAt();

    const button = screen.getByRole('button', { name: /subscribe for/i });
    await user.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');

    await act(async () => {
      resolve('https://checkout.stripe.com/c/pay/cs_test_1');
      await Promise.resolve();
    });

    expect(billingMocks.redirectToBilling).toHaveBeenCalledWith(
      'https://checkout.stripe.com/c/pay/cs_test_1'
    );
  });

  it.each([
    ['ALREADY_PREMIUM', 409, /already have an active premium/i],
    ['STRIPE_NOT_CONFIGURED', 503, /payments are not available/i],
    ['STRIPE_PRICE_MISSING', 503, /payments are not available/i],
    ['STRIPE_ERROR', 502, /could not start checkout/i],
  ])(
    'shows friendly copy for %s and re-enables the button',
    async (code, status, copy) => {
      billingMocks.createCheckoutSession.mockRejectedValueOnce(
        billingError(status, code)
      );
      const user = userEvent.setup();
      renderAt();

      await user.click(screen.getByRole('button', { name: /subscribe for/i }));

      expect(await screen.findByRole('alert')).toHaveTextContent(copy);
      expect(
        screen.getByRole('button', { name: /subscribe for/i })
      ).toBeEnabled();
      expect(billingMocks.redirectToBilling).not.toHaveBeenCalled();
    }
  );

  it('shows generic copy for a network failure', async () => {
    billingMocks.createCheckoutSession.mockRejectedValueOnce(
      new TypeError('Failed to fetch')
    );
    const user = userEvent.setup();
    renderAt();

    await user.click(screen.getByRole('button', { name: /subscribe for/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not start checkout/i
    );
  });

  it('shows the cancelled note and keeps the subscribe button', () => {
    renderAt('/checkout?status=cancelled');

    expect(
      screen.getByRole('heading', { name: /checkout cancelled/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/no charge was made/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /subscribe for/i })
    ).toBeEnabled();
  });

  it('shows the already premium card with a manage subscription button', async () => {
    setUser(mockPremiumUser);
    billingMocks.createPortalSession.mockResolvedValueOnce(
      'https://billing.stripe.com/p/session/test_1'
    );
    const user = userEvent.setup();
    renderAt();

    expect(
      screen.getByRole('heading', { name: /already premium/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /subscribe for/i })
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: /manage subscription/i })
    );

    await waitFor(() =>
      expect(billingMocks.redirectToBilling).toHaveBeenCalledWith(
        'https://billing.stripe.com/p/session/test_1'
      )
    );
  });

  it('shows an inline error when the portal session fails', async () => {
    setUser(mockPremiumUser);
    billingMocks.createPortalSession.mockRejectedValueOnce(
      billingError(409, 'NO_BILLING_ACCOUNT')
    );
    const user = userEvent.setup();
    renderAt();

    await user.click(
      screen.getByRole('button', { name: /manage subscription/i })
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not find a billing account/i
    );
  });

  it('polls the user after a successful payment until premium, then confirms', async () => {
    let refreshes = 0;
    checkAuthStatus.mockImplementation(() => {
      refreshes += 1;
      if (refreshes >= 2) setUser(mockPremiumUser);
      return Promise.resolve();
    });
    vi.useFakeTimers();
    renderAt('/checkout?status=success&session_id=cs_test_1');

    const activating = screen.getByRole('status');
    expect(
      within(activating).getByText(/payment received, activating premium/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /subscribe for/i })
    ).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(checkAuthStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/activating premium/i)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(checkAuthStatus).toHaveBeenCalledTimes(2);

    expect(
      screen.getByRole('heading', { name: /welcome to premium/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /profile/i })).toHaveAttribute(
      'href',
      '/profile'
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(checkAuthStatus).toHaveBeenCalledTimes(2);
  });

  it('stops polling after about 30 seconds and shows the delayed state', async () => {
    vi.useFakeTimers();
    renderAt('/checkout?status=success&session_id=cs_test_1');

    for (let step = 0; step < 16; step += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2500);
      });
    }

    expect(checkAuthStatus).toHaveBeenCalledTimes(12);
    expect(
      screen.getByRole('heading', { name: /still activating/i })
    ).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(checkAuthStatus).toHaveBeenCalledTimes(12);
  });

  it('confirms immediately when the user is already premium on return', () => {
    setUser(mockPremiumUser);
    renderAt('/checkout?status=success&session_id=cs_test_1');

    expect(
      screen.getByRole('heading', { name: /welcome to premium/i })
    ).toBeInTheDocument();
    expect(checkAuthStatus).not.toHaveBeenCalled();
  });
});
