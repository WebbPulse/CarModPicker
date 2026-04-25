/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.post).mockResolvedValueOnce(...) is the canonical
 * mock pattern; the unbound-method rule flags the reference syntactically
 * but vi.mocked returns a spy wrapper.
 */
import type { ReactNode } from 'react';
import { render, waitFor } from '@testing-library/react';
import { AxiosHeaders, type AxiosResponse } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../api/client';
import PartList from './PartList';
import { __resetSparklineCellCache } from './SparklineCell';
import type {
  PartReadWithVotes,
  PriceHistoryBatchResponse,
  PriceHistorySummary,
} from '../../types/Api';

// PartList depends on ResizeObserver via useContainerWidth. jsdom doesn't
// ship one — stub here so the callback ref attaches to a DOM node without
// throwing.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

// jsdom does not implement IntersectionObserver. Stub a fake one. We don't
// need to trigger intersection in this integration test — we only want to
// assert the PARENT batch hook fires exactly one POST regardless of
// per-row sparkline behavior. The fake's `observe()` is a no-op.
class FakeIntersectionObserver {
  observe(): void {}
  disconnect(): void {}
  unobserve(): void {}
}

beforeEach(() => {
  vi.clearAllMocks();
  __resetSparklineCellCache();
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function buildResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
}

function makeSummary(
  overrides: Partial<PriceHistorySummary> = {},
): PriceHistorySummary {
  return {
    min_cents: 1000,
    max_cents: 2000,
    last_cents: 1500,
    last_observed_at: '2026-04-01T00:00:00Z',
    trend: 'flat',
    observation_count: 3,
    ...overrides,
  };
}

function makePart(id: string, name: string): PartReadWithVotes {
  return {
    id,
    name,
    description: `${name} description`,
    best_price_cents: 1500,
    image_urls: null,
    category_id: 'cat-1',
    user_id: 'u-1',
    car_ids: [],
    is_universal: false,
    part_manufacturer: 'TestMfr',
    part_number: `PN-${id}`,
    specifications: null,
    is_verified: true,
    source: 'user',
    edit_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    upvotes: 0,
    downvotes: 0,
    total_votes: 0,
    user_vote: null,
  };
}

function wrap(node: ReactNode) {
  return <MemoryRouter>{node}</MemoryRouter>;
}

describe('PartList — price-history integration', () => {
  it('makes exactly ONE POST to /parts/price-history for the displayed page', async () => {
    const parts = [
      makePart('p-zero', 'Zero observations'),
      makePart('p-single', 'Single observation'),
      makePart('p-multi', 'Multi observations'),
    ];
    const batch: PriceHistoryBatchResponse = {
      summaries: {
        'p-zero': makeSummary({ observation_count: 0 }),
        'p-single': makeSummary({ observation_count: 1 }),
        'p-multi': makeSummary({ observation_count: 5, trend: 'down' }),
      },
      window: '90d',
      requested_count: 3,
      found_count: 3,
    };

    vi.mocked(apiClient.post).mockResolvedValueOnce(buildResponse(batch));

    render(wrap(<PartList data={parts} />));

    await waitFor(() => {
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/parts/price-history',
      expect.objectContaining({
        part_ids: expect.arrayContaining(['p-zero', 'p-single', 'p-multi']),
      }),
    );
  });

  it('renders a sparkline (role=img) for the multi-observation card and none for the zero card', async () => {
    const parts = [
      makePart('p-zero', 'Zero Part'),
      makePart('p-multi', 'Multi Part'),
    ];
    const batch: PriceHistoryBatchResponse = {
      summaries: {
        'p-zero': makeSummary({ observation_count: 0 }),
        'p-multi': makeSummary({
          observation_count: 4,
          trend: 'up',
          last_cents: 2000,
        }),
      },
      window: '90d',
      requested_count: 2,
      found_count: 2,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce(buildResponse(batch));

    const { container } = render(wrap(<PartList data={parts} />));

    // Wait for the hook to populate summaries.
    await waitFor(() => {
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    });

    // Multi-observation card has a SparklineCell wrapper rendered (waiting on
    // intersection to fetch history before drawing the polyline). Zero card
    // renders nothing for the sparkline.
    await waitFor(() => {
      const multiCells = container.querySelectorAll(
        '[data-testid="sparkline-cell"][data-part-id="p-multi"]',
      );
      expect(multiCells.length).toBeGreaterThan(0);
    });

    const zeroCells = container.querySelectorAll(
      '[data-testid="sparkline-cell"][data-part-id="p-zero"]',
    );
    expect(zeroCells.length).toBe(0);
  });

  it('renders a single-observation dot from the summary alone (no extra fetch)', async () => {
    const parts = [makePart('p-single', 'Single Part')];
    const batch: PriceHistoryBatchResponse = {
      summaries: {
        'p-single': makeSummary({
          observation_count: 1,
          last_cents: 1500,
          last_observed_at: '2026-04-01T00:00:00Z',
        }),
      },
      window: '90d',
      requested_count: 1,
      found_count: 1,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce(buildResponse(batch));

    const { container } = render(wrap(<PartList data={parts} />));

    // Centered dot indicates single-obs branch — populated synchronously
    // from summary, no additional GET to /parts/:id/price-history fired.
    await waitFor(() => {
      expect(
        container.querySelector('[data-testid="sparkline-dot"]'),
      ).not.toBeNull();
    });

    // The only request is the batch POST. No GET to per-part price-history.
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    const getCalls = vi.mocked(apiClient.get).mock.calls;
    const perPartGets = getCalls.filter((args) => {
      const url = String(args[0] ?? '');
      return url.includes('price-history') && url.includes('p-single');
    });
    expect(perPartGets).toHaveLength(0);
  });
});
