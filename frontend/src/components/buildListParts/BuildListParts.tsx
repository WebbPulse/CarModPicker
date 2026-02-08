import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import {
  brandsApi,
  buildListPartsApi,
  carsApi,
  categoriesApi,
} from '../../services/Api';
import type {
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
  CarRead,
} from '../../types/Api';
import { normalizeCarReadList } from '../../utils/carUtils';
import ActionButton from '../buttons/ActionButton';
import { ErrorAlert } from '../common/Alerts';
import DeleteConfirmationDialog from '../common/DeleteConfirmationDialog';
import SectionHeader from '../layout/SectionHeader';
import BuildListPartList from './BuildListPartList';
import EditBuildListPartForm from './EditBuildListPartForm';

interface BuildListPartsProps {
  buildListId: number;
  buildListCarId?: number | null;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: number) =>
  buildListPartsApi.getBuildListParts(buildListId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchBrandsRequestFn = () => brandsApi.getBrands(true);

const fetchCarsRequestFn = () => carsApi.listCars({ limit: LARGE_FETCH_LIMIT });

const BuildListParts: React.FC<BuildListPartsProps> = ({
  buildListId,
  buildListCarId,
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

  const { data: brandsData, executeRequest: fetchBrands } =
    useApiRequest(fetchBrandsRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  const brands = brandsData ?? [];
  const carsById = useMemo(() => {
    const list = Array.isArray(carsData) ? carsData : [];
    const normalized = normalizeCarReadList(list);
    const map: Record<number, CarRead> = {};
    for (const car of normalized) {
      map[car.id] = car;
    }
    return map;
  }, [carsData]);

  // Local state for optimistic updates - sync with API data
  const [localBuildListParts, setLocalBuildListParts] = useState<
    BuildListPartReadWithGlobalPart[] | null
  >(null);

  // Sync local state with API data when it changes
  useEffect(() => {
    if (buildListParts) {
      setLocalBuildListParts(buildListParts);
    }
  }, [buildListParts]);

  useEffect(() => {
    void fetchBuildListParts(buildListId);
    void fetchCategories();
    void fetchBrands();
    void fetchCars();
  }, [
    buildListId,
    refreshKey,
    fetchBuildListParts,
    fetchCategories,
    fetchBrands,
    fetchCars,
  ]);

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

  const handleTogglePurchased = useCallback(
    async (buildListPart: BuildListPartReadWithGlobalPart) => {
      if (!canManageParts) return;

      const newPurchasedStatus = !buildListPart.purchased;

      // Optimistic update: update local state immediately
      setLocalBuildListParts((prevParts) => {
        if (!prevParts) return prevParts;
        return prevParts.map((part) =>
          part.id === buildListPart.id
            ? { ...part, purchased: newPurchasedStatus }
            : part
        );
      });

      try {
        await buildListPartsApi.updateBuildListPart(
          buildListId,
          buildListPart.global_part_id,
          { purchased: newPurchasedStatus }
        );
        // Optionally sync with server, but don't refetch to avoid full re-render
        // The optimistic update is already applied
      } catch {
        // Revert optimistic update on error
        setLocalBuildListParts((prevParts) => {
          if (!prevParts) return prevParts;
          return prevParts.map((part) =>
            part.id === buildListPart.id
              ? { ...part, purchased: buildListPart.purchased }
              : part
          );
        });
      }
    },
    [canManageParts, buildListId]
  );

  // Wrapper to match the expected void return type
  const handleTogglePurchasedWrapper = useCallback(
    (part: BuildListPartReadWithGlobalPart) => {
      void handleTogglePurchased(part);
    },
    [handleTogglePurchased]
  );

  const parts = localBuildListParts || buildListParts || [];
  const hasCarMismatchParts =
    buildListCarId != null &&
    parts.some((p) => {
      const gp = p.global_part;
      if (!gp) return false;
      if (gp.is_universal) return false;
      const carIds = gp.car_ids ?? [];
      return carIds.length > 0 && !carIds.includes(buildListCarId);
    });

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

      {hasCarMismatchParts && (
        <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-4">
          <div className="flex gap-3">
            <svg
              className="flex-shrink-0 w-5 h-5 text-amber-400 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-amber-200">
                Possible car compatibility warning
              </p>
              <p className="text-sm text-amber-200/90 mt-1">
                One or more parts in this build list may be associated with a
                different car model. Parts may not be compatible across
                vehicles. Please verify fitment and do your own due diligence.
              </p>
            </div>
          </div>
        </div>
      )}

      <BuildListPartList
        buildListParts={parts}
        categories={categories || []}
        brands={brands}
        carsById={carsById}
        loading={isLoading || isLoadingCategories}
        onEdit={handleEdit}
        onDelete={handleDelete}
        {...(canManageParts && {
          onTogglePurchased: handleTogglePurchasedWrapper,
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
