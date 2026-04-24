// Phase 8 plan 08-07: adminApi coverage tests.
//
// admin.ts is 421 lines — the single largest API module. Per RESEARCH.md §2 it
// gets its own plan so the PR stays reviewable. Tests cover every method on
// `adminApi` (~32 methods across 10 sub-surfaces).
//
// The setup.ts D-18 mock installs a shared `mockApiClient` for both
// `../api/client` and `../services/Api`, so importing `apiClient` from
// `./client` gives us the mocked surface automatically — no per-file vi.mock
// needed. Fixture factories come from plan 08-01's `src/test/mocks/admin/*.ts`.
//
// Lint note: `@typescript-eslint/unbound-method` (enabled by the recommended-
// type-checked preset + Phase 6 D-05 removing the test-file override) fires on
// both `expect(apiClient.post)` and `vi.mocked(apiClient.post)` because
// `apiClient.post` appears as a detached method reference in the argument
// position — the rule fires before control reaches the runtime unbound call.
// This is the canonical vitest pattern for API-module tests (we MUST reference
// the method to set up mocks and assert call shape), so we disable the rule
// file-wide here. Matches the pattern every Wave 1 API test file will adopt.
/* eslint-disable @typescript-eslint/unbound-method */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { adminApi } from './admin';
import {
  makeSystemStats,
  makeCrawlBucketSummary,
} from '../test/mocks/admin/stats';

describe('adminApi — migrations & db-ops', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runMigrations POSTs to /admin/db-ops/migrations/run', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        success: true,
        output: 'upgraded',
        error: null,
        current_revision: 'abc123',
      },
    });

    await adminApi.runMigrations();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/migrations/run'
    );
  });

  it('getCurrentRevision GETs /admin/db-ops/migrations/current', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { current_revision: 'abc123', output: 'ok' },
    });

    await adminApi.getCurrentRevision();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/db-ops/migrations/current'
    );
  });

  it('initCarGenerations POSTs to /admin/db-ops/init/car-generations', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { success: true, message: 'seeded' },
    });

    await adminApi.initCarGenerations();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/init/car-generations'
    );
  });

  it('initPartCategories POSTs to /admin/db-ops/init/part-categories', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { success: true, message: 'seeded' },
    });

    await adminApi.initPartCategories();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/init/part-categories'
    );
  });

  it('deleteAllParts POSTs to /admin/db-ops/parts/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { deleted_count: 42 },
    });

    const result = await adminApi.deleteAllParts();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/parts/delete-all'
    );
    expect(result.data.deleted_count).toBe(42);
  });

  it('deleteAllCars POSTs to /admin/db-ops/cars/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        deleted_count: 5,
        deleted_car_models_count: 10,
        deleted_makes_count: 3,
      },
    });

    const result = await adminApi.deleteAllCars();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/cars/delete-all'
    );
    expect(result.data.deleted_makes_count).toBe(3);
  });

  it('deleteAllPartManufacturers POSTs to /admin/db-ops/part-manufacturers/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { deleted_count: 7 },
    });

    await adminApi.deleteAllPartManufacturers();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/part-manufacturers/delete-all'
    );
  });
});

describe('adminApi — system stats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getTableCounts GETs /admin/stats/table-counts', async () => {
    const stats = makeSystemStats({ crawled_pages: 123, part_listings: 456 });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: stats });

    const result = await adminApi.getTableCounts();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/stats/table-counts'
    );
    expect(result.data).toEqual(stats);
    expect(result.data.crawled_pages).toBe(123);
  });

  it('getTableCounts returns vote/report polymorphic breakdown', async () => {
    const stats = makeSystemStats({
      votes_by_entity_type: { part: 10, build_list: 5 },
      reports_by_entity_type: { part: 2 },
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: stats });

    const result = await adminApi.getTableCounts();

    expect(result.data.votes_by_entity_type).toEqual({
      part: 10,
      build_list: 5,
    });
    expect(result.data.reports_by_entity_type).toEqual({ part: 2 });
  });

  it('getCrawlBucketSummary GETs /admin/stats/crawl-bucket', async () => {
    const summary = makeCrawlBucketSummary({
      crawl_bucket_total: 9999,
      crawl_bucket_by_prefix: { 'adapter-a/': 5000, 'adapter-b/': 4999 },
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: summary });

    const result = await adminApi.getCrawlBucketSummary();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/stats/crawl-bucket'
    );
    expect(result.data.crawl_bucket_total).toBe(9999);
  });
});

describe('adminApi — crawled page counts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCrawledPageCountsBySource GETs /crawled-pages/counts-by-source', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { 'adapter-a': 100, chrome_extension: 50 },
    });

    const result = await adminApi.getCrawledPageCountsBySource();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/crawled-pages/counts-by-source'
    );
    expect(result.data['adapter-a']).toBe(100);
  });

  it('getCrawledPageCountsBySourceAndStatus GETs /crawled-pages/counts-by-source-and-status', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        'adapter-a': { parsed: 80, pending: 20 },
        chrome_extension: { parsed: 50, pending: 0 },
      },
    });

    const result = await adminApi.getCrawledPageCountsBySourceAndStatus();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/crawled-pages/counts-by-source-and-status'
    );
    expect(result.data['adapter-a']?.['parsed']).toBe(80);
  });
});
