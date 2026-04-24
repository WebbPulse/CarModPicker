// Utility / health API. No backend domain mirror — these are top-level
// liveness / root probes. Extracted from services/Api.ts (lines 941-944)
// per Phase 6 D-22.
import { apiClient } from './client';

export const utilityApi = {
  getRoot: () => apiClient.get<Record<string, string>>('/'),
  healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
};
