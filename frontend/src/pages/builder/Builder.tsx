import { useCallback, useEffect, useState } from 'react';
import BuildListItem from '../../components/buildLists/BuildListItem';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import AddItemTile from '../../components/common/AddItemTile';
import { ErrorAlert } from '../../components/common/Alerts';
import Dialog from '../../components/common/Dialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListsApi } from '../../services/Api';
import type { BuildListRead } from '../../types/Api';

function Builder() {
  const { user } = useAuth();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [formKey, setFormKey] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;
  const [totalItems, setTotalItems] = useState<number | null>(null);
  const isFirstPage = currentPage === 1;
  // On first page: create button (1) + 7 build lists = 8 items
  // On other pages: 8 build lists = 8 items
  const buildListsPerPage = isFirstPage ? 7 : 8;

  // Fetch user's build lists with pagination
  const fetchMyBuildListsFn = useCallback(() => {
    // Calculate skip: page 1 = 0, page 2 = 7, page 3 = 15, page 4 = 23, etc.
    const skip = isFirstPage ? 0 : 7 + (currentPage - 2) * 8;
    return buildListsApi.getMyBuildLists({
      skip,
      limit: buildListsPerPage,
    });
  }, [currentPage, isFirstPage, buildListsPerPage]);

  const {
    data: buildListsResponse,
    isLoading,
    error,
    executeRequest: fetchMyBuildLists,
  } = useApiRequest(fetchMyBuildListsFn);

  // Extract build lists and total from paginated response
  const buildLists = buildListsResponse?.data || [];
  const totalBuildLists = buildListsResponse?.pagination?.total_items ?? 0;

  // Calculate total items: build lists + 1 for the create button on page 1
  useEffect(() => {
    if (buildListsResponse) {
      // Total items = total build lists + 1 (for the create button on page 1)
      setTotalItems(totalBuildLists + 1);
    }
  }, [buildListsResponse, totalBuildLists]);

  useEffect(() => {
    if (user) {
      void fetchMyBuildLists();
    }
  }, [user, fetchMyBuildLists, refreshTrigger, currentPage]);

  const handleBuildListCreated = (newBuildList: BuildListRead) => {
    // Refresh the list after creation and reset to first page
    void newBuildList;
    setCurrentPage(1);
    setTotalItems(null);
    setRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false);
  };

  const openCreateBuildListDialog = () => {
    setFormKey((prev) => prev + 1);
    setIsCreateBuildListFormOpen(true);
  };

  const closeCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(false);
  };

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader
          title="Builder"
          subtitle="Please log in to view and manage your build lists."
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Builder"
        subtitle="Manage your build lists and create new ones for your projects."
      />

      <Dialog
        isOpen={isCreateBuildListFormOpen}
        onClose={closeCreateBuildListDialog}
        title="Create New Build List"
        maxWidth="4xl"
      >
        <CreateBuildListForm
          key={formKey}
          onBuildListCreated={handleBuildListCreated}
        />
      </Dialog>

      {isLoading ? (
        <div className="mt-8">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <div className="mt-8">
          <ErrorAlert message={error} />
        </div>
      ) : (
        <div className="mt-8">
          <SectionHeader title="My Build Lists" />
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 mt-4">
            {isFirstPage && (
              <AddItemTile
                title="Create New Build List"
                description="Click here to start a new build list for your project."
                onClick={openCreateBuildListDialog}
              />
            )}
            {buildLists && buildLists.length > 0 ? (
              buildLists.map((buildList) => (
                <BuildListItem key={buildList.id} buildList={buildList} />
              ))
            ) : isFirstPage ? (
              <div className="col-span-full text-center py-8 text-gray-400">
                <p className="mb-4">
                  You don't have any build lists yet. Click the tile above to
                  create your first one!
                </p>
              </div>
            ) : null}
          </div>
          {totalItems !== null && totalItems > itemsPerPage && (
            <Pagination
              currentPage={currentPage}
              totalPages={Math.ceil(totalItems / itemsPerPage)}
              onPageChange={(page) => {
                setCurrentPage(page);
                // Scroll to top when page changes
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              itemsPerPage={itemsPerPage}
              totalItems={totalItems}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default Builder;
