import { useCallback, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { globalPartsApi } from '../../services/Api';
import type { GlobalPartReadWithVotes, PaginationInfo } from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import VoteButtons from './VoteButtons';

interface GlobalPartListProps {
  params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  };
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
  onPaginationChange?: (pagination: PaginationInfo | null) => void;
}

const fetchGlobalPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  search?: string;
}) => globalPartsApi.getGlobalPartsWithVotes(params);

function GlobalPartList({
  params,
  refreshKey = 0,
  title = 'Parts Catalog',
  emptyMessage = 'No parts found.',
  showVoteButtons = false,
  onVoteUpdate,
  onAddToBuildList,
  showAddToBuildListButton = false,
  onPaginationChange,
}: GlobalPartListProps) {
  const {
    data: paginatedResponse,
    isLoading,
    error,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  const memoizedFetchGlobalParts = useCallback(() => {
    void fetchGlobalParts(params);
  }, [fetchGlobalParts, params]);

  useEffect(() => {
    memoizedFetchGlobalParts();
  }, [memoizedFetchGlobalParts, refreshKey]);

  // Track previous pagination to prevent unnecessary updates
  const prevPaginationRef = useRef<PaginationInfo | null>(null);

  // Notify parent of pagination info when data changes
  useEffect(() => {
    const currentPagination = paginatedResponse?.pagination ?? null;

    // Only notify if pagination actually changed
    if (
      onPaginationChange &&
      JSON.stringify(prevPaginationRef.current) !==
        JSON.stringify(currentPagination)
    ) {
      prevPaginationRef.current = currentPagination;
      onPaginationChange(currentPagination);
    }
  }, [paginatedResponse, onPaginationChange]);

  if (isLoading) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${error}`} />
      </Card>
    );
  }

  const globalParts = paginatedResponse?.data ?? [];

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
      </div>

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
                      {globalPart.price !== null &&
                        globalPart.price !== undefined && (
                          <div className="flex-shrink-0 text-right">
                            <p className="text-base font-semibold text-green-400">
                              ${globalPart.price.toFixed(2)}
                            </p>
                          </div>
                        )}
                    </div>
                  </Link>

                  {/* Actions Row */}
                  <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-gray-700">
                    {/* Vote Buttons */}
                    {showVoteButtons && onVoteUpdate && (
                      <VoteButtons
                        partId={globalPart.id}
                        upvotes={globalPart.upvotes}
                        downvotes={globalPart.downvotes}
                        userVote={globalPart.user_vote ?? null}
                        onVoteUpdate={onVoteUpdate}
                      />
                    )}
                    {!showVoteButtons && <div />}

                    {/* Add to Build List Button */}
                    {showAddToBuildListButton && onAddToBuildList && (
                      <ActionButton
                        onClick={() => onAddToBuildList(globalPart)}
                        className="text-xs px-3 py-1"
                      >
                        📋 Add to Build List
                      </ActionButton>
                    )}
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
