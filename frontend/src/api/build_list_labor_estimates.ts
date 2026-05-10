// Build List Labor Estimates domain API. Mirrors backend endpoints/build_list_labor_estimates.py.
// Update/delete by labor estimate ID; list/create live on buildListsApi (parent-scoped).
import { apiClient } from './client';
import type {
  BuildListLaborEstimateRead,
  BuildListLaborEstimateUpdate,
} from '../types/Api';

export const buildListLaborEstimatesApi = {
  updateLaborEstimate: (
    laborEstimateId: string,
    data: BuildListLaborEstimateUpdate
  ) =>
    apiClient.put<BuildListLaborEstimateRead>(
      `/build-list-labor-estimates/${laborEstimateId}`,
      data
    ),
  deleteLaborEstimate: (laborEstimateId: string) =>
    apiClient.delete<BuildListLaborEstimateRead>(
      `/build-list-labor-estimates/${laborEstimateId}`
    ),
};
