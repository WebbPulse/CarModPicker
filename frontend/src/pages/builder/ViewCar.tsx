import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { carsApi } from '../../services/Api';

import BuildListList from '../../components/buildLists/BuildListList';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import ActionButton from '../../components/buttons/ActionButton';
import EditCarForm from '../../components/cars/EditCarForm';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import CardInfoItem from '../../components/common/CardInfoItem';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchCarRequestFn = (carId: string) => carsApi.getCar(Number(carId));

const deleteCarRequestFn = (carId: string) => carsApi.deleteCar(Number(carId));

function ViewCar() {
  const { carId } = useParams<{ carId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [buildListRefreshTrigger, setBuildListRefreshTrigger] = useState(0);
  const [isEditCarFormOpen, setIsEditCarFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  const {
    data: car,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const {
    isLoading: isDeletingCar,
    error: deleteCarError,
    executeRequest: executeDeleteCar,
    setError: setDeleteCarError,
  } = useApiRequest(deleteCarRequestFn);

  useEffect(() => {
    if (carId) {
      void fetchCar(carId);
    }
  }, [carId, fetchCar]);

  const handleBuildListCreated = () => {
    setBuildListRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false); // Close dialog
  };

  const openCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(true);
  };

  const closeCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(false);
  };

  const openEditCarDialog = () => {
    setIsEditCarFormOpen(true);
  };

  const closeEditCarDialog = () => {
    setIsEditCarFormOpen(false);
  };

  const handleCarUpdated = () => {
    if (carId) {
      void fetchCar(carId);
    }
    setIsEditCarFormOpen(false);
  };

  const openDeleteConfirmDialog = () => {
    setDeleteCarError(null); // Clear previous errors
    setIsDeleteConfirmOpen(true);
  };

  const closeDeleteConfirmDialog = () => {
    setIsDeleteConfirmOpen(false);
  };

  const handleConfirmDelete = async () => {
    if (!car || !carId) return;

    const result = await executeDeleteCar(carId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      void navigate('/builder');
    }
  };

  if (isLoadingCar) {
    return (
      <>
        <PageHeader title="Car Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (carApiError) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load car with ID "${carId}". ${carApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!car) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert message={`Car with ID "${carId}" not found.`} />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={`${car.make} ${car.model} ${car.generation_name} (${car.start_year}-${car.end_year})`}
      />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Car Information" />
          {currentUser &&
            (currentUser.is_admin || currentUser.is_superuser) && (
              <div className="flex space-x-2">
                <ActionButton onClick={openEditCarDialog}>
                  Edit Car
                </ActionButton>
                <ActionButton
                  onClick={openDeleteConfirmDialog}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Delete Car
                </ActionButton>
              </div>
            )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <CardInfoItem label="">
            <ImageWithPlaceholder
              srcUrl={car.image_url ?? null}
              altText={`${car.make} ${car.model} ${car.generation_name}`}
              imageClassName="h-48 w-auto object-contain rounded"
              containerClassName="h-48 flex justify-left items-center"
              fallbackText="No image available."
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          <CardInfoItem label="Make:">
            <p>{car.make}</p>
          </CardInfoItem>
          <CardInfoItem label="Model:">
            <p>{car.model}</p>
          </CardInfoItem>
          <CardInfoItem label="Generation:">
            <p>{car.generation_name}</p>
          </CardInfoItem>
          <CardInfoItem label="Year Range:">
            <p>
              {car.start_year}-{car.end_year}
            </p>
          </CardInfoItem>
          {car.description && (
            <CardInfoItem label="Description:">
              <p>{car.description}</p>
            </CardInfoItem>
          )}
        </div>
      </Card>

      <Divider />

      {/* Dialog for Editing Car */}
      {car && (
        <Dialog
          isOpen={isEditCarFormOpen}
          onClose={closeEditCarDialog}
          title={`Edit ${car.make} ${car.model}`}
        >
          <EditCarForm
            car={car}
            onCarUpdated={handleCarUpdated}
            onCancel={closeEditCarDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Car Confirmation */}
      {car && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={() => void handleConfirmDelete()}
          itemName={`${car.make} ${car.model} ${car.generation_name}`}
          itemType="car"
          isProcessing={isDeletingCar}
          error={deleteCarError}
        />
      )}

      {/* Dialog for Creating Build List */}
      <Dialog
        isOpen={isCreateBuildListFormOpen}
        onClose={closeCreateBuildListDialog}
        title={`Create Build List for ${car.make} ${car.model}`}
      >
        <CreateBuildListForm
          carId={car.id}
          onBuildListCreated={handleBuildListCreated}
        />
      </Dialog>

      {/* Build Lists Section */}
      {currentUser && (
        <BuildListList
          carId={car.id}
          currentUserId={currentUser.id}
          refreshKey={buildListRefreshTrigger}
          title={`Build Lists for ${car.make} ${car.model}`}
          emptyMessage="This car doesn't have any build lists yet."
          onAddBuildListClick={openCreateBuildListDialog}
        />
      )}
    </div>
  );
}

export default ViewCar;
