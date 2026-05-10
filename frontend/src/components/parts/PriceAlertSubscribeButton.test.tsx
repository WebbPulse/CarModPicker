// Component test for PriceAlertSubscribeButton (M002/S07/T04).
// Covers: anonymous→login-redirect, authenticated→listMine prefill,
// successful subscribe POST, threshold validation rejection, 422 error.
/* eslint-disable @typescript-eslint/unbound-method */
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import PriceAlertSubscribeButton from './PriceAlertSubscribeButton';
import { mockUser } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { render } from '../../test/utils/test-utils';
import type { PartPriceAlertRead } from '../../types/Api';

// testScenarios in test-utils builds its `user` from a stale createMockUser
// helper that pre-dates UserRead's subscription/2fa fields. Build matching
// scenarios here from the canonical `mockUser` so the call sites type-check
// under the project's `exactOptionalPropertyTypes: true`.
const authedScenario = {
  initialAuthState: {
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
  },
};
const anonScenario = {
  initialAuthState: {
    isAuthenticated: false,
    user: null,
    isLoading: false,
  },
};

// vi.mock is hoisted per-file, so the test-utils.tsx hook mock doesn't
// auto-apply here — declare it explicitly so PriceAlertSubscribeButton's
// useAuth() call resolves to the test-controlled mockUseAuth fn that
// TestProviders configures via initialAuthState.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Spy on useNavigate so we can assert the redirect target without actually
// pushing browser history. importOriginal preserves Link, BrowserRouter, etc.
const navigateMock = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

const PART_ID = '44444444-4444-7444-8444-444444444444';

const existingAlert: PartPriceAlertRead = {
  id: '99999999-9999-7999-8999-999999999999',
  user_id: '11111111-1111-7111-8111-111111111111',
  part_id: PART_ID,
  threshold_cents: 7500, // $75.00
  active: true,
  last_fired_at: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

beforeEach(() => {
  navigateMock.mockReset();
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('PriceAlertSubscribeButton', () => {
  it('redirects anonymous users to /login?next=/parts/:partId on click (does not open dialog)', () => {
    // Anonymous → useAuth().user is null → no listMine call should happen.
    render(
      <PriceAlertSubscribeButton
        partId={PART_ID}
        currentBestPriceCents={10000}
      />,
      anonScenario
    );

    const trigger = screen.getByTestId('price-alert-subscribe-trigger');
    fireEvent.click(trigger);

    expect(navigateMock).toHaveBeenCalledWith(`/login?next=/parts/${PART_ID}`);
    // Dialog should NOT have rendered.
    expect(
      screen.queryByTestId('price-alert-subscribe-dialog')
    ).not.toBeInTheDocument();
    // listMine should NOT have been called for an anonymous user.
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it('authenticated user with no existing alert → opens dialog prefilled to current best price → POST creates alert', async () => {
    // listMine returns empty → label stays "Notify me on price drop".
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...existingAlert, threshold_cents: 10000 },
    });

    render(
      <PriceAlertSubscribeButton
        partId={PART_ID}
        currentBestPriceCents={10000}
      />,
      authedScenario
    );

    // Wait for the listMine fetch to resolve so the effect cleanup ran.
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/part-price-alerts/me');
    });

    const trigger = screen.getByTestId('price-alert-subscribe-trigger');
    expect(trigger).toHaveTextContent('Notify me on price drop');

    fireEvent.click(trigger);

    const input = await screen.findByTestId('price-alert-threshold-input');
    expect(input).toHaveValue(100); // $100.00 prefill from currentBestPriceCents

    const submit = screen.getByTestId('price-alert-subscribe-submit');
    fireEvent.click(submit);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/part-price-alerts/', {
        part_id: PART_ID,
        threshold_cents: 10000,
      });
    });

    // Dialog should close on success.
    await waitFor(() => {
      expect(
        screen.queryByTestId('price-alert-subscribe-dialog')
      ).not.toBeInTheDocument();
    });
  });

  it('authenticated user with existing alert → label flips to "Manage alert ($X.XX)" and dialog prefills the existing threshold', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [existingAlert] });

    render(
      <PriceAlertSubscribeButton
        partId={PART_ID}
        currentBestPriceCents={10000}
      />,
      authedScenario
    );

    // Wait for listMine to resolve and the label to flip.
    await waitFor(() => {
      expect(
        screen.getByTestId('price-alert-subscribe-trigger')
      ).toHaveTextContent('Manage alert ($75.00)');
    });

    fireEvent.click(screen.getByTestId('price-alert-subscribe-trigger'));

    const input = await screen.findByTestId('price-alert-threshold-input');
    // Should pre-fill from existing alert (75.00), not currentBestPriceCents (100.00).
    expect(input).toHaveValue(75);
  });

  it('rejects negative threshold client-side without calling the API', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    render(
      <PriceAlertSubscribeButton
        partId={PART_ID}
        currentBestPriceCents={10000}
        defaultOpen
      />,
      authedScenario
    );

    const input = await screen.findByTestId('price-alert-threshold-input');
    fireEvent.change(input, { target: { value: '-5' } });

    fireEvent.click(screen.getByTestId('price-alert-subscribe-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('price-alert-error')).toHaveTextContent(
        /non-negative/i
      );
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('surfaces a 422 server error inline (does not close dialog)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 422,
        data: { detail: [{ msg: 'Threshold must be non-negative' }] },
      },
    });

    render(
      <PriceAlertSubscribeButton
        partId={PART_ID}
        currentBestPriceCents={10000}
        defaultOpen
      />,
      authedScenario
    );

    const input = await screen.findByTestId('price-alert-threshold-input');
    fireEvent.change(input, { target: { value: '50' } });
    fireEvent.click(screen.getByTestId('price-alert-subscribe-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('price-alert-error')).toHaveTextContent(
        /threshold must be non-negative/i
      );
    });
    // Dialog should remain open after a 4xx so the user can correct & retry.
    expect(
      screen.getByTestId('price-alert-subscribe-dialog')
    ).toBeInTheDocument();
  });
});
