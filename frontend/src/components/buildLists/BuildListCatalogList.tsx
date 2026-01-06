import { useCallback, useEffect } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi } from '../../services/Api';

import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import BuildListItem from './BuildListItem';

interface BuildListCatalogListProps {
  params?: {
    skip?: number;
    limit?: number;
    search?: string;
  };
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  search?: string;
}) => buildListsApi.listBuildLists(params);

function BuildListCatalogList({
  params,
  refreshKey = 0,
  title = 'Build Lists Catalog',
  emptyMessage = 'No build lists found.',
}: BuildListCatalogListProps) {
  const {
    data: buildLists,
    isLoading,
    error,
    executeRequest: fetchBuildLists,
  } = useApiRequest(fetchBuildListsRequestFn);

  const memoizedFetchBuildLists = useCallback(() => {
    void fetchBuildLists(params);
  }, [fetchBuildLists, params]);

  useEffect(() => {
    memoizedFetchBuildLists();
  }, [memoizedFetchBuildLists, refreshKey]);

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
        <ErrorAlert message={`Failed to load build lists: ${error}`} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
      </div>

      {!buildLists || buildLists.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {buildLists.map((buildList) => (
            <BuildListItem key={buildList.id} buildList={buildList} />
          ))}
        </div>
      )}
    </Card>
  );
}

export default BuildListCatalogList;
