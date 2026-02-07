import { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi } from '../../services/Api';
import type {
  BuildListRead,
  BuildListReadWithVotes,
  PaginatedResponse,
} from '../../types/Api';

import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import BuildListCard from './BuildListCard';
import BuildListItem from './BuildListItem';
import { LARGE_FETCH_LIMIT } from '../../constants';

interface BuildListCatalogListProps {
  params?: {
    skip?: number;
    limit?: number;
    search?: string;
  };
  carIds?: number[]; // Optional: filter by car IDs
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  /** When 'card', renders build cards with image previews (Home-style). Default 'list'. */
  layout?: 'card' | 'list';
}

const fetchBuildListsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  search?: string;
  car_id?: number;
}) => buildListsApi.getBuildListsWithVotes(params);

// Type predicate to check if response is a PaginatedResponse
function isPaginatedResponse<T>(
  response: unknown
): response is PaginatedResponse<T> {
  return (
    typeof response === 'object' &&
    response !== null &&
    'data' in response &&
    Array.isArray((response as { data: unknown }).data) &&
    'pagination' in response
  );
}

function BuildListCatalogList({
  params,
  carIds,
  refreshKey = 0,
  title = 'Build Lists Catalog',
  emptyMessage = 'No build lists found.',
  showVoteButtons = false,
  layout = 'list',
}: BuildListCatalogListProps) {
  const [allBuildLists, setAllBuildLists] = useState<BuildListRead[]>([]);
  const [isLoadingMultiple, setIsLoadingMultiple] = useState(false);
  const [errorMultiple, setErrorMultiple] = useState<string | null>(null);
  const [buildListsWithVotes, setBuildListsWithVotes] = useState<
    BuildListReadWithVotes[]
  >([]);

  // Use standard fetch when no carIds are provided
  const {
    data: buildListsResponse,
    isLoading,
    error,
    executeRequest: fetchBuildLists,
  } = useApiRequest<
    PaginatedResponse<BuildListReadWithVotes>,
    { skip?: number; limit?: number; search?: string; car_id?: number }
  >(fetchBuildListsRequestFn);

  // Update buildListsWithVotes when response changes
  useEffect(() => {
    if (isPaginatedResponse<BuildListReadWithVotes>(buildListsResponse)) {
      // Extract the array from PaginatedResponse

      setBuildListsWithVotes(buildListsResponse.data);
    } else if (buildListsResponse === null) {
      // If response is null, clear the votes list
      setBuildListsWithVotes([]);
    }
  }, [buildListsResponse]);

  // Fetch build lists for multiple cars
  const fetchBuildListsForCars = useCallback(async () => {
    if (!carIds || carIds.length === 0) {
      return;
    }

    setIsLoadingMultiple(true);
    setErrorMultiple(null);

    try {
      // Fetch build lists for all selected cars in parallel
      const promises = carIds.map(
        (carId) =>
          buildListsApi
            .getBuildListsByCar(carId, { limit: LARGE_FETCH_LIMIT })
            .then((response) => response.data.data) // Extract the array from PaginatedResponse
      );

      const results = await Promise.all(promises);
      // Combine all build lists and remove duplicates (in case a build list is associated with multiple car generations)
      const combined = results.flat();
      const uniqueBuildLists = Array.from(
        new Map(combined.map((bl) => [bl.id, bl])).values()
      );

      setAllBuildLists(uniqueBuildLists);
    } catch (err) {
      setErrorMultiple(
        err instanceof Error ? err.message : 'Failed to fetch build lists'
      );
    } finally {
      setIsLoadingMultiple(false);
    }
  }, [carIds]);

  const handleVoteUpdate = useCallback(
    (buildListId: number, newVote: 'upvote' | 'downvote' | null) => {
      // Update local state optimistically
      setBuildListsWithVotes((prev) =>
        prev.map((bl) => {
          if (bl.id === buildListId) {
            let newUpvotes = bl.upvotes;
            let newDownvotes = bl.downvotes;

            // Remove previous vote
            if (bl.user_vote === 'upvote') {
              newUpvotes -= 1;
            } else if (bl.user_vote === 'downvote') {
              newDownvotes -= 1;
            }

            // Add new vote
            if (newVote === 'upvote') {
              newUpvotes += 1;
            } else if (newVote === 'downvote') {
              newDownvotes += 1;
            }

            return {
              ...bl,
              upvotes: newUpvotes,
              downvotes: newDownvotes,
              total_votes: newUpvotes + newDownvotes,
              user_vote: newVote,
            };
          }
          return bl;
        })
      );
    },
    []
  );

  const memoizedFetchBuildLists = useCallback(() => {
    if (carIds && carIds.length > 0) {
      if (carIds.length === 1) {
        // Use with-votes endpoint for single car (vote counts for cards)
        void fetchBuildLists({
          ...params,
          car_id: carIds[0] as number,
        });
      } else {
        void fetchBuildListsForCars();
      }
    } else {
      void fetchBuildLists(params);
    }
  }, [fetchBuildLists, fetchBuildListsForCars, params, carIds]);

  // Refetch when params (including search) or carIds change
  useEffect(() => {
    memoizedFetchBuildLists();
  }, [memoizedFetchBuildLists, refreshKey]);

  // Filter build lists by search term if provided
  // When showVoteButtons is true and we have a single car, we use the with-votes endpoint
  // which populates buildListsWithVotes. Otherwise, use allBuildLists for multiple cars
  // or buildListsResponse for no carIds.
  let filteredBuildLists: (BuildListRead | BuildListReadWithVotes)[] = [];
  if (carIds && carIds.length > 0) {
    if (carIds.length === 1) {
      // Single car: we used with-votes endpoint - data is in buildListsWithVotes
      filteredBuildLists = buildListsWithVotes;
    } else {
      // Multiple cars: data is in allBuildLists
      filteredBuildLists = allBuildLists;
    }
  } else {
    // No carIds - use buildListsResponse
    if (showVoteButtons) {
      filteredBuildLists = buildListsWithVotes;
    } else {
      // Extract the array from PaginatedResponse
      if (isPaginatedResponse<BuildListReadWithVotes>(buildListsResponse)) {
        filteredBuildLists = buildListsResponse.data;
      } else {
        filteredBuildLists = [];
      }
    }
  }
  const searchTerm = params?.search?.toLowerCase() || '';
  const finalBuildLists = searchTerm
    ? filteredBuildLists.filter(
        (bl) =>
          bl.name?.toLowerCase().includes(searchTerm) ||
          bl.description?.toLowerCase().includes(searchTerm)
      )
    : filteredBuildLists;

  const isLoadingState =
    carIds && carIds.length > 0
      ? carIds.length === 1
        ? isLoading
        : isLoadingMultiple
      : isLoading;
  const errorState =
    carIds && carIds.length > 0
      ? carIds.length === 1
        ? error
        : errorMultiple
      : error;

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
        <ErrorAlert message={`Failed to load build lists: ${errorState}`} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
      </div>

      {finalBuildLists.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : layout === 'card' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {finalBuildLists.map((buildList) => (
            <BuildListCard key={buildList.id} buildList={buildList} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {finalBuildLists.map((buildList) => {
            const props: {
              buildList: BuildListRead | BuildListReadWithVotes;
              showVoteButtons: boolean;
              onVoteUpdate?: (
                buildListId: number,
                newVote: 'upvote' | 'downvote' | null
              ) => void;
            } = {
              buildList,
              showVoteButtons,
            };
            if (showVoteButtons) {
              props.onVoteUpdate = handleVoteUpdate;
            }
            return <BuildListItem key={buildList.id} {...props} />;
          })}
        </div>
      )}
    </Card>
  );
}

export default BuildListCatalogList;
