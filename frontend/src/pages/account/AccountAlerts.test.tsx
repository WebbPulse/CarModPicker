// Page test for AccountAlerts (M002/S07/T05).
// Covers: loading state, empty state, single-alert render, multi-alert render,
// unsubscribe → row removed, listMine 401 → error surfaced inline (the
// route-level ProtectedRoute is what handles unauth redirect; once you're on
// this page, a stale-token 401 surfaces as an inline error, not a redirect).
// Also covers the ?status=success / ?status=error banners landed on by the
// token-as-auth public unsubscribe redirect.
/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/no-unsafe-assignment */
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import AccountAlerts from './AccountAlerts';
import { mockUser, mockPart } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { render } from '../../test/utils/test-utils';
import type { PartPriceAlertRead, PartRead } from '../../types/Api';

// Build the authed scenario from the canonical mockUser (matching the
// pattern in PriceAlertSubscribeButton.test.tsx — testScenarios.authenticated
// in test-utils builds `user` from a stale createMockUser helper that
// pre-dates UserRead's subscription/2fa fields).
const authedScenario = {
  initialAuthState: {
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
  },
};

// vi.mock is hoisted per-file, so the test-utils.tsx hook mock doesn't
// auto-apply here — declare it explicitly so AccountAlerts' useAuth() (well,
// it doesn't currently call useAuth, but other transitive children might)
// resolves to the test-controlled mockUseAuth.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const PART_A_ID = '44444444-4444-7444-8444-444444444444';
const PART_B_ID = 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb';

const partA: PartRead = { ...mockPart, id: PART_A_ID, name: 'Cold Air Intake' };
const partB: PartRead = {
  ...mockPart,
  id: PART_B_ID,
  name: 'Lowering Springs',
};

