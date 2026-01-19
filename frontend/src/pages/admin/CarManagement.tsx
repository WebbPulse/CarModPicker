import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { carsApi } from '../../services/Api';
import type { CarCreate, CarRead, CarUpdate } from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchCarsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  search?: string;
}) => carsApi.listCars(params);
const updateCarRequestFn = (payload: { carId: number; data: CarUpdate }) =>
  carsApi.updateCar(payload.carId, payload.data);
const deleteCarRequestFn = (carId: number) => carsApi.deleteCar(carId);
const createCarRequestFn = (data: CarCreate) => carsApi.createCar(data);

function CarManagement() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedCar, setSelectedCar] = useState<CarRead | null>(null);
  const [formData, setFormData] = useState<CarCreate>({
    make: '',
    model: '',
    generation_name: '',
    start_year: new Date().getFullYear(),
    end_year: new Date().getFullYear(),
    description: '',
    image_url: '',
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMake, setSelectedMake] = useState<string>('');

  const {
    data: cars,
    isLoading: isLoadingCars,
    error: carsError,
    executeRequest: fetchCars,
  } = useApiRequest(fetchCarsRequestFn);

  const {
    isLoading: isCreating,
    error: createError,
    executeRequest: executeCreate,
    setError: setCreateError,
  } = useApiRequest(createCarRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateCarRequestFn);

  const {
    isLoading: isDeleting,
    error: deleteError,
    executeRequest: executeDelete,
    setError: setDeleteError,
  } = useApiRequest(deleteCarRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const refreshCars = useCallback(() => {
    const params: { limit?: number; search?: string } = {
      limit: 1000, // High limit to get all cars
    };
    if (searchTerm.trim()) {
      params.search = searchTerm.trim();
    }
    void fetchCars(params);
  }, [fetchCars, searchTerm]);

  // Group cars by make
  const carsByMake = useMemo(() => {
    if (!cars) return {};
    const grouped: Record<string, CarRead[]> = {};
    cars.forEach((car) => {
      if (!grouped[car.make]) {
        grouped[car.make] = [];
      }
      const makeArray = grouped[car.make];
      if (makeArray) {
        makeArray.push(car);
      }
    });
    // Sort makes alphabetically and sort cars within each make
    return Object.keys(grouped)
      .sort()
      .reduce(
        (acc, make) => {
          const makeCars = grouped[make];
          if (makeCars) {
            acc[make] = makeCars.sort((a, b) => {
              // Sort by model, then by generation name
              if (a.model !== b.model) {
                return a.model.localeCompare(b.model);
              }
              return a.generation_name.localeCompare(b.generation_name);
            });
          }
          return acc;
        },
        {} as Record<string, CarRead[]>
      );
  }, [cars]);

  // Get unique makes for the filter dropdown
  const uniqueMakes = useMemo(() => {
    if (!cars) return [];
    const makesSet = new Set(cars.map((car) => car.make));
    return Array.from(makesSet).sort();
  }, [cars]);

  // Filter cars by selected make - only show cars if a make is selected
  const filteredCarsByMake = useMemo(() => {
    if (!selectedMake) return {};
    if (!carsByMake[selectedMake]) return {};
    return { [selectedMake]: carsByMake[selectedMake] };
  }, [carsByMake, selectedMake]);

  const filteredMakes = useMemo(
    () => Object.keys(filteredCarsByMake),
    [filteredCarsByMake]
  );

  useEffect(() => {
    refreshCars();
  }, [refreshCars]);

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Car Management" />
        <Card>
          <ErrorAlert message="Please log in to access car management." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Car Management" />
        <Card>
          <ErrorAlert message="You do not have permission to access car management." />
        </Card>
      </div>
    );
  }

  const handleCreateCar = async () => {
    if (
      !formData.make.trim() ||
      !formData.model.trim() ||
      !formData.generation_name.trim()
    ) {
      setCreateError('Make, Model, and Generation Name are required.');
      return;
    }
    if (formData.start_year > formData.end_year) {
      setCreateError('Start year must be less than or equal to end year.');
      return;
    }
    const result = await executeCreate(formData);
    if (result) {
      setIsCreateDialogOpen(false);
      setFormData({
        make: '',
        model: '',
        generation_name: '',
        start_year: new Date().getFullYear(),
        end_year: new Date().getFullYear(),
        description: '',
        image_url: '',
      });
      refreshCars();
    }
  };

  const handleUpdateCar = async () => {
    if (!selectedCar) return;
    if (
      formData.make.trim() &&
      formData.model.trim() &&
      formData.generation_name.trim()
    ) {
      if (formData.start_year > formData.end_year) {
        setUpdateError('Start year must be less than or equal to end year.');
        return;
      }
    }
    const result = await executeUpdate({
      carId: selectedCar.id,
      data: formData,
    });
    if (result) {
      setIsEditDialogOpen(false);
      setSelectedCar(null);
      refreshCars();
    }
  };

  const handleDeleteCar = async () => {
    if (!selectedCar) return;
    const result = await executeDelete(selectedCar.id);
    if (result) {
      setIsDeleteDialogOpen(false);
      setSelectedCar(null);
      refreshCars();
    }
  };

  const openCreateDialog = () => {
    setCreateError(null);
    setIsCreateDialogOpen(true);
  };

  const openEditDialog = (car: CarRead) => {
    setUpdateError(null);
    setSelectedCar(car);
    setFormData({
      make: car.make,
      model: car.model,
      generation_name: car.generation_name,
      start_year: car.start_year,
      end_year: car.end_year,
      description: car.description || '',
      image_url: car.image_url || '',
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (car: CarRead) => {
    setDeleteError(null);
    setSelectedCar(car);
    setIsDeleteDialogOpen(true);
  };

  const closeCreateDialog = () => {
    setIsCreateDialogOpen(false);
    setFormData({
      make: '',
      model: '',
      generation_name: '',
      start_year: new Date().getFullYear(),
      end_year: new Date().getFullYear(),
      description: '',
      image_url: '',
    });
  };

  const closeEditDialog = () => {
    setIsEditDialogOpen(false);
    setSelectedCar(null);
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSelectedCar(null);
  };

  if (isLoadingCars && !cars) {
    return (
      <>
        <PageHeader title="Car Management" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Car Management"
        subtitle="Edit and manage car generations (cars are primarily created via scripts)"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
        <div className="flex gap-2">
          <Input
            id="search-cars"
            placeholder="Search by make, model, or generation..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
            }}
            className="w-64"
          />
          <ActionButton
            onClick={openCreateDialog}
            className="bg-gray-600 hover:bg-gray-700"
          >
            Create New Car
          </ActionButton>
        </div>
      </div>

      {/* Make Selection Tiles */}
      {cars && uniqueMakes.length > 0 && (
        <Card>
          <SectionHeader title="Select a Make" />
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mt-4">
            {uniqueMakes.map((make) => {
              const makeCarCount = carsByMake[make]?.length || 0;
              const isSelected = selectedMake === make;
              return (
                <div
                  key={make}
                  onClick={() => setSelectedMake(isSelected ? '' : make)}
                  className={`
                    cursor-pointer transition-all duration-200
                    border-2 rounded-lg p-4 text-center
                    ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-500/10 shadow-lg shadow-indigo-500/20'
                        : 'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800'
                    }
                  `}
                >
                  <h3
                    className={`text-lg font-semibold mb-1 ${
                      isSelected ? 'text-indigo-400' : 'text-gray-200'
                    }`}
                  >
                    {make}
                  </h3>
                  <p className="text-sm text-gray-400">
                    {makeCarCount} {makeCarCount === 1 ? 'car' : 'cars'}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {carsError && (
        <Card>
          <ErrorAlert message={`Failed to load cars: ${carsError}`} />
        </Card>
      )}

      {cars && (
        <Card>
          <SectionHeader title="Cars" />
          {!selectedMake ? (
            <div className="p-8 text-center">
              <p className="text-gray-400 text-lg mb-2">
                Please select a make to view cars
              </p>
              <p className="text-gray-500 text-sm">
                Choose a make from the dropdown above to see available cars
              </p>
            </div>
          ) : (
            <>
              <div className="mb-4 text-sm text-gray-400">
                Showing {filteredCarsByMake[selectedMake]?.length || 0} car
                {(filteredCarsByMake[selectedMake]?.length || 0) !== 1
                  ? 's'
                  : ''}{' '}
                for {selectedMake}
                {searchTerm && ` matching "${searchTerm}"`}
              </div>
              {filteredMakes.length === 0 ? (
                <div className="p-4 text-center text-gray-400">
                  No cars found for {selectedMake}
                  {searchTerm && ` matching "${searchTerm}"`}
                </div>
              ) : (
                <div className="space-y-6">
                  {filteredMakes.map((make) => {
                    const makeCars = filteredCarsByMake[make];
                    if (!makeCars) return null;
                    return (
                      <div
                        key={make}
                        className="border border-gray-700 rounded-lg overflow-hidden"
                      >
                        <div className="bg-gray-800 px-4 py-3 border-b border-gray-700">
                          <h3 className="text-lg font-semibold text-gray-200">
                            {make}
                            <span className="ml-2 text-sm font-normal text-gray-400">
                              ({makeCars.length}{' '}
                              {makeCars.length === 1 ? 'car' : 'cars'})
                            </span>
                          </h3>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left">
                            <thead className="border-b border-gray-700 bg-gray-800/50">
                              <tr>
                                <th className="p-2 text-gray-300">Model</th>
                                <th className="p-2 text-gray-300">
                                  Generation Name
                                </th>
                                <th className="p-2 text-gray-300">Years</th>
                                <th className="p-2 text-gray-300">
                                  Description
                                </th>
                                <th className="p-2 text-gray-300">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {makeCars.map((car) => (
                                <tr
                                  key={car.id}
                                  className="border-b border-gray-800 hover:bg-gray-800/30"
                                >
                                  <td className="p-2 text-gray-200">
                                    {car.model}
                                  </td>
                                  <td className="p-2 text-gray-200">
                                    {car.generation_name}
                                  </td>
                                  <td className="p-2 text-gray-200">
                                    {car.start_year} - {car.end_year}
                                  </td>
                                  <td className="p-2 text-gray-400 max-w-xs truncate">
                                    {car.description || 'No description'}
                                  </td>
                                  <td className="p-2">
                                    <div className="flex space-x-2">
                                      <ActionButton
                                        onClick={() => openEditDialog(car)}
                                        className="text-sm px-2 py-1"
                                      >
                                        Edit
                                      </ActionButton>
                                      <ActionButton
                                        onClick={() => openDeleteDialog(car)}
                                        className="text-sm px-2 py-1 bg-red-600 hover:bg-red-700"
                                      >
                                        Delete
                                      </ActionButton>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </Card>
      )}

      {/* Create Car Dialog */}
      <Dialog
        isOpen={isCreateDialogOpen}
        onClose={closeCreateDialog}
        title="Create New Car"
      >
        <div className="space-y-4">
          <Input
            id="create-make"
            label="Make"
            value={formData.make}
            onChange={(e) => setFormData({ ...formData, make: e.target.value })}
            placeholder="e.g., Honda"
            required
          />
          <Input
            id="create-model"
            label="Model"
            value={formData.model}
            onChange={(e) =>
              setFormData({ ...formData, model: e.target.value })
            }
            placeholder="e.g., Civic"
            required
          />
          <Input
            id="create-generation-name"
            label="Generation Name"
            value={formData.generation_name}
            onChange={(e) =>
              setFormData({ ...formData, generation_name: e.target.value })
            }
            placeholder="e.g., 5th Gen, MK7, F30"
            required
          />
          <Input
            id="create-start-year"
            label="Start Year"
            type="number"
            value={formData.start_year}
            onChange={(e) =>
              setFormData({
                ...formData,
                start_year:
                  parseInt(e.target.value) || new Date().getFullYear(),
              })
            }
            required
          />
          <Input
            id="create-end-year"
            label="End Year"
            type="number"
            value={formData.end_year}
            onChange={(e) =>
              setFormData({
                ...formData,
                end_year: parseInt(e.target.value) || new Date().getFullYear(),
              })
            }
            required
          />
          <Input
            id="create-description"
            label="Description (Optional)"
            value={formData.description || ''}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            placeholder="Description of this car generation"
          />
          <Input
            id="create-image-url"
            label="Image URL (Optional)"
            value={formData.image_url || ''}
            onChange={(e) =>
              setFormData({ ...formData, image_url: e.target.value })
            }
            placeholder="https://example.com/image.jpg"
          />
          {createError && <ErrorAlert message={createError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeCreateDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleCreateCar()}
              disabled={
                isCreating ||
                !formData.make.trim() ||
                !formData.model.trim() ||
                !formData.generation_name.trim()
              }
            >
              {isCreating ? 'Creating...' : 'Create Car'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Edit Car Dialog */}
      <Dialog
        isOpen={isEditDialogOpen}
        onClose={closeEditDialog}
        title={`Edit Car: ${selectedCar?.make} ${selectedCar?.model} ${selectedCar?.generation_name}`}
      >
        <div className="space-y-4">
          <Input
            id="edit-make"
            label="Make"
            value={formData.make}
            onChange={(e) => setFormData({ ...formData, make: e.target.value })}
            placeholder="e.g., Honda"
            required
          />
          <Input
            id="edit-model"
            label="Model"
            value={formData.model}
            onChange={(e) =>
              setFormData({ ...formData, model: e.target.value })
            }
            placeholder="e.g., Civic"
            required
          />
          <Input
            id="edit-generation-name"
            label="Generation Name"
            value={formData.generation_name}
            onChange={(e) =>
              setFormData({ ...formData, generation_name: e.target.value })
            }
            placeholder="e.g., 5th Gen, MK7, F30"
            required
          />
          <Input
            id="edit-start-year"
            label="Start Year"
            type="number"
            value={formData.start_year}
            onChange={(e) =>
              setFormData({
                ...formData,
                start_year:
                  parseInt(e.target.value) || new Date().getFullYear(),
              })
            }
            required
          />
          <Input
            id="edit-end-year"
            label="End Year"
            type="number"
            value={formData.end_year}
            onChange={(e) =>
              setFormData({
                ...formData,
                end_year: parseInt(e.target.value) || new Date().getFullYear(),
              })
            }
            required
          />
          <Input
            id="edit-description"
            label="Description (Optional)"
            value={formData.description || ''}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            placeholder="Description of this car generation"
          />
          <Input
            id="edit-image-url"
            label="Image URL (Optional)"
            value={formData.image_url || ''}
            onChange={(e) =>
              setFormData({ ...formData, image_url: e.target.value })
            }
            placeholder="https://example.com/image.jpg"
          />
          {updateError && <ErrorAlert message={updateError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeEditDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateCar()}
              disabled={
                isUpdating ||
                !formData.make.trim() ||
                !formData.model.trim() ||
                !formData.generation_name.trim()
              }
            >
              {isUpdating ? 'Updating...' : 'Update Car'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={() => void handleDeleteCar()}
        itemName={`${selectedCar?.make} ${selectedCar?.model} ${selectedCar?.generation_name}`}
        itemType="car"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
}

export default CarManagement;
