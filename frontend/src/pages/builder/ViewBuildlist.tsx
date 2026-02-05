import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import apiClient, { buildListVotesApi } from '../../services/Api';
import type {
  BuildListRead,
  CarRead,
  UserRead,
  VoteSummary,
} from '../../types/Api';

import BuildListParts from '../../components/buildListParts/BuildListParts';
import CreateBuildListPartForm from '../../components/buildListParts/CreateBuildListPartForm';
import EditBuildListForm from '../../components/buildLists/EditBuildListForm';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import CardInfoItem from '../../components/common/CardInfoItem';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import ImageGallery from '../../components/globalParts/ImageGallery';
import VoteButtons from '../../components/globalParts/VoteButtons';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchBuildListRequestFn = (buildListId: string) =>
  apiClient.get<BuildListRead>(`/build-lists/${buildListId}`);

const fetchCarRequestFn = (carId: number) =>
  apiClient.get<CarRead>(`/cars/${carId}`);

const fetchUserRequestFn = (userId: number) =>
  apiClient.get<UserRead>(`/users/${userId}`);

const fetchVoteSummaryRequestFn = (buildListId: string) =>
  buildListVotesApi.getVoteSummary(Number(buildListId));

const deleteBuildListRequestFn = (buildListId: string) =>
  apiClient.delete<Record<string, string>>(`/build-lists/${buildListId}`);

