// Search domain API. Mirrors backend endpoints/search.py.
// Extracted from services/Api.ts (lines 919-938) per Phase 6 D-22.
//
// Co-located response types per D-04 (these are not pydantic-generated; they
// describe the bespoke search-result envelope produced by the search router).
import { apiClient } from './client';
import type { BuildListRead, PartRead, UserRead } from '../types/Api';

export interface SearchCategoryResults<T> {
  data: T[];
  total: number;
  has_next: boolean;
  skip: number;
  limit: number;
}

export interface SearchResults {
  build_lists: SearchCategoryResults<BuildListRead>;
  users: SearchCategoryResults<UserRead>;
  parts: SearchCategoryResults<PartRead>;
  query: string;
}

export const searchApi = {
  search: (params: { q: string; skip?: number; limit?: number }) =>
    apiClient.get<SearchResults>('/search/', { params }),
};
