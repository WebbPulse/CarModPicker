/**
 * Part category lookup and the parts listed under each category.
 */

import { apiClient } from './client';
import type {
  CategoryResponse,
  CursorPage,
  CursorParams,
  PartRead,
} from '../types/Api';

/** Part category lookup and the parts under each category. */
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories'),
  getCategory: (categoryId: string) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  getPartsByCategory: (categoryId: string, params?: CursorParams) =>
    apiClient.get<CursorPage<PartRead>>(`/categories/${categoryId}/parts`, {
      params,
    }),

  getCategoryPartsCount: (categoryId: string) =>
    apiClient.get<{ count: number }>(`/categories/${categoryId}/parts-count`),
  countCategories: () => apiClient.get<{ count: number }>('/categories/count'),
};
