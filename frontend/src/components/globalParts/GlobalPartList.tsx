import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { globalPartVotesApi, globalPartsApi } from '../../services/Api';
import type { GlobalPartReadWithVotes, PaginationInfo } from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import VoteButtons from './VoteButtons';
import { CACHE_DURATION_MS } from '../../constants';

// Simple cache for global parts data to improve UX when switching between pages
interface CachedData {
  data: GlobalPartReadWithVotes[];
  pagination: PaginationInfo | null;
  timestamp: number;
}
const globalPartsCache = new Map<string, CachedData>();

function getCacheKey(params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  car_id?: number;
  search?: string;
}): string {
  return JSON.stringify(params || {});
}

function getCachedData(cacheKey: string): CachedData | null {
  const cached = globalPartsCache.get(cacheKey);
  if (!cached) return null;

  // Check if cache is still valid
  const now = Date.now();
  if (now - cached.timestamp > CACHE_DURATION_MS) {
    globalPartsCache.delete(cacheKey);
    return null;
  }

  return cached;
}

interface GlobalPartListProps {
  params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    car_id?: number;
    search?: string;
  };
  data?: GlobalPartReadWithVotes[]; // Optional: pass pre-fetched data instead of fetching
  pagination?: PaginationInfo | null; // Optional: pass pagination info when using pre-fetched data
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
  onAddToBuildList?: (globalPart: GlobalPartReadWithVotes) => void;
  showAddToBuildListButton?: boolean;
  onEdit?: (globalPart: GlobalPartReadWithVotes) => void;
  onDelete?: (globalPart: GlobalPartReadWithVotes) => void;
  canEdit?: (globalPart: GlobalPartReadWithVotes) => boolean;
  canDelete?: (globalPart: GlobalPartReadWithVotes) => boolean;
  onPaginationChange?: (pagination: PaginationInfo | null) => void;
}

const fetchGlobalPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  car_id?: number;
  search?: string;
}) => globalPartsApi.getGlobalPartsWithVotes(params);

