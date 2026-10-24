import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import BuildListItem from '../components/buildLists/BuildListItem';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import PartListItem from '../components/parts/PartListItem';
import { ErrorAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import Spinner from '../components/ui/spinner';
import UserCard from '../components/users/UserCard';
import { SEARCH_INITIAL_LIMITS, SEARCH_RESULTS_LIMIT } from '../constants';
import useApiRequest from '../hooks/UseApiRequest';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import {
  searchApi,
  type SearchCategory,
  type SearchParams,
  type SearchResults,
} from '../api/search';
import type {
  BuildListRead,
  CursorPage,
  PartRead,
  PublicUserRead,
} from '../types/Api';
import { getApiErrorMessage } from '../utils/apiError';

/** Loaded items, next cursor, and how many are shown for one category. */
interface CategoryState<T> {
  items: T[];
  nextCursor: string | null;
  hasNext: boolean;
  displayed: number;
}

/** Per category results for the current query. */
interface SearchState {
  build_lists: CategoryState<BuildListRead>;
  parts: CategoryState<PartRead>;
  users: CategoryState<PublicUserRead>;
}

const SECTION_ORDER: SearchCategory[] = ['build_lists', 'parts', 'users'];

const SECTION_LABELS: Record<SearchCategory, string> = {
  build_lists: 'Build Lists',
  parts: 'Parts',
  users: 'Users',
};

const CURSOR_PARAM: Record<
  SearchCategory,
  'build_lists_cursor' | 'parts_cursor' | 'users_cursor'
> = {
  build_lists: 'build_lists_cursor',
  parts: 'parts_cursor',
  users: 'users_cursor',
};

const emptyCategory = <T,>(): CategoryState<T> => ({
  items: [],
  nextCursor: null,
  hasNext: false,
  displayed: 0,
});

const emptySearchState = (): SearchState => ({
  build_lists: emptyCategory<BuildListRead>(),
  parts: emptyCategory<PartRead>(),
  users: emptyCategory<PublicUserRead>(),
});

const categoryFromPage = <T,>(
  page: CursorPage<T>,
  category: SearchCategory
): CategoryState<T> => ({
  items: page.items,
  nextCursor: page.next_cursor,
  hasNext: page.has_next,
  displayed: Math.min(SEARCH_INITIAL_LIMITS[category], page.items.length),
});

const appendPage = <T,>(
  current: CategoryState<T>,
  page: CursorPage<T>,
  category: SearchCategory
): CategoryState<T> => {
  const items = [...current.items, ...page.items];
  return {
    items,
    nextCursor: page.next_cursor,
    hasNext: page.has_next,
    displayed: Math.min(
      current.displayed + SEARCH_INITIAL_LIMITS[category],
      items.length
    ),
  };
};

/** Maps a first page search response onto per category state. */
const searchStateFromResults = (results: SearchResults): SearchState => ({
  build_lists: categoryFromPage(results.build_lists, 'build_lists'),
  parts: categoryFromPage(results.parts, 'parts'),
  users: categoryFromPage(results.users, 'users'),
});

const fetchSearchResultsRequestFn = (params: SearchParams) =>
  searchApi.search(params);

/**
 * Site search page. The query lives in the URL, so a search is shareable and
 * survives reload, and results cover build lists, parts and users, each paged
 * by its own cursor.
 */
function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState(
    () => searchParams.get('q') || ''
  );

  const queryFromUrl = (searchParams.get('q') || '').trim();
  useDocumentMeta({
    title: queryFromUrl ? `Search: ${queryFromUrl}` : 'Search',
    description: queryFromUrl
      ? `Search results on CarModPicker for "${queryFromUrl}": builds, parts and users matching your query.`
      : 'Search CarModPicker for builds, parts and users across the community.',
    canonicalPath: '/search',
  });

  const [results, setResults] = useState<SearchState>(emptySearchState);
  const [currentQuery, setCurrentQuery] = useState<string>(queryFromUrl);
  const [loadingMore, setLoadingMore] = useState<SearchCategory | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);

  const {
    data: searchResults,
    isLoading,
    error,
    executeRequest: performSearch,
  } = useApiRequest(fetchSearchResultsRequestFn);

  const sortedSections = useMemo(
    () =>
      [...SECTION_ORDER].sort(
        (a, b) => results[b].items.length - results[a].items.length
      ),
    [results]
  );

  const handleSearch = useCallback(() => {
    const query = searchTerm.trim();
    if (query) setSearchParams({ q: query });
  }, [searchTerm, setSearchParams]);

  useEffect(() => {
    const trimmed = searchTerm.trim();
    const timer = setTimeout(() => {
      if (trimmed) {
        setSearchParams({ q: trimmed });
      } else {
        setSearchParams({});
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, setSearchParams]);

  useEffect(() => {
    setCurrentQuery(queryFromUrl);
    setResults(emptySearchState());
    setLoadMoreError(null);
    if (queryFromUrl) {
      setSearchTerm((prev) =>
        prev.trim() === queryFromUrl ? prev : queryFromUrl
      );
      void performSearch({ q: queryFromUrl, limit: SEARCH_RESULTS_LIMIT });
    }
  }, [queryFromUrl, performSearch]);

  useEffect(() => {
    if (searchResults && searchResults.query === currentQuery) {
      setResults(searchStateFromResults(searchResults));
    }
  }, [searchResults, currentQuery]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const loadMore = useCallback(
    async (category: SearchCategory) => {
      const state = results[category];
      if (state.displayed < state.items.length) {
        setResults((prev) => ({
          ...prev,
          [category]: {
            ...prev[category],
            displayed: Math.min(
              prev[category].displayed + SEARCH_INITIAL_LIMITS[category],
              prev[category].items.length
            ),
          },
        }));
        return;
      }
      if (!state.hasNext || !state.nextCursor || !currentQuery) return;

      const query = currentQuery;
      setLoadingMore(category);
      setLoadMoreError(null);
      try {
        const params: SearchParams = { q: query, limit: SEARCH_RESULTS_LIMIT };
        params[CURSOR_PARAM[category]] = state.nextCursor;
        const response = await searchApi.search(params);
        if (response.data.query !== query) return;
        setResults((prev) => {
          switch (category) {
            case 'build_lists':
              return {
                ...prev,
                build_lists: appendPage(
                  prev.build_lists,
                  response.data.build_lists,
                  category
                ),
              };
            case 'parts':
              return {
                ...prev,
                parts: appendPage(prev.parts, response.data.parts, category),
              };
            case 'users':
              return {
                ...prev,
                users: appendPage(prev.users, response.data.users, category),
              };
          }
        });
      } catch (err) {
        setLoadMoreError(
          getApiErrorMessage(err, 'Could not load more results.')
        );
      } finally {
        setLoadingMore(null);
      }
    },
    [results, currentQuery]
  );

  const renderItems = (category: SearchCategory) => {
    switch (category) {
      case 'build_lists':
        return results.build_lists.items
          .slice(0, results.build_lists.displayed)
          .map((buildList) => (
            <BuildListItem key={buildList.id} buildList={buildList} />
          ));
      case 'parts':
        return results.parts.items
          .slice(0, results.parts.displayed)
          .map((part) => <PartListItem key={part.id} part={part} />);
      case 'users':
        return results.users.items
          .slice(0, results.users.displayed)
          .map((user) => <UserCard key={user.id} user={user} />);
    }
  };

  const totalResults = SECTION_ORDER.reduce(
    (sum, category) => sum + results[category].items.length,
    0
  );

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Search" />

      <Card className="mb-8">
        <div className="flex gap-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Search build lists, parts and users..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full"
            />
          </div>
          <Button
            type="button"
            onClick={handleSearch}
            className="bg-info hover:bg-info/90 text-white"
          >
            Search
          </Button>
        </div>
      </Card>

      {isLoading && (
        <Card>
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        </Card>
      )}

      {error && !isLoading && (
        <Card>
          <ErrorAlert message={`Search failed: ${error}`} />
        </Card>
      )}

      {!isLoading && !error && currentQuery && (
        <>
          {loadMoreError && (
            <Card className="mb-6">
              <ErrorAlert message={loadMoreError} />
            </Card>
          )}

          {sortedSections.map((category) => {
            const state = results[category];
            const label = SECTION_LABELS[category];
            const canLoadMore =
              state.hasNext || state.displayed < state.items.length;
            return (
              <Card key={category} className="mb-6">
                <SectionHeader
                  title={`${label} (${state.items.length}${state.hasNext ? '+' : ''})`}
                />
                {state.items.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <p>No {label.toLowerCase()} found.</p>
                  </div>
                ) : (
                  <>
                    <div className="tile-grid-compact">
                      {renderItems(category)}
                    </div>
                    {canLoadMore && (
                      <div className="mt-6 flex justify-center">
                        <Button
                          type="button"
                          onClick={() => void loadMore(category)}
                          disabled={loadingMore !== null}
                        >
                          {loadingMore === category
                            ? 'Loading...'
                            : `Load More ${label}`}
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </Card>
            );
          })}

          {totalResults === 0 && (
            <Card>
              <div className="text-center py-12">
                <p className="text-xl text-muted-foreground mb-2">
                  No results found for "{currentQuery}"
                </p>
                <p className="text-muted-foreground">
                  Try different search terms or check your spelling.
                </p>
              </div>
            </Card>
          )}
        </>
      )}

      {!isLoading && !error && !currentQuery && (
        <Card>
          <div className="text-center py-12">
            <p className="text-xl text-muted-foreground mb-2">
              Enter a search term to find build lists, parts and users
            </p>
            <p className="text-muted-foreground">
              Search across names and descriptions
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

export default Search;
