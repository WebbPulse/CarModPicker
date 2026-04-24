// Retailers domain API. Mirrors backend endpoints/retailers.py.
// Extracted from services/Api.ts (lines 529-531) per Phase 6 D-22.
// Currently only exposes a count endpoint; richer surface lands when needed.
import { apiClient } from './client';

export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};
