import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { carGenerationsApi } from '../../services/Api';
import type {
  CarGenerationCreate,
  CarGenerationRead,
  CarGenerationUpdate,
} from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchCarGenerationsRequestFn = () =>
  carGenerationsApi.listCarGenerations();
const createCarGenerationRequestFn = (data: CarGenerationCreate) =>
  carGenerationsApi.createCarGeneration(data);
const updateCarGenerationRequestFn = (payload: {
  generationId: number;
  data: CarGenerationUpdate;
}) => carGenerationsApi.updateCarGeneration(payload.generationId, payload.data);
const deleteCarGenerationRequestFn = (generationId: number) =>
  carGenerationsApi.deleteCarGeneration(generationId);

function CarGenerationManagement() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedGeneration, setSelectedGeneration] =
    useState<CarGenerationRead | null>(null);
  const [formData, setFormData] = useState<CarGenerationCreate>({
    make: '',
    model: '',
    generation_name: '',
    start_year: new Date().getFullYear(),
    end_year: new Date().getFullYear(),
    description: '',
  });

  const {
    data: generations,
    isLoading: isLoadingGenerations,
    error: generationsError,
    executeRequest: fetchGenerations,
  } = useApiRequest(fetchCarGenerationsRequestFn);

  const {
    isLoading: isCreating,
    error: createError,
    executeRequest: executeCreate,
    setError: setCreateError,
  } = useApiRequest(createCarGenerationRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateCarGenerationRequestFn);

  const {
    isLoading: isDeleting,
    error: deleteError,
    executeRequest: executeDelete,
    setError: setDeleteError,
  } = useApiRequest(deleteCarGenerationRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    void fetchGenerations();
  }, [fetchGenerations]);

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Car Generation Management" />
        <Card>
          <ErrorAlert message="Please log in to access car generation management." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Car Generation Management" />
        <Card>
          <ErrorAlert message="You do not have permission to access car generation management." />
        </Card>
      </div>
    );
  }

  const handleCreateGeneration = async () => {
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
      });
      void fetchGenerations();
    }
  };

  const handleUpdateGeneration = async () => {
    if (!selectedGeneration) return;
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
      generationId: selectedGeneration.id,
      data: formData,
    });
    if (result) {
      setIsEditDialogOpen(false);
      setSelectedGeneration(null);
      void fetchGenerations();
    }
  };

  const handleDeleteGeneration = async () => {
    if (!selectedGeneration) return;
    const result = await executeDelete(selectedGeneration.id);
    if (result) {
      setIsDeleteDialogOpen(false);
      setSelectedGeneration(null);
      void fetchGenerations();
    }
  };

  const openCreateDialog = () => {
    setCreateError(null);
    setIsCreateDialogOpen(true);
  };

  const openEditDialog = (generation: CarGenerationRead) => {
    setUpdateError(null);
    setSelectedGeneration(generation);
    setFormData({
      make: generation.make,
      model: generation.model,
      generation_name: generation.generation_name,
      start_year: generation.start_year,
      end_year: generation.end_year,
      description: generation.description || '',
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (generation: CarGenerationRead) => {
    setDeleteError(null);
    setSelectedGeneration(generation);
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
    });
  };

  const closeEditDialog = () => {
    setIsEditDialogOpen(false);
    setSelectedGeneration(null);
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSelectedGeneration(null);
  };

  if (isLoadingGenerations && !generations) {
    return (
      <>
        <PageHeader title="Car Generation Management" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Car Generation Management"
        subtitle="Create and manage car generations (e.g., 5th Gen Civic, MK7 Golf)"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
        <ActionButton onClick={openCreateDialog}>
          Create New Generation
        </ActionButton>
      </div>

      {generationsError && (
        <Card>
          <ErrorAlert
            message={`Failed to load car generations: ${generationsError}`}
          />
        </Card>
      )}

      {generations && (
        <Card>
          <SectionHeader title="Car Generations" />
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-gray-700">
                <tr>
                  <th className="p-2 text-gray-300">Make</th>
                  <th className="p-2 text-gray-300">Model</th>
                  <th className="p-2 text-gray-300">Generation Name</th>
                  <th className="p-2 text-gray-300">Years</th>
                  <th className="p-2 text-gray-300">Description</th>
                  <th className="p-2 text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody>
                {generations.map((generation) => (
                  <tr key={generation.id} className="border-b border-gray-800">
                    <td className="p-2 text-gray-200">{generation.make}</td>
                    <td className="p-2 text-gray-200">{generation.model}</td>
                    <td className="p-2 text-gray-200">
                      {generation.generation_name}
                    </td>
                    <td className="p-2 text-gray-200">
                      {generation.start_year} - {generation.end_year}
                    </td>
                    <td className="p-2 text-gray-400 max-w-xs truncate">
                      {generation.description || 'No description'}
                    </td>
                    <td className="p-2">
                      <div className="flex space-x-2">
                        <ActionButton
                          onClick={() => openEditDialog(generation)}
                          className="text-sm px-2 py-1"
                        >
                          Edit
                        </ActionButton>
                        <ActionButton
                          onClick={() => openDeleteDialog(generation)}
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
        </Card>
      )}

      {/* Create Generation Dialog */}
      <Dialog
        isOpen={isCreateDialogOpen}
        onClose={closeCreateDialog}
        title="Create New Car Generation"
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
            placeholder="Description of this generation"
          />
          {createError && <ErrorAlert message={createError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeCreateDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleCreateGeneration()}
              disabled={
                isCreating ||
                !formData.make.trim() ||
                !formData.model.trim() ||
                !formData.generation_name.trim()
              }
            >
              {isCreating ? 'Creating...' : 'Create Generation'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Edit Generation Dialog */}
      <Dialog
        isOpen={isEditDialogOpen}
        onClose={closeEditDialog}
        title={`Edit Generation: ${selectedGeneration?.generation_name}`}
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
            placeholder="Description of this generation"
          />
          {updateError && <ErrorAlert message={updateError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeEditDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateGeneration()}
              disabled={
                isUpdating ||
                !formData.make.trim() ||
                !formData.model.trim() ||
                !formData.generation_name.trim()
              }
            >
              {isUpdating ? 'Updating...' : 'Update Generation'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={() => void handleDeleteGeneration()}
        itemName={`${selectedGeneration?.make} ${selectedGeneration?.model} ${selectedGeneration?.generation_name}`}
        itemType="car generation"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
}

export default CarGenerationManagement;
