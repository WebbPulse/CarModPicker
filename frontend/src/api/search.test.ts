/**
 * Tests for searchApi.
 */

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import { searchApi, type SearchResults } from './search';
import { mockBuildList, mockPart, mockUser } from '../test/mocks/api';

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

function makeEmptyResults(query: string): SearchResults {
  return {
    build_lists: { items: [], next_cursor: null, has_next: false },
    users: { items: [], next_cursor: null, has_next: false },
    parts: { items: [], next_cursor: null, has_next: false },
    query,
  };
}

describe('searchApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('search forwards query params to /search via GET', async () => {
    const payload: SearchResults = {
      build_lists: {
        items: [mockBuildList],
        next_cursor: null,
        has_next: false,
      },
      users: {
        items: [mockUser],
        next_cursor: null,
        has_next: false,
      },
      parts: {
        items: [mockPart],
        next_cursor: 'parts-cursor-1',
        has_next: true,
      },
      query: 'honda civic',
    };
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await searchApi.search({
      q: 'honda civic',
      limit: 10,
      parts_cursor: 'parts-cursor-0',
    });

    expect(getMock).toHaveBeenCalledWith('/search', {
      params: { q: 'honda civic', limit: 10, parts_cursor: 'parts-cursor-0' },
    });
    expect(result.data).toEqual(payload);
    expect(result.data.query).toBe('honda civic');
  });

  it('search passes through the q-only form without limit or cursors', async () => {
    getMock.mockResolvedValueOnce({
      data: makeEmptyResults('civic'),
    });

    await searchApi.search({ q: 'civic' });

    expect(getMock).toHaveBeenCalledWith('/search', {
      params: { q: 'civic' },
    });
    expect(getMock).toHaveBeenCalledTimes(1);
  });

  it('search returns the empty-results envelope verbatim for a no-match query', async () => {
    const payload = makeEmptyResults('xyzzy-no-match');
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await searchApi.search({ q: 'xyzzy-no-match' });

    expect(result.data.build_lists.items).toHaveLength(0);
    expect(result.data.users.items).toHaveLength(0);
    expect(result.data.parts.items).toHaveLength(0);
    expect(result.data.query).toBe('xyzzy-no-match');
  });
});