function GlobalPartList({
  params,
  data: providedData,
  pagination: providedPagination,
  refreshKey = 0,
  title = 'Parts Catalog',
  emptyMessage = 'No parts found.',
  showVoteButtons = false,
  onVoteUpdate,
  onAddToBuildList,
  showAddToBuildListButton = false,
  onEdit,
  onDelete,
  canEdit,
  canDelete,
  onPaginationChange,
}: GlobalPartListProps) {
  const {
    data: paginatedResponse,
    isLoading,
    error,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  // Initialize with cached data if available (for instant display)
  const cacheKey = getCacheKey(params);
  const [displayData, setDisplayData] = useState<GlobalPartReadWithVotes[]>(
    () => {
      if (providedData) return providedData;
      const cached = getCachedData(cacheKey);
      return cached?.data ?? [];
    }
  );
  const [displayPagination, setDisplayPagination] =
    useState<PaginationInfo | null>(() => {
      if (providedPagination) return providedPagination;
      const cached = getCachedData(cacheKey);
      return cached?.pagination ?? null;
    });

  const memoizedFetchGlobalParts = useCallback(() => {
    void fetchGlobalParts(params);
  }, [fetchGlobalParts, params]);

  // Only fetch if data is not provided
  useEffect(() => {
    if (!providedData) {
      // Check cache first - if we have cached data, show it immediately and fetch in background
      const cached = getCachedData(cacheKey);
      if (cached) {
        setDisplayData(cached.data);
        setDisplayPagination(cached.pagination);
      }
      // Always fetch fresh data in background
      memoizedFetchGlobalParts();
    }
  }, [memoizedFetchGlobalParts, refreshKey, providedData, cacheKey]);

  // Update display data when fresh data arrives
  useEffect(() => {
    if (paginatedResponse?.data) {
      setDisplayData(paginatedResponse.data);
      setDisplayPagination(paginatedResponse.pagination ?? null);
      // Update cache
      globalPartsCache.set(cacheKey, {
        data: paginatedResponse.data,
        pagination: paginatedResponse.pagination ?? null,
        timestamp: Date.now(),
      });
    }
  }, [paginatedResponse, cacheKey]);

  // Track previous pagination to prevent unnecessary updates
  const prevPaginationRef = useRef<PaginationInfo | null>(null);

  // Notify parent of pagination info when data changes
  useEffect(() => {
    const currentPagination = providedPagination ?? displayPagination;

    // Only notify if pagination actually changed
    if (
      onPaginationChange &&
      JSON.stringify(prevPaginationRef.current) !==
        JSON.stringify(currentPagination)
    ) {
      prevPaginationRef.current = currentPagination;
      onPaginationChange(currentPagination);
    }
  }, [displayPagination, providedPagination, onPaginationChange]);

  // Use provided data if available, otherwise use display data (from cache or fresh fetch)
  const isLoadingState = providedData
    ? false
    : isLoading && displayData.length === 0;
  const errorState = providedData ? null : error;
  const globalParts = providedData ?? displayData;

  if (isLoadingState) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (errorState) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${errorState}`} />
      </Card>
    );
  }

  return (
    <Card>
      {title && (
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
        </div>
      )}

      {!globalParts || globalParts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {globalParts.map((globalPart) => (
            <div
              key={globalPart.id}
              className="bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500 transition-colors"
            >
              <div className="flex flex-row items-center gap-4 p-3">
                {/* Image */}
                <Link
                  to={`/global-parts/${globalPart.id}`}
                  className="flex-shrink-0"
                >
                  <div className="w-20 h-20">
                    <ImageWithPlaceholder
                      srcUrl={globalPart.image_url ?? null}
                      altText={globalPart.name}
                      imageClassName="w-full h-full object-cover rounded"
                      containerClassName="w-full h-full flex justify-center items-center"
                      fallbackText="No image"
                    />
                  </div>
                </Link>

                {/* Main Content */}
                <div className="flex-grow min-w-0">
                  <Link
                    to={`/global-parts/${globalPart.id}`}
                    className="block hover:no-underline"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-grow min-w-0">
                        <h3 className="text-base font-semibold text-gray-200 mb-1 truncate">
                          {globalPart.name}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                          {globalPart.brand && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">Brand:</span>{' '}
                              {globalPart.brand}
                            </span>
                          )}
                          {globalPart.part_number && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">P/N:</span>{' '}
                              {globalPart.part_number}
                            </span>
                          )}
                        </div>
                        {globalPart.description && (
                          <p className="text-sm text-gray-400 mt-1 line-clamp-1">
                            {globalPart.description}
                          </p>
                        )}
                      </div>
                      {globalPart.best_price_cents != null && (
                        <div className="flex-shrink-0 text-right">
                          <p className="text-base font-semibold text-green-400">
                            ${(globalPart.best_price_cents / 100).toFixed(2)}
                          </p>
                        </div>
                      )}
                    </div>
                  </Link>

                  {/* Actions Row */}
                  <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-gray-700">
                    {/* Left side: Vote Buttons */}
                    <div className="flex items-center gap-2">
                      {showVoteButtons && onVoteUpdate && (
                        <VoteButtons
                          entityId={globalPart.id}
                          upvotes={globalPart.upvotes}
                          downvotes={globalPart.downvotes}
                          userVote={globalPart.user_vote ?? null}
                          onVoteUpdate={onVoteUpdate}
                          voteApi={{
                            voteOnEntity: (id, data) =>
                              globalPartVotesApi.voteOnGlobalPart(id, data),
                            removeVote: (id) =>
                              globalPartVotesApi.removeVote(id),
                          }}
                        />
                      )}
                    </div>

                    {/* Right side: Action Buttons */}
                    <div className="flex items-center gap-2">
                      {/* Add to Build List Button */}
                      {showAddToBuildListButton && onAddToBuildList && (
                        <ActionButton
                          onClick={() => onAddToBuildList(globalPart)}
                          className="text-xs px-3 py-1"
                        >
                          📋 Add to Build List
                        </ActionButton>
                      )}

                      {/* Edit Button */}
                      {onEdit && (!canEdit || canEdit(globalPart)) && (
                        <SecondaryButton
                          onClick={() => onEdit(globalPart)}
                          className="text-xs px-3 py-1"
                        >
                          Edit
                        </SecondaryButton>
                      )}

                      {/* Delete Button */}
                      {onDelete && (!canDelete || canDelete(globalPart)) && (
                        <ActionButton
                          onClick={() => onDelete(globalPart)}
                          className="text-xs px-3 py-1 bg-red-600 hover:bg-red-700"
                        >
                          Delete
                        </ActionButton>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default GlobalPartList;
