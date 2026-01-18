import React, { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient from '../../services/Api';
import type { BuildListRead } from '../../types/Api';
import AddItemTile from '../common/AddItemTile';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import BuildListItem from './BuildListItem';
interface BuildListListProps {
  carId: number;
  currentUserId?: number; // Logged-in user's ID (optional, for display purposes)
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddBuildListClick?: () => void; // Callback to open create form
}

const BuildListList: React.FC<BuildListListProps> = ({
  carId,
  currentUserId,
  refreshKey,
  title = 'Build Lists',
  emptyMessage = 'No build lists found for this car.',
  onAddBuildListClick,
}) => {
  const [internalBuildLists, setInternalBuildLists] = useState<
    BuildListRead[] | null
  >(null);

  const fetchBuildListsByCarIdRequestFn = useCallback(
    (id: number) => apiClient.get<BuildListRead[]>(`/build-lists/car/${id}`),
    []
  );

  const {
    data: fetchedApiBuildLists,
    isLoading,
    error,
    executeRequest: fetchCarBuildLists,
  } = useApiRequest(fetchBuildListsByCarIdRequestFn);

  useEffect(() => {
    void fetchCarBuildLists(carId);
  }, [carId, fetchCarBuildLists, refreshKey]);

  useEffect(() => {
    if (fetchedApiBuildLists) {
      setInternalBuildLists(fetchedApiBuildLists);
    } else if (!isLoading && !error) {
      setInternalBuildLists([]);
    }
  }, [fetchedApiBuildLists, isLoading, error]);

  const canAddBuildList = onAddBuildListClick !== undefined;

  if (isLoading) {
    return (
      <>
        <SectionHeader title={title} />
        <LoadingSpinner />
      </>
    );
  }

  if (error) {
    return (
      <>
        <SectionHeader title={title} />
        <ErrorAlert message={error} />
      </>
    );
  }

  const noBuildListsToShow =
    !internalBuildLists || internalBuildLists.length === 0;

  return (
    <div>
      <SectionHeader title={title} />
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 mt-4">
        {canAddBuildList && (
          <AddItemTile
            title="Create New Build List"
            description="Click here to start a new build list for this car."
            onClick={onAddBuildListClick}
          />
        )}
        {internalBuildLists &&
          internalBuildLists.map((buildList) => (
            <BuildListItem key={buildList.id} buildList={buildList} />
          ))}
      </div>
      {noBuildListsToShow && (
        <p className="text-gray-400 mt-4">
          {canAddBuildList
            ? 'This car has no build lists yet. Click the tile above to create one!'
            : emptyMessage}
        </p>
      )}
    </div>
  );
};

export default BuildListList;
