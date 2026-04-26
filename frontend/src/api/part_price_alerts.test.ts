// API-module test pattern (mirrors `parts.test.ts` per PATTERNS.md §7).
// `vi.mocked(apiClient.method)` and `expect(apiClient.method).toHaveBeenCalledWith(...)`
// reference methods as unbound values; the eslint rule is a false positive
// because vitest's mock runtime invokes them via the same mockApiClient identity
// (see frontend/src/test/setup.ts dual-mock block).
/* eslint-disable @typescript-eslint/unbound-method */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { partPriceAlertsApi } from './part_price_alerts';
import type {
  PartPriceAlertCreate,
  PartPriceAlertRead,
  PartPriceAlertUpdate,
} from '../types/Api';

const mockAlert: PartPriceAlertRead = {
  id: '99999999-9999-7999-8999-999999999999',
  user_id: '11111111-1111-7111-8111-111111111111',
  part_id: '44444444-4444-7444-8444-444444444444',
  threshold_cents: 9999,
  active: true,
  last_fired_at: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

describe('partPriceAlertsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('subscribe POSTs body to /part-price-alerts/', async () => {
    const body: PartPriceAlertCreate = {
      part_id: mockAlert.part_id,
      threshold_cents: 9999,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockAlert });

    const result = await partPriceAlertsApi.subscribe(body);

    expect(apiClient.post).toHaveBeenCalledWith('/part-price-alerts/', body);
    expect(result.data).toEqual(mockAlert);
  });

  it('listMine GETs /part-price-alerts/me', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockAlert] });

    const result = await partPriceAlertsApi.listMine();

    expect(apiClient.get).toHaveBeenCalledWith('/part-price-alerts/me');
    expect(result.data).toEqual([mockAlert]);
  });

  it('updateAlert PATCHes /part-price-alerts/{id} with body', async () => {
    const body: PartPriceAlertUpdate = { threshold_cents: 5000 };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: { ...mockAlert, threshold_cents: 5000 },
    });

    const result = await partPriceAlertsApi.updateAlert(mockAlert.id, body);

    expect(apiClient.patch).toHaveBeenCalledWith(
      `/part-price-alerts/${mockAlert.id}`,
      body
    );
    expect(result.data.threshold_cents).toBe(5000);
  });

  it('updateAlert can patch active flag only', async () => {
    const body: PartPriceAlertUpdate = { active: false };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: { ...mockAlert, active: false },
    });

    await partPriceAlertsApi.updateAlert(mockAlert.id, body);

    expect(apiClient.patch).toHaveBeenCalledWith(
      `/part-price-alerts/${mockAlert.id}`,
      body
    );
  });

  it('deleteAlert DELETEs /part-price-alerts/{id}', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: undefined });

    await partPriceAlertsApi.deleteAlert(mockAlert.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/part-price-alerts/${mockAlert.id}`
    );
  });
});
