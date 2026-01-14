import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import BuildListItem from '../components/buildLists/BuildListItem';
import ActionButton from '../components/buttons/ActionButton';
import { ErrorAlert } from '../components/common/Alerts';
import Card from '../components/common/Card';
import ImageWithPlaceholder from '../components/common/ImageWithPlaceholder';
import LoadingSpinner from '../components/common/LoadingSpinner';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import UserCard from '../components/users/UserCard';
import useApiRequest from '../hooks/UseApiRequest';
import { searchApi } from '../services/Api';
import type { BuildListRead, GlobalPartRead, UserRead } from '../types/Api';

const fetchSearchResultsRequestFn = (params: {
  q: string;
  skip?: number;
  limit?: number;
}) => searchApi.search(params);

function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [searchTerm, setSearchTerm] = useState(initialQuery);

  // Track accumulated results and pagination state for each category
  const [buildLists, setBuildLists] = useState<BuildListRead[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [globalParts, setGlobalParts] = useState<GlobalPartRead[]>([]);
  const [pagination, setPagination] = useState<{
    build_lists: { has_next: boolean; skip: number };
    users: { has_next: boolean; skip: number };
    global_parts: { has_next: boolean; skip: number };
  } | null>(null);
  const [currentQuery, setCurrentQuery] = useState<string>('');

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
      setGlobalParts([]);
      setPagination(null);
      void performSearch({ q: query, skip: 0, limit: 20 });
    }
  }, [searchTerm, setSearchParams, performSearch]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Load more results for a specific category
  // Note: Backend uses same skip/limit for all categories, so we'll load next page for all
  const loadMore = useCallback(
    (category: 'build_lists' | 'users' | 'global_parts') => {
      if (!pagination || !currentQuery) return;

      // Use the skip value from the category we're loading more for
      const currentSkip = pagination[category].skip;
      const limit = 20;

      void performSearch({ q: currentQuery, skip: currentSkip, limit });
    },
    [pagination, currentQuery, performSearch]
  );

  // Update accumulated results when new search results arrive
  useEffect(() => {
    if (searchResults) {
      setCurrentQuery(searchResults.query);

      // If skip is 0, replace results (new search), otherwise append (load more)
      if (searchResults.build_lists.skip === 0) {
        setBuildLists(searchResults.build_lists.data);
      } else {
        setBuildLists((prev) => [...prev, ...searchResults.build_lists.data]);
      }

      if (searchResults.users.skip === 0) {
        setUsers(searchResults.users.data);
      } else {
        setUsers((prev) => [...prev, ...searchResults.users.data]);
      }

      if (searchResults.global_parts.skip === 0) {
        setGlobalParts(searchResults.global_parts.data);
      } else {
        setGlobalParts((prev) => [...prev, ...searchResults.global_parts.data]);
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
        global_parts: {
          has_next: searchResults.global_parts.has_next,
          skip:
            searchResults.global_parts.skip +
            searchResults.global_parts.data.length,
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
      setGlobalParts([]);
      setPagination(null);
      void performSearch({ q: query.trim(), skip: 0, limit: 20 });
    }
  }, [searchParams, performSearch]);

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Search" />

      {/* Search Input */}
      <Card className="mb-8">
        <div className="flex gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search build lists, users, and parts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-4 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="button"
            onClick={handleSearch}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors font-medium"
          >
            Search
          </button>
        </div>
      </Card>

      {/* Loading State */}
      {isLoading && (
        <Card>
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        </Card>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <Card>
          <ErrorAlert message={`Search failed: ${error}`} />
        </Card>
      )}

      {/* Search Results */}
      {!isLoading &&
        !error &&
        (searchResults ||
          buildLists.length > 0 ||
          users.length > 0 ||
          globalParts.length > 0) && (
          <>
            {/* Build Lists Results */}
            <Card className="mb-6">
              <SectionHeader
                title={`Build Lists (${pagination?.build_lists ? searchResults?.build_lists.total || buildLists.length : buildLists.length}${pagination?.build_lists ? ` of ${searchResults?.build_lists.total || 0}` : ''})`}
              />
              {buildLists.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <p>No build lists found.</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    {buildLists.map((buildList) => (
                      <BuildListItem key={buildList.id} buildList={buildList} />
                    ))}
                  </div>
                  {pagination?.build_lists.has_next && (
                    <div className="mt-6 flex justify-center">
                      <ActionButton
                        onClick={() => loadMore('build_lists')}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Loading...' : 'Load More Build Lists'}
                      </ActionButton>
                    </div>
                  )}
                </>
              )}
            </Card>

            {/* Users Results */}
            <Card className="mb-6">
              <SectionHeader
                title={`Users (${pagination?.users ? searchResults?.users.total || users.length : users.length}${pagination?.users ? ` of ${searchResults?.users.total || 0}` : ''})`}
              />
              {users.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <p>No users found.</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    {users.map((user) => (
                      <UserCard key={user.id} user={user} />
                    ))}
                  </div>
                  {pagination?.users.has_next && (
                    <div className="mt-6 flex justify-center">
                      <ActionButton
                        onClick={() => loadMore('users')}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Loading...' : 'Load More Users'}
                      </ActionButton>
                    </div>
                  )}
                </>
              )}
            </Card>

            {/* Parts Results */}
            <Card className="mb-6">
              <SectionHeader
                title={`Parts (${pagination?.global_parts ? searchResults?.global_parts.total || globalParts.length : globalParts.length}${pagination?.global_parts ? ` of ${searchResults?.global_parts.total || 0}` : ''})`}
              />
              {globalParts.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <p>No parts found.</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {globalParts.map((globalPart: GlobalPartRead) => (
                      <div
                        key={globalPart.id}
                        className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-indigo-500 transition-colors"
                      >
                        <Link
                          to={`/global-parts/${globalPart.id}`}
                          className="block group"
                        >
                          <div className="aspect-square mb-3">
                            <ImageWithPlaceholder
                              srcUrl={globalPart.image_url ?? null}
                              altText={globalPart.name}
                              imageClassName="w-full h-full object-cover rounded"
                              containerClassName="w-full h-full flex justify-center items-center"
                              fallbackText="No image"
                            />
                          </div>
                          <h3 className="text-lg font-semibold text-gray-200 mb-2">
                            {globalPart.name}
                          </h3>
                          {globalPart.brand && (
                            <p className="text-sm text-gray-400 mb-1">
                              Brand: {globalPart.brand}
                            </p>
                          )}
                          {globalPart.part_number && (
                            <p className="text-sm text-gray-400 mb-1">
                              Part #: {globalPart.part_number}
                            </p>
                          )}
                          {globalPart.price !== null &&
                            globalPart.price !== undefined && (
                              <p className="text-sm font-medium text-green-400">
                                ${globalPart.price.toFixed(2)}
                              </p>
                            )}
                          {globalPart.description && (
                            <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                              {globalPart.description}
                            </p>
                          )}
                        </Link>
                      </div>
                    ))}
                  </div>
                  {pagination?.global_parts.has_next && (
                    <div className="mt-6 flex justify-center">
                      <ActionButton
                        onClick={() => loadMore('global_parts')}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Loading...' : 'Load More Parts'}
                      </ActionButton>
                    </div>
                  )}
                </>
              )}
            </Card>

            {/* No Results Message */}
            {buildLists.length === 0 &&
              users.length === 0 &&
              globalParts.length === 0 &&
              currentQuery && (
                <Card>
                  <div className="text-center py-12">
                    <p className="text-xl text-gray-400 mb-2">
                      No results found for "{currentQuery}"
                    </p>
                    <p className="text-gray-500">
                      Try different search terms or check your spelling.
                    </p>
                  </div>
                </Card>
              )}
          </>
        )}

      {/* Initial State (no search performed yet) */}
      {!isLoading && !error && !searchResults && (
        <Card>
          <div className="text-center py-12">
            <p className="text-xl text-gray-400 mb-2">
              Enter a search term to find build lists, users, and parts
            </p>
            <p className="text-gray-500">
              Search across names, descriptions, brands, and more
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

export default Search;
