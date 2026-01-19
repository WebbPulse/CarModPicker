import { useCallback, useEffect, useState } from 'react';
import BuildListItem from '../../components/buildLists/BuildListItem';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import AddItemTile from '../../components/common/AddItemTile';
import { ErrorAlert } from '../../components/common/Alerts';
import Dialog from '../../components/common/Dialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
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

  // Fetch user's build lists
  const fetchMyBuildListsFn = useCallback(
    () => buildListsApi.getMyBuildLists({ limit: 1000 }),
    []
  );

  const {
    data: buildLists,
    isLoading,
    error,
    executeRequest: fetchMyBuildLists,
  } = useApiRequest(fetchMyBuildListsFn);

  useEffect(() => {
    if (user) {
      void fetchMyBuildLists();
    }
  }, [user, fetchMyBuildLists, refreshTrigger]);

  const handleBuildListCreated = (newBuildList: BuildListRead) => {
    // Refresh the list after creation
    void newBuildList;
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
            <AddItemTile
              title="Create New Build List"
              description="Click here to start a new build list for your project."
              onClick={openCreateBuildListDialog}
            />
            {buildLists && buildLists.length > 0 ? (
              buildLists.map((buildList) => (
                <BuildListItem key={buildList.id} buildList={buildList} />
              ))
            ) : (
              <div className="col-span-full text-center py-8 text-gray-400">
                <p className="mb-4">
                  You don't have any build lists yet. Click the tile above to
                  create your first one!
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Builder;
