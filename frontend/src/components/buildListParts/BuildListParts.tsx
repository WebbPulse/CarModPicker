import React, { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi, categoriesApi } from '../../services/Api';
import type {
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
} from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import { ErrorAlert } from '../common/Alerts';
import DeleteConfirmationDialog from '../common/DeleteConfirmationDialog';
import SectionHeader from '../layout/SectionHeader';
import BuildListPartList from './BuildListPartList';
import EditBuildListPartForm from './EditBuildListPartForm';

interface BuildListPartsProps {
  buildListId: number;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: number) =>
  buildListPartsApi.getBuildListParts(buildListId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const BuildListParts: React.FC<BuildListPartsProps> = ({
  buildListId,
  canManageParts,
  refreshKey,
  onAddPartClick,
  title = 'Parts in Build List',
  emptyMessage = 'No parts added to this build list yet.',
}) => {
  const { user: currentUser } = useAuth();
  const [editingPart, setEditingPart] =
    useState<BuildListPartReadWithGlobalPart | null>(null);
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingPartId, setDeletingPartId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const {
    data: buildListParts,
    isLoading,
    error,
    executeRequest: fetchBuildListParts,
  } = useApiRequest(fetchBuildListPartsRequestFn);

  const {
    data: categories,
    isLoading: isLoadingCategories,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  useEffect(() => {
    void fetchBuildListParts(buildListId);
    void fetchCategories();
  }, [buildListId, refreshKey, fetchBuildListParts, fetchCategories]);

  // Helper function to check if user can edit a specific build list part
  const canEditBuildListPart = (
    buildListPart: BuildListPartReadWithGlobalPart
  ) => {
    if (!currentUser) return false;
    return buildListPart.added_by === currentUser.id;
  };

  // Helper function to check if user can delete a specific build list part
  const canDeleteBuildListPart = (
    buildListPart: BuildListPartReadWithGlobalPart
  ) => {
    if (!currentUser) return false;
    return (
      buildListPart.added_by === currentUser.id ||
      currentUser.is_admin ||
      currentUser.is_superuser
    );
  };

  const handleEdit = (buildListPart: BuildListPartReadWithGlobalPart) => {
    if (!canEditBuildListPart(buildListPart)) {
      console.error('User not authorized to edit this build list part');
      return;
    }
    setEditingPart(buildListPart);
    setIsEditFormOpen(true);
  };

  const handleEditSubmit = async (
    _buildListPartId: number,
    data: BuildListPartUpdate
  ) => {
    try {
      setIsUpdating(true);
      await buildListPartsApi.updateBuildListPart(
        buildListId,
        editingPart!.global_part_id,
        data
      );
      // Refresh the build list parts
      await fetchBuildListParts(buildListId);
    } catch (error) {
      console.error('Failed to update build list part:', error);
      throw error;
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = (buildListPartId: number) => {
    // Find the build list part to get the global_part_id
    const buildListPart = buildListParts?.find(
      (part) => part.id === buildListPartId
    );
    if (!buildListPart) return;

    if (!canDeleteBuildListPart(buildListPart)) {
      console.error('User not authorized to delete this build list part');
      return;
    }

    // Open confirmation dialog instead of directly deleting
    setDeleteError(null);
    setDeletingPartId(buildListPartId);
  };

  const handleConfirmDelete = async () => {
    if (deletingPartId === null) return;

    // Find the build list part to get the global_part_id
    const buildListPart = buildListParts?.find(
      (part) => part.id === deletingPartId
    );
    if (!buildListPart) {
      setDeletingPartId(null);
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await buildListPartsApi.removeBuildListPart(
        buildListId,
        buildListPart.global_part_id
      );
      await fetchBuildListParts(buildListId);
      setDeletingPartId(null);
    } catch (error: unknown) {
      console.error('Failed to remove part from build list:', error);
      setDeleteError(
        error instanceof Error
          ? error.message
          : 'Failed to remove part from build list'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCloseDeleteDialog = () => {
    setDeletingPartId(null);
    setDeleteError(null);
  };

  const handleCloseEditForm = () => {
    setIsEditFormOpen(false);
    setEditingPart(null);
  };

  const handleTogglePurchased = async (buildListPart: BuildListPartReadWithGlobalPart) => {
    if (!canManageParts) return;
    
    try {
      await buildListPartsApi.updateBuildListPart(
        buildListId,
        buildListPart.global_part_id,
        { purchased: !buildListPart.purchased }
      );
      // Refresh the build list parts
      await fetchBuildListParts(buildListId);
    } catch (error) {
      console.error('Failed to update purchased status:', error);
    }
  };

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
          {canManageParts && onAddPartClick && (
            <ActionButton onClick={() => void onAddPartClick()}>
              Add Part
            </ActionButton>
          )}
        </div>
        <ErrorAlert message="Failed to load parts. Please try again." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
        {canManageParts && onAddPartClick && (
          <ActionButton onClick={() => void onAddPartClick()}>
            Add Part
          </ActionButton>
        )}
      </div>

      <BuildListPartList
        buildListParts={buildListParts || []}
        categories={categories || []}
        loading={isLoading || isLoadingCategories}
        onEdit={handleEdit}
        onDelete={handleDelete}
        {...(canManageParts && {
          onTogglePurchased: (part) => void handleTogglePurchased(part),
        })}
        canEdit={canManageParts}
        canDelete={canManageParts}
        canMarkPurchased={canManageParts}
        emptyMessage={emptyMessage}
        // Pass individual permission check functions
        canEditPart={canEditBuildListPart}
        canDeletePart={canDeleteBuildListPart}
      />

      {editingPart && (
        <EditBuildListPartForm
          buildListPart={editingPart}
          isOpen={isEditFormOpen}
          onClose={handleCloseEditForm}
          onSubmit={handleEditSubmit}
          loading={isUpdating}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={deletingPartId !== null}
        onClose={handleCloseDeleteDialog}
        onConfirm={() => void handleConfirmDelete()}
        itemName={
          buildListParts?.find((p) => p.id === deletingPartId)?.global_part
            .name || ''
        }
        itemType="part"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
};

export default BuildListParts;