const alertA: PartPriceAlertRead = {
  id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
  user_id: mockUser.id,
  part_id: PART_A_ID,
  threshold_cents: 7500, // $75.00
  active: true,
  last_fired_at: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

const alertB: PartPriceAlertRead = {
  id: 'bbbbbbb1-bbbb-7bbb-8bbb-bbbbbbbbbbbb',
  user_id: mockUser.id,
  part_id: PART_B_ID,
  threshold_cents: 19999, // $199.99
  active: true,
  last_fired_at: '2026-04-15T12:00:00Z',
  created_at: '2026-04-10T00:00:00Z',
  updated_at: '2026-04-15T12:00:00Z',
};

// Tag the listMine GET vs the per-row getPart GETs by URL prefix so the
// dispatcher returns the right payload regardless of call order. apiClient.get
// is the shared mock (test-utils registers it under '../api/client').
function setupGetDispatcher(
  alerts: PartPriceAlertRead[],
  parts: Record<string, PartRead> = {}
) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/part-price-alerts/me') {
      return Promise.resolve({ data: alerts });
    }
    if (url.startsWith('/parts/')) {
      const id = url.replace(/^\/parts\//, '');
      const part = parts[id];
      if (part) return Promise.resolve({ data: part });
      return Promise.reject({ response: { status: 404 } });
    }
    return Promise.resolve({ data: null });
  });
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.delete).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('AccountAlerts', () => {
  it('shows a loading spinner while listMine is in-flight', async () => {
    // Never resolve the listMine promise so the loading branch holds.
    let _resolve: ((v: { data: PartPriceAlertRead[] }) => void) | undefined;
    const pending = new Promise<{ data: PartPriceAlertRead[] }>((resolve) => {
      _resolve = resolve;
    });
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/part-price-alerts/me') return pending;
      return Promise.resolve({ data: null });
    });

    render(<AccountAlerts />, authedScenario);

    expect(await screen.findByTestId('alerts-loading')).toBeInTheDocument();
    // Resolve at the end so the test cleanup doesn't get a dangling promise.
    _resolve?.({ data: [] });
  });

  it('renders the empty state when listMine returns no alerts', async () => {
    setupGetDispatcher([]);

    render(<AccountAlerts />, authedScenario);

    expect(await screen.findByTestId('alerts-empty')).toHaveTextContent(
      /no active price-drop alerts/i
    );
    // The empty-state link to /parts must be present.
    const browseLink = screen.getByRole('link', { name: /browse parts/i });
    expect(browseLink).toHaveAttribute('href', '/parts');
    // No alert rows.
    expect(screen.queryByTestId('alert-row')).not.toBeInTheDocument();
  });

  it('renders a single alert row with hydrated part name, threshold, created_at, and "Not sent yet"', async () => {
    setupGetDispatcher([alertA], { [PART_A_ID]: partA });

    render(<AccountAlerts />, authedScenario);

    // Row appears once listMine resolves; part name fills in once getPart resolves.
    const row = await screen.findByTestId('alert-row');
    await waitFor(() => {
      expect(within(row).getByTestId('alert-row-part-link')).toHaveTextContent(
        'Cold Air Intake'
      );
    });
    expect(within(row).getByTestId('alert-row-part-link')).toHaveAttribute(
      'href',
      `/parts/${PART_A_ID}`
    );
    expect(within(row).getByTestId('alert-row-threshold')).toHaveTextContent(
      '$75.00'
    );
    // alertA.created_at is 2026-04-01 UTC — date string varies by tz, just
    // assert we have a date formatted next to "Created".
    expect(within(row).getByTestId('alert-row-created')).toHaveTextContent(
      /Created \d/
    );
    // last_fired_at is null → "Not sent yet".
    expect(within(row).getByTestId('alert-row-last-fired')).toHaveTextContent(
      /not sent yet/i
    );
    expect(within(row).getByTestId('alert-row-unsubscribe')).toBeEnabled();
  });

  it('renders multiple alert rows in listMine order with mixed last-fired states', async () => {
    setupGetDispatcher([alertA, alertB], {
      [PART_A_ID]: partA,
      [PART_B_ID]: partB,
    });

    render(<AccountAlerts />, authedScenario);

    // Wait for both rows to appear (listMine resolves first, then per-row part fetches).
    await waitFor(() => {
      expect(screen.getAllByTestId('alert-row')).toHaveLength(2);
    });
    // Wait for both part names to hydrate.
    await waitFor(() => {
      expect(screen.getByText('Cold Air Intake')).toBeInTheDocument();
      expect(screen.getByText('Lowering Springs')).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId('alert-row');
    // Row order matches listMine order.
    expect(rows[0]).toHaveAttribute('data-alert-id', alertA.id);
    expect(rows[1]).toHaveAttribute('data-alert-id', alertB.id);
    // alertA is "Not sent yet"; alertB has a last_fired_at → "Last sent <date>".
    expect(within(rows[0]!).getByTestId('alert-row-last-fired')).toHaveTextContent(
      /not sent yet/i
    );
    expect(within(rows[1]!).getByTestId('alert-row-last-fired')).toHaveTextContent(
      /last sent/i
    );
    // alertB threshold $199.99.
    expect(within(rows[1]!).getByTestId('alert-row-threshold')).toHaveTextContent(
      '$199.99'
    );
  });

  it('clicking Unsubscribe DELETEs the alert and removes the row from the list', async () => {
    setupGetDispatcher([alertA, alertB], {
      [PART_A_ID]: partA,
      [PART_B_ID]: partB,
    });
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: undefined });

    render(<AccountAlerts />, authedScenario);

    await waitFor(() => {
      expect(screen.getAllByTestId('alert-row')).toHaveLength(2);
    });

    const rows = screen.getAllByTestId('alert-row');
    const unsubBtn = within(rows[0]!).getByTestId('alert-row-unsubscribe');
    fireEvent.click(unsubBtn);

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith(
        `/part-price-alerts/${alertA.id}`
      );
    });

    // Row for alertA is gone; alertB row remains.
    await waitFor(() => {
      expect(screen.getAllByTestId('alert-row')).toHaveLength(1);
    });
    expect(screen.getAllByTestId('alert-row')[0]).toHaveAttribute(
      'data-alert-id',
      alertB.id
    );
  });

  it('surfaces a row-level error if the DELETE fails (row stays in the list)', async () => {
    setupGetDispatcher([alertA], { [PART_A_ID]: partA });
    vi.mocked(apiClient.delete).mockRejectedValueOnce({
      response: { status: 500, data: { detail: 'Internal server error' } },
    });

    render(<AccountAlerts />, authedScenario);

    const row = await screen.findByTestId('alert-row');
    fireEvent.click(within(row).getByTestId('alert-row-unsubscribe'));

    await waitFor(() => {
      expect(within(row).getByTestId('alert-row-error')).toHaveTextContent(
        /internal server error/i
      );
    });
    // Row still present.
    expect(screen.getByTestId('alert-row')).toBeInTheDocument();
  });

  it('surfaces a top-level error message if listMine returns 401 (stale token mid-session)', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/part-price-alerts/me') {
        return Promise.reject({
          isAxiosError: true,
          response: {
            status: 401,
            data: { detail: 'Could not validate credentials' },
          },
        });
      }
      return Promise.resolve({ data: null });
    });

    render(<AccountAlerts />, authedScenario);

    // useApiRequest's parseApiError surfaces the detail string verbatim.
    await waitFor(() => {
      expect(
        screen.getByText(/could not load your alerts/i)
      ).toBeInTheDocument();
    });
    // No alert rows when the load fails.
    expect(screen.queryByTestId('alert-row')).not.toBeInTheDocument();
  });

  it('renders a success banner when the page is reached with ?status=success (post token-unsubscribe)', async () => {
    setupGetDispatcher([]);

    render(<AccountAlerts />, {
      ...authedScenario,
      route: '/account/alerts?status=success',
    });

    expect(
      await screen.findByTestId('status-banner-success')
    ).toBeInTheDocument();
    // The empty state still renders below it (since this user has zero alerts now).
    expect(await screen.findByTestId('alerts-empty')).toBeInTheDocument();
  });

  it('renders an error banner when the page is reached with ?status=error (invalid/expired token)', async () => {
    setupGetDispatcher([]);

    render(<AccountAlerts />, {
      ...authedScenario,
      route: '/account/alerts?status=error',
    });

    expect(
      await screen.findByTestId('status-banner-error')
    ).toBeInTheDocument();
  });
});
