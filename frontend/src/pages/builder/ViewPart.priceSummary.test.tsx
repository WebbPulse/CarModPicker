/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.*) is the canonical Vitest mock-introspection pattern;
 * matches sibling tests under src/components/parts/ and src/pages/builder/.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom ResizeObserver stub — ViewPart pulls in nothing that explicitly
// needs it today, but the Tabs primitive (Radix) and downstream charts
// historically have, so stub defensively to match ViewPart.test.tsx.
class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

import { apiClient } from '../../api/client';
import {
  mockCategory,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import type {
  PartListingReadWithRetailer,
  PriceHistorySinglePartResponse,
  RetailerPriceBreakdown,
} from '../../types/Api';
import ViewPart from './ViewPart';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../services/Api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/Api')>(
      '../../services/Api',
    );
  return actual;
});

function seedAuthenticated(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

function makeRetailer(
  overrides: Partial<RetailerPriceBreakdown> & { retailer_id: string },
): RetailerPriceBreakdown {
  const base: RetailerPriceBreakdown = {
    retailer_id: overrides.retailer_id,
    retailer_name: `Retailer ${overrides.retailer_id}`,
    min_cents: 1000,
    max_cents: 2000,
    last_cents: 1500,
    last_observed_at: '2026-04-01T00:00:00Z',
    observation_count: 3,
  };
  return { ...base, ...overrides };
}

function makeListing(
  id: string,
  retailerName: string,
  daysAgo: number | null,
): PartListingReadWithRetailer {
  const updated =
    daysAgo === null
      ? null
      : new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000).toISOString();
  return {
    id,
    part_id: mockPart.id,
    retailer_id: `r-${id}`,
    product_url: `https://example.com/${id}`,
    last_known_price_cents: 1500,
    last_price_updated_at: updated,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: updated ?? '2026-01-01T00:00:00Z',
    retailer: {
      id: `r-${id}`,
      name: retailerName,
      domain: null,
      base_url: null,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  };
}

interface InstallOpts {
  summary: PriceHistorySinglePartResponse;
  listings?: PartListingReadWithRetailer[];
}

function installGetRouting({ summary, listings = [] }: InstallOpts): void {
  // The /parts/{id}/price-history URL is shared between two callers:
  //  - getPartPriceHistory(id)        -> { params: { legacy: true } }
  //  - getPartPriceHistorySummary(id, { window: '90d' })
  //                                   -> { params: { window: '90d' } }
  // We discriminate by inspecting the params arg (second argument).
  vi.mocked(apiClient.get).mockImplementation(
    (url: string, config?: { params?: Record<string, unknown> }) => {
      if (url === `/parts/${mockPart.id}`) {
        return Promise.resolve({ data: mockPart });
      }
      if (url === `/votes/part/${mockPart.id}/summary`) {
        return Promise.resolve({ data: mockVoteSummary });
      }
      if (url === '/categories/') {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url === `/users/${mockUser.id}`) {
        return Promise.resolve({ data: mockUser });
      }
      if (url === `/parts/${mockPart.id}/listings`) {
        return Promise.resolve({ data: listings });
      }
      if (url === `/parts/${mockPart.id}/price-history`) {
        // Legacy call -> array shape; summary call -> object shape.
        if (config?.params?.['legacy'] === true) {
          return Promise.resolve({ data: [] });
        }
        return Promise.resolve({ data: summary });
      }
      return Promise.resolve({ data: null });
    },
  );
}

function renderViewPart() {
  return render(
    <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
      <Routes>
        <Route path="/parts/:partId" element={<ViewPart />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ViewPart price summary block', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('does not render the Price summary block when observation_count is 0', async () => {
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: null,
        max_cents: null,
        last_cents: null,
        last_observed_at: null,
        trend: 'flat',
        observation_count: 0,
      },
      retailers: [],
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    // Page loads.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: mockPart.name }),
      ).toBeInTheDocument(),
    );

    // Section heading exists (always rendered as a sibling block), but the
    // body — the stat strip / retailer breakdown — should not appear.
    expect(
      screen.queryByTestId('price-summary-stat-strip'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('retailer-breakdown-flat'),
    ).not.toBeInTheDocument();
  });

  it('renders a flat retailer list (no tabs) when retailer count <= 3', async () => {
    const retailers = [
      makeRetailer({ retailer_id: 'r1', retailer_name: 'Acme Parts' }),
      makeRetailer({ retailer_id: 'r2', retailer_name: 'Bravo Auto' }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 900,
        max_cents: 2100,
        last_cents: 1500,
        last_observed_at: '2026-04-01T00:00:00Z',
        trend: 'down',
        observation_count: 6,
      },
      retailers,
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    await waitFor(() =>
      expect(
        screen.getByTestId('price-summary-stat-strip'),
      ).toBeInTheDocument(),
    );

    // Flat list rendered, no tabs.
    expect(screen.getByTestId('retailer-breakdown-flat')).toBeInTheDocument();
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    // Both retailer names are visible.
    expect(screen.getByText('Acme Parts')).toBeInTheDocument();
    expect(screen.getByText('Bravo Auto')).toBeInTheDocument();
  });

  it('renders Tabs (one trigger per retailer + All) when retailer count > 3', async () => {
    const retailers = [
      makeRetailer({ retailer_id: 'r1', retailer_name: 'Acme' }),
      makeRetailer({ retailer_id: 'r2', retailer_name: 'Bravo' }),
      makeRetailer({ retailer_id: 'r3', retailer_name: 'Charlie' }),
      makeRetailer({ retailer_id: 'r4', retailer_name: 'Delta' }),
      makeRetailer({ retailer_id: 'r5', retailer_name: 'Echo' }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 900,
        max_cents: 2100,
        last_cents: 1500,
        last_observed_at: '2026-04-01T00:00:00Z',
        trend: 'up',
        observation_count: 10,
      },
      retailers,
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    await waitFor(() =>
      expect(
        screen.getByTestId('price-summary-stat-strip'),
      ).toBeInTheDocument(),
    );

    // Tablist present; flat list absent.
    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(
      screen.queryByTestId('retailer-breakdown-flat'),
    ).not.toBeInTheDocument();

    // One trigger per retailer + an 'All' trigger = 6 tabs.
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(retailers.length + 1);
    expect(screen.getByRole('tab', { name: 'All' })).toBeInTheDocument();
    for (const r of retailers) {
      expect(
        screen.getByRole('tab', { name: r.retailer_name }),
      ).toBeInTheDocument();
    }
  });

  it("shows the 'as of' stale caveat for a listing with last_price_updated_at 90 days ago", async () => {
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 1000,
        max_cents: 2000,
        last_cents: 1500,
        last_observed_at: '2026-04-01T00:00:00Z',
        trend: 'flat',
        observation_count: 3,
      },
      retailers: [],
      history: [],
      window: '90d',
    };
    const listings = [makeListing('L1', 'Stale Shop', 90)];
    installGetRouting({ summary, listings });

    renderViewPart();

    await waitFor(() =>
      expect(screen.getByText('Stale Shop')).toBeInTheDocument(),
    );

    // The amber 'as of' caveat is present.
    expect(screen.getByText(/as of/i)).toBeInTheDocument();
  });

  it("does not show the 'as of' caveat when last_price_updated_at is 5 days ago", async () => {
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 1000,
        max_cents: 2000,
        last_cents: 1500,
        last_observed_at: '2026-04-01T00:00:00Z',
        trend: 'flat',
        observation_count: 3,
      },
      retailers: [],
      history: [],
      window: '90d',
    };
    const listings = [makeListing('L1', 'Fresh Shop', 5)];
    installGetRouting({ summary, listings });

    renderViewPart();

    await waitFor(() =>
      expect(screen.getByText('Fresh Shop')).toBeInTheDocument(),
    );

    // No stale caveat — the regular 'updated' span renders, but no 'as of'.
    expect(screen.queryByText(/as of/i)).not.toBeInTheDocument();
  });
});