function ViewBuildList() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditBuildListFormOpen, setIsEditBuildListFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] =
    useState<boolean>(false);
  const [associatedCar, setAssociatedCar] = useState<CarRead | null>(null);
  const [buildListOwner, setBuildListOwner] = useState<UserRead | null>(null);
  const [partsRefreshTrigger, setPartsRefreshTrigger] = useState<number>(0);
  const [isCreatePartFormOpen, setIsCreatePartFormOpen] = useState(false);
  const [voteSummary, setVoteSummary] = useState<VoteSummary | null>(null);

  const {
    data: buildList,
    isLoading: isLoadingBuildList,
    error: buildListApiError,
    executeRequest: fetchBuildList,
  } = useApiRequest(fetchBuildListRequestFn);

  const {
    data: carData,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const {
    data: userData,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const { data: voteSummaryData, executeRequest: fetchVoteSummary } =
    useApiRequest(fetchVoteSummaryRequestFn);

  const {
    isLoading: isDeletingBuildList,
    error: deleteBuildListError,
    executeRequest: executeDeleteBuildList,
    setError: setDeleteBuildListError,
  } = useApiRequest(deleteBuildListRequestFn);

  const copyBuildListRequestFn = (buildListId: string) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/copy`, {
      new_name: null,
    });

  const {
    isLoading: isCopyingBuildList,
    error: copyBuildListError,
    executeRequest: executeCopyBuildList,
    setError: setCopyBuildListError,
  } = useApiRequest(copyBuildListRequestFn);

  useEffect(() => {
    if (buildListId) {
      void fetchBuildList(buildListId);
    }
  }, [buildListId, fetchBuildList]);

  useEffect(() => {
    if (buildList?.car_id) {
      void fetchCar(buildList.car_id);
    }
  }, [buildList?.car_id, fetchCar]);

  useEffect(() => {
    if (carData) {
      setAssociatedCar(carData);
    }
  }, [carData]);

  useEffect(() => {
    if (buildList?.user_id) {
      void fetchUser(buildList.user_id);
    }
  }, [buildList?.user_id, fetchUser]);

  useEffect(() => {
    if (buildListId) {
      void fetchVoteSummary(buildListId);
    }
  }, [buildListId, fetchVoteSummary]);

  useEffect(() => {
    if (voteSummaryData) {
      setVoteSummary(voteSummaryData);
    }
  }, [voteSummaryData]);

  const handleVoteUpdate = (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _entityId: number,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _newVote: 'upvote' | 'downvote' | null
  ) => {
    // Refresh vote summary after voting
    if (buildListId) {
      void fetchVoteSummary(buildListId);
    }
  };

  useEffect(() => {
    if (userData) {
      setBuildListOwner(userData);
    }
  }, [userData]);

  const handleBuildListUpdated = () => {
    if (buildListId) {
      void fetchBuildList(buildListId); // Refresh build list data
    }
    setIsEditBuildListFormOpen(false);
  };

  const openEditBuildListDialog = () => setIsEditBuildListFormOpen(true);
  const closeEditBuildListDialog = () => setIsEditBuildListFormOpen(false);

  const openDeleteConfirmDialog = () => {
    setDeleteBuildListError(null);
    setIsDeleteConfirmOpen(true);
  };
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const handleConfirmDelete = async () => {
    if (!buildList || !buildListId) return;

    const result = await executeDeleteBuildList(buildListId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      if (buildList.car_id) {
        void navigate(`/cars/${buildList.car_id}`);
      } else {
        void navigate('/builder');
      }
    }
  };

  const handleCopyBuildList = async () => {
    if (!buildList || !buildListId) return;

    setCopyBuildListError(null);
    const result = await executeCopyBuildList(buildListId);
    if (result !== null) {
      // Navigate to the newly copied build list
      void navigate(`/build-lists/${result.id}`);
    }
  };

  // Handlers for Part creation
  const handlePartAdded = () => {
    setPartsRefreshTrigger(partsRefreshTrigger + 1); // Trigger BuildListParts refresh
    setIsCreatePartFormOpen(false); // Close dialog
  };

  const openCreatePartDialog = () => setIsCreatePartFormOpen(true);
  const closeCreatePartDialog = () => setIsCreatePartFormOpen(false);

  const isLoading = isLoadingBuildList || isLoadingCar;

  if (isLoading && !buildList) {
    return (
      <>
        <PageHeader title="Build List Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (buildListApiError) {
    return (
      <div>
        <PageHeader title="Build List Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load build list with ID "${buildListId}". ${buildListApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!buildList) {
    return (
      <div>
        <PageHeader title="Build List Details" />
        <Card>
          <ErrorAlert
            message={`Build list with ID "${buildListId}" not found.`}
          />
        </Card>
      </div>
    );
  }

  // Check if current user owns the build list (build lists have their own user_id)
  const canManage =
    currentUser && buildList && currentUser.id === buildList.user_id;

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={buildList.name}
        subtitle={`For car: ${associatedCar ? `${associatedCar.make} ${associatedCar.model} ${associatedCar.generation_name} (${associatedCar.start_year}-${associatedCar.end_year})` : buildList.car_id ? 'Loading...' : 'No car assigned'}`}
      />

      {/* Warning when build list has no car assigned */}
      {!buildList.car_id && (
        <Card className="mb-6 border-2 border-yellow-600 bg-yellow-900/20">
          <div className="p-6">
            <div className="flex items-start space-x-4">
              <div className="text-4xl">⚠️</div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-yellow-300 mb-2">
                  Car Assignment Required
                </h3>
                <p className="text-yellow-200 mb-4">
                  This build list doesn't have a car assigned.
                  {canManage
                    ? ' Please assign a car to help organize your build list and make it easier for others to find.'
                    : ' The owner should assign a car to help organize this build list.'}
                </p>
                {canManage && (
                  <ActionButton
                    onClick={openEditBuildListDialog}
                    className="bg-yellow-600 hover:bg-yellow-700 text-white"
                  >
                    Assign Car Now
                  </ActionButton>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Build List Information" />
          <div className="flex space-x-2">
            <ActionButton
              onClick={() =>
                void navigate(`/build-lists/${buildList.id}/build-log`)
              }
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              View Build Log
            </ActionButton>
            {currentUser && (
              <ActionButton
                onClick={() => void handleCopyBuildList()}
                disabled={isCopyingBuildList}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                {isCopyingBuildList ? 'Copying...' : 'Copy Build List'}
              </ActionButton>
            )}
            {canManage && (
              <>
                <ActionButton onClick={openEditBuildListDialog}>
                  Edit Build List
                </ActionButton>
                <ActionButton
                  onClick={openDeleteConfirmDialog}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Delete Build List
                </ActionButton>
              </>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 text-gray-300 items-start">
          <div className="min-w-0">
            <ImageGallery
              imageUrl={buildList.image_url ?? null}
              imageUrls={null}
              altText={buildList.name}
              layout="hero"
              emptyMessage="No image available for this build list."
            />
          </div>
          <div className="min-w-0 space-y-4">
            <CardInfoItem label="Description:">
              <p>{buildList.description || 'No description provided.'}</p>
            </CardInfoItem>
            {associatedCar && (
              <CardInfoItem label="Associated Car:">
                <ParentNavigationLink
                  linkTo={`/cars/${associatedCar.id}`}
                  linkText={`${associatedCar.make} ${associatedCar.model} ${associatedCar.generation_name} (${associatedCar.start_year}-${associatedCar.end_year})`}
                />
              </CardInfoItem>
            )}
            {buildListOwner && (
              <CardInfoItem label="Build List Owner:">
                <ParentNavigationLink
                  linkTo={`/user/${buildListOwner.id}`}
                  linkText={buildListOwner.username}
                />
              </CardInfoItem>
            )}
            {voteSummary && (
              <CardInfoItem label="Community Rating:">
                <VoteButtons
                  entityId={buildList.id}
                  upvotes={voteSummary.upvotes}
                  downvotes={voteSummary.downvotes}
                  userVote={voteSummary.user_vote ?? null}
                  onVoteUpdate={handleVoteUpdate}
                  voteApi={{
                    voteOnEntity: (
                      id: number,
                      data: { vote_type: 'upvote' | 'downvote' }
                    ) => buildListVotesApi.voteOnBuildList(id, data),
                    removeVote: (id: number) =>
                      buildListVotesApi.removeVote(id),
                  }}
                  size="md"
                />
              </CardInfoItem>
            )}
          </div>
        </div>
        {carApiError && (
          <ErrorAlert
            message={`Error loading associated car details: ${carApiError}`}
          />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading build list owner details: ${ownerApiError}`}
          />
        )}
        {copyBuildListError && (
          <ErrorAlert
            message={`Error copying build list: ${copyBuildListError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Build List */}
      {buildList && canManage && (
        <Dialog
          isOpen={isEditBuildListFormOpen}
          onClose={closeEditBuildListDialog}
          title={`Edit ${buildList.name}`}
        >
          <EditBuildListForm
            buildList={buildList}
            onBuildListUpdated={handleBuildListUpdated}
            onCancel={closeEditBuildListDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Build List Confirmation */}
      {buildList && canManage && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={() => void handleConfirmDelete()}
          itemName={buildList.name}
          itemType="build list"
          isProcessing={isDeletingBuildList}
          error={deleteBuildListError}
        />
      )}

      {/* Dialog for Creating Part */}
      {buildList && canManage && (
        <Dialog
          isOpen={isCreatePartFormOpen}
          onClose={closeCreatePartDialog}
          title="Add Part to Build List"
          maxWidth="4xl"
        >
          <CreateBuildListPartForm
            buildListId={buildList.id}
            onPartAdded={handlePartAdded}
            onCancel={closeCreatePartDialog}
          />
        </Dialog>
      )}

      {/* Parts Section */}
      {buildList && (
        <BuildListParts
          buildListId={buildList.id}
          buildListCarId={buildList.car_id ?? null}
          canManageParts={canManage || false}
          refreshKey={partsRefreshTrigger}
          {...(canManage && { onAddPartClick: openCreatePartDialog })}
          title={`Parts in ${buildList.name}`}
          emptyMessage="This build list currently has no parts."
        />
      )}
    </div>
  );
}

export default ViewBuildList;
