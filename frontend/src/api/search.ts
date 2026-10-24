/**
 * Cross-entity search returning build lists, users, and parts in one response so
 * the results page needs a single request.
 */

import { apiClient } from './client';
import type {
  BuildListRead,
  CursorPage,
  PartRead,
  PublicUserRead,
} from '../types/Api';

/** Search hits grouped by entity type, each a cursor page, echoing the query. */
export interface SearchResults {
  build_lists: CursorPage<BuildListRead>;
  users: CursorPage<PublicUserRead>;
  parts: CursorPage<PartRead>;
  query: string;
}

/** A searchable entity type, keyed as in `SearchResults`. */
export type SearchCategory = 'build_lists' | 'users' | 'parts';

/** Query, per category limit, and the cursor of each category to continue. */
export type SearchParams = {
  q: string;
  limit?: number;
  build_lists_cursor?: string;
  users_cursor?: string;
  parts_cursor?: string;
};

/** Cross entity search in a single request. */
export const searchApi = {
  search: (params: SearchParams) =>
    apiClient.get<SearchResults>('/search', { params }),
};
