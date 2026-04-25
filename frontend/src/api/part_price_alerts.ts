// Part price-drop alert subscriptions (M002/S07).
// Mirrors backend `app/api/endpoints/part_price_alerts.py` (prefix /part-price-alerts).
// Per-user surface: subscribe, list-mine, patch, soft-delete. Token-based
// public unsubscribe (`GET /unsubscribe`) is not exposed here — it's only
// reached via the email link, never an authenticated client call.
import { apiClient } from './client';
import type {
  PartPriceAlertCreate,
  PartPriceAlertRead,
  PartPriceAlertUpdate,
} from '../types/Api';

export const partPriceAlertsApi = {
  // Subscribe (or re-subscribe — backend is idempotent on user_id+part_id).
  subscribe: (data: PartPriceAlertCreate) =>
    apiClient.post<PartPriceAlertRead>('/part-price-alerts/', data),

  // List the current user's active alerts.
  listMine: () =>
    apiClient.get<PartPriceAlertRead[]>('/part-price-alerts/me'),

  // Patch threshold and/or active flag on the user's own alert.
  updateAlert: (alertId: string, data: PartPriceAlertUpdate) =>
    apiClient.patch<PartPriceAlertRead>(
      `/part-price-alerts/${alertId}`,
      data
    ),

  // Soft-delete (active=false).
  deleteAlert: (alertId: string) =>
    apiClient.delete<void>(`/part-price-alerts/${alertId}`),
};
