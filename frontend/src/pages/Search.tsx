import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import BuildListItem from '../components/buildLists/BuildListItem';
import PartList from '../components/parts/PartList';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import { ErrorAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import Spinner from '../components/ui/spinner';
import UserCard from '../components/users/UserCard';
import {
  SEARCH_INITIAL_LIMITS,
  SEARCH_LOAD_MORE_INCREMENT,
  SEARCH_RESULTS_LIMIT,
} from '../constants';
import useApiRequest from '../hooks/UseApiRequest';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import { searchApi } from '../services/Api';
import type {
  BuildListRead,
  PartRead,
  PartReadWithVotes,
  UserRead,
} from '../types/Api';

const fetchSearchResultsRequestFn = (params: {
  q: string;
  skip?: number;
  limit?: number;
}) => searchApi.search(params);

function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState(
    () => searchParams.get('q') || ''
  );

  const queryFromUrl = searchParams.get('q') || '';
  useDocumentMeta({
    title: queryFromUrl ? `Search: ${queryFromUrl}` : 'Search',
    description: queryFromUrl
      ? `Search results on CarModPicker for "${queryFromUrl}" — builds, parts, and users matching your query.`
      : 'Search CarModPicker for builds, parts, and users across the community.',
    canonicalPath: '/search',
  });

  // Track accumulated results and pagination state for each category
  const [buildLists, setBuildLists] = useState<BuildListRead[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [parts, setParts] = useState<PartRead[]>([]);
  const [displayedCounts, setDisplayedCounts] = useState<{
    build_lists: number;
    users: number;
    parts: number;
  }>({
    build_lists: 0,
    users: 0,
    parts: 0,
  });
  const [pagination, setPagination] = useState<{
    build_lists: { has_next: boolean; skip: number };
    users: { has_next: boolean; skip: number };
    parts: { has_next: boolean; skip: number };
  } | null>(null);
  const [currentQuery, setCurrentQuery] = useState<string>(
    () => searchParams.get('q') || ''
  );

  const sortedSections = useMemo(() => {
    const sections: Array<'build_lists' | 'users' | 'parts'> = [
      'build_lists',
      'users',
      'parts',
    ];
    const counts = {
      build_lists: buildLists.length,
      users: users.length,
      parts: parts.length,
    };
    return [...sections].sort((a, b) => counts[b] - counts[a]);
  }, [buildLists.length, users.length, parts.length]);

  // Convert PartRead to PartReadWithVotes for PartList (adds vote defaults)
  const partsWithVotes = useMemo((): PartReadWithVotes[] => {
    const count =
      displayedCounts.parts ||
      Math.min(SEARCH_INITIAL_LIMITS.parts, parts.length);
    return parts.slice(0, count).map(
      (p): PartReadWithVotes => ({
        ...p,
        upvotes: 0,
        downvotes: 0,
        total_votes: 0,
        user_vote: null,
      })
    );
  }, [parts, displayedCounts.parts]);

  const {
    data: searchResults,
    isLoading,
    error,
    executeRequest: performSearch,
  } = useApiRequest(fetchSearchResultsRequestFn);

  const handleSearch = useCallback(() => {
    if (searchTerm.trim()) {
      const query = searchTerm.trim();
      setSearchParams({ q: query });
      setCurrentQuery(query);
      // Reset accumulated results for new search
      setBuildLists([]);
      setUsers([]);
      setParts([]);
      setDisplayedCounts({
        build_lists: 0,
        users: 0,
        parts: 0,
      });
      setPagination(null);
      void performSearch({ q: query, skip: 0, limit: SEARCH_RESULTS_LIMIT });
    }
  }, [searchTerm, setSearchParams, performSearch]);

  // Live search: debounce search as user types (300ms delay)
  useEffect(() => {
    const trimmed = searchTerm.trim();
    const timer = setTimeout(() => {
      if (trimmed) {
        setSearchParams({ q: trimmed });
      } else {
        setSearchParams({});
        setCurrentQuery('');
        setBuildLists([]);
        setUsers([]);
        setParts([]);
        setDisplayedCounts({
          build_lists: 0,
          users: 0,
          parts: 0,
        });
        setPagination(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, setSearchParams]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Load more results for a specific category
  const loadMore = useCallback(
    (category: 'build_lists' | 'users' | 'parts') => {
      if (!pagination || !currentQuery) return;

      // Check if we have more results already fetched that we haven't displayed
      const currentDisplayed = displayedCounts[category];
      let allResults: BuildListRead[] | UserRead[] | PartRead[] = [];

      if (category === 'build_lists') {
        allResults = buildLists;
      } else if (category === 'users') {
        allResults = users;
      } else {
        allResults = parts;
      }

      // If we have more results already fetched, just increase the displayed count
      if (currentDisplayed < allResults.length) {
        const increment =
          category === 'parts'
            ? SEARCH_LOAD_MORE_INCREMENT.parts
            : SEARCH_LOAD_MORE_INCREMENT.build_lists;
        setDisplayedCounts((prev) => ({
          ...prev,
          [category]: Math.min(currentDisplayed + increment, allResults.length),
        }));
      } else if (pagination[category].has_next) {
        // Otherwise, fetch more from the backend
        const currentSkip = pagination[category].skip;
        const limit = SEARCH_RESULTS_LIMIT;
        void performSearch({ q: currentQuery, skip: currentSkip, limit });
      }
    },
    [
      pagination,
      currentQuery,
      performSearch,
      displayedCounts,
      buildLists,
      users,
      parts,
    ]
  );

  // Update accumulated results when new search results arrive
  useEffect(() => {
    if (searchResults) {
      setCurrentQuery(searchResults.query);

      // If skip is 0, replace results (new search), otherwise append (load more)
      if (searchResults.build_lists.skip === 0) {
        setBuildLists(searchResults.build_lists.data);
        // Set initial displayed count to the limit or actual count, whichever is smaller
        setDisplayedCounts((prev) => ({
          ...prev,
          build_lists: Math.min(
            SEARCH_INITIAL_LIMITS.build_lists,
            searchResults.build_lists.data.length
          ),
        }));
      } else {
        setBuildLists((prev) => {
          const newList = [...prev, ...searchResults.build_lists.data];
          // When loading more, increase displayed count by the increment
          setDisplayedCounts((prevCounts) => ({
            ...prevCounts,
            build_lists: Math.min(
              prevCounts.build_lists + SEARCH_INITIAL_LIMITS.build_lists,
              newList.length
            ),
          }));
          return newList;
        });
      }

      if (searchResults.users.skip === 0) {
        setUsers(searchResults.users.data);
        // Set initial displayed count to the limit or actual count, whichever is smaller
        setDisplayedCounts((prev) => ({
          ...prev,
          users: Math.min(
            SEARCH_INITIAL_LIMITS.users,
            searchResults.users.data.length
          ),
        }));
      } else {
        setUsers((prev) => {
          const newList = [...prev, ...searchResults.users.data];
          // When loading more, increase displayed count by the increment
          setDisplayedCounts((prevCounts) => ({
            ...prevCounts,
            users: Math.min(
              prevCounts.users + SEARCH_INITIAL_LIMITS.users,
              newList.length
            ),
          }));
          return newList;
        });
      }

      if (searchResults.parts.skip === 0) {
        setParts(searchResults.parts.data);
        // Set initial displayed count to the limit or actual count, whichever is smaller
        setDisplayedCounts((prev) => ({
          ...prev,
          parts: Math.min(
            SEARCH_INITIAL_LIMITS.parts,
            searchResults.parts.data.length
          ),
        }));
      } else {
        setParts((prev) => {
          const newList = [...prev, ...searchResults.parts.data];
          // When loading more, increase displayed count by the increment
          setDisplayedCounts((prevCounts) => ({
            ...prevCounts,
            parts: Math.min(
              prevCounts.parts + SEARCH_INITIAL_LIMITS.parts,
              newList.length
            ),
          }));
          return newList;
        });
      }

      setPagination({
        build_lists: {
          has_next: searchResults.build_lists.has_next,
          skip:
            searchResults.build_lists.skip +
            searchResults.build_lists.data.length,
        },
        users: {
          has_next: searchResults.users.has_next,
          skip: searchResults.users.skip + searchResults.users.data.length,
        },
        parts: {
          has_next: searchResults.parts.has_next,
          skip: searchResults.parts.skip + searchResults.parts.data.length,
        },
      });
    }
  }, [searchResults]);

  // Perform search when query param changes (e.g., from URL)
  useEffect(() => {
    const query = searchParams.get('q');
    if (query && query.trim()) {
      setSearchTerm(query);
      setCurrentQuery(query);
      // Reset accumulated results
      setBuildLists([]);
      setUsers([]);
      setParts([]);
      setDisplayedCounts({
        build_lists: 0,
        users: 0,
        parts: 0,
      });
      setPagination(null);
      void performSearch({
        q: query.trim(),
        skip: 0,
        limit: SEARCH_RESULTS_LIMIT,
      });
    }
  }, [searchParams, performSearch]);

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Search" />

      {/* Search Input */}
      <Card className="mb-8">
        <div className="flex gap-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Search build lists, users, and parts..."
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

      {/* Loading State */}
      {isLoading && (
        <Card>
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        </Card>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <Card>
          <ErrorAlert message={`Search failed: ${error}`} />
        </Card>
      )}

      {/* Search Results (including "no results" state when currentQuery is set) */}
      {!isLoading && !error && currentQuery && (
        <>
          {sortedSections.map((section) => {
            if (section === 'build_lists') {
              return (
                <Card key="build_lists" className="mb-6">
                  <SectionHeader
                    title={`Build Lists (${pagination?.build_lists ? searchResults?.build_lists.total || buildLists.length : buildLists.length}${pagination?.build_lists ? ` of ${searchResults?.build_lists.total || 0}` : ''})`}
                  />
                  {buildLists.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>No build lists found.</p>
                    </div>
                  ) : (
                    <>
                      <div className="tile-grid-compact">
                        {buildLists
                          .slice(
                            0,
                            displayedCounts.build_lists ||
                              Math.min(
                                SEARCH_INITIAL_LIMITS.build_lists,
                                buildLists.length
                              )
                          )
                          .map((buildList) => (
                            <BuildListItem
                              key={buildList.id}
                              buildList={buildList}
                            />
                          ))}
                      </div>
                      {(pagination?.build_lists.has_next ||
                        displayedCounts.build_lists < buildLists.length) && (
                        <div className="mt-6 flex justify-center">
                          <Button
                            type="button"
                            onClick={() => loadMore('build_lists')}
                            disabled={isLoading}
                          >
                            {isLoading ? 'Loading...' : 'Load More Build Lists'}
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                </Card>
              );
            }

            if (section === 'users') {
              return (
                <Card key="users" className="mb-6">
                  <SectionHeader
                    title={`Users (${pagination?.users ? searchResults?.users.total || users.length : users.length}${pagination?.users ? ` of ${searchResults?.users.total || 0}` : ''})`}
                  />
                  {users.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>No users found.</p>
                    </div>
                  ) : (
                    <>
                      <div className="tile-grid-compact">
                        {users
                          .slice(
                            0,
                            displayedCounts.users ||
                              Math.min(
                                SEARCH_INITIAL_LIMITS.users,
                                users.length
                              )
                          )
                          .map((user) => (
                            <UserCard key={user.id} user={user} />
                          ))}
                      </div>
                      {(pagination?.users.has_next ||
                        displayedCounts.users < users.length) && (
                        <div className="mt-6 flex justify-center">
                          <Button
                            type="button"
                            onClick={() => loadMore('users')}
                            disabled={isLoading}
                          >
                            {isLoading ? 'Loading...' : 'Load More Users'}
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                </Card>
              );
            }

            return (
              <div key="parts" className="mb-6">
                <PartList
                  data={partsWithVotes}
                  layout="table"
                  title={`Parts (${pagination?.parts ? (searchResults?.parts.total ?? parts.length) : parts.length}${pagination?.parts ? ` of ${searchResults?.parts.total ?? 0}` : ''})`}
                  emptyMessage="No parts found."
                  categories={[]}
                  part_manufacturers={[]}
                  carsById={{}}
                />
                {(pagination?.parts.has_next ||
                  displayedCounts.parts < parts.length) && (
                  <div className="mt-6 flex justify-center">
                    <Button
                      type="button"
                      onClick={() => loadMore('parts')}
                      disabled={isLoading}
                    >
                      {isLoading ? 'Loading...' : 'Load More Parts'}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}

          {/* No Results Message */}
          {buildLists.length === 0 &&
            users.length === 0 &&
            parts.length === 0 &&
            currentQuery && (
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

      {/* Initial State (no search performed yet or search cleared) */}
      {!isLoading && !error && !currentQuery && (
        <Card>
          <div className="text-center py-12">
            <p className="text-xl text-muted-foreground mb-2">
              Enter a search term to find build lists, users, and parts
            </p>
            <p className="text-muted-foreground">
              Search across names, descriptions, part manufacturers, and more
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

export default Search;
