import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import {
  partManufacturersApi,
  buildListPartsApi,
  buildListPhasesApi,
  buildListsApi,
  carGenerationsApi,
  categoriesApi,
} from '../../services/Api';
import type {
  BuildListPartReadWithPart,
  BuildListPartUpdate,
  BuildListPhaseRead,
  CarGenerationRead,
} from '../../types/Api';
import { normalizeCarReadList } from '../../utils/carUtils';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import DeleteConfirmationDialog from '../common/DeleteConfirmationDialog';
import SectionHeader from '../layout/SectionHeader';
import BuildListPartList from './BuildListPartList';
import EditBuildListPartForm from './EditBuildListPartForm';

interface BuildListPartsProps {
  buildListId: string;
  buildListCarId?: string | null;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: string) =>
  buildListPartsApi.getBuildListParts(buildListId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchPartManufacturersRequestFn = () =>
  partManufacturersApi.getPartManufacturers(true);

const fetchCarsRequestFn = () =>
  carGenerationsApi.listCars({ limit: LARGE_FETCH_LIMIT });

const fetchPhasesRequestFn = (buildListId: string) =>
  buildListsApi.getPhases(buildListId);

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
    useState<BuildListPartReadWithPart | null>(null);
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingPartId, setDeletingPartId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'category' | 'phase'>('category');
  const [newPhaseName, setNewPhaseName] = useState('');
  const [isAddingPhase, setIsAddingPhase] = useState(false);
  const [editingPhaseId, setEditingPhaseId] = useState<string | null>(null);
  const [editingPhaseName, setEditingPhaseName] = useState('');
  const [deletingPhaseId, setDeletingPhaseId] = useState<string | null>(null);
  const [phaseError, setPhaseError] = useState<string | null>(null);

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

  const {
    data: part_manufacturersData,
    executeRequest: fetchPartManufacturers,
  } = useApiRequest(fetchPartManufacturersRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  const { data: phases, executeRequest: fetchPhases } =
    useApiRequest(fetchPhasesRequestFn);

  const part_manufacturers = part_manufacturersData ?? [];
  const carsById = useMemo(() => {
    const list = Array.isArray(carsData) ? carsData : [];
    const normalized = normalizeCarReadList(list);
    const map: Record<string, CarGenerationRead> = {};
    for (const car of normalized) {
      map[car.id] = car;
    }
    return map;
  }, [carsData]);

  // Local state for optimistic updates - sync with API data
  const [localBuildListParts, setLocalBuildListParts] = useState<
    BuildListPartReadWithPart[] | null
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
    void fetchPartManufacturers();
    void fetchCars();
    void fetchPhases(buildListId);
  }, [
    buildListId,
    refreshKey,
    fetchBuildListParts,
    fetchCategories,
    fetchPartManufacturers,
    fetchCars,
    fetchPhases,
  ]);

  // Helper function to check if user can edit a specific build list part
  const canEditBuildListPart = (buildListPart: BuildListPartReadWithPart) => {
    if (!currentUser) return false;
    return buildListPart.added_by === currentUser.id;
  };

  // Helper function to check if user can delete a specific build list part
  const canDeleteBuildListPart = (buildListPart: BuildListPartReadWithPart) => {
    if (!currentUser) return false;
    return (
      buildListPart.added_by === currentUser.id ||
      currentUser.is_admin ||
      currentUser.is_superuser
    );
  };

  const handleEdit = (buildListPart: BuildListPartReadWithPart) => {
    if (!canEditBuildListPart(buildListPart)) {
      return;
    }
    setEditingPart(buildListPart);
    setIsEditFormOpen(true);
  };

  const handleEditSubmit = async (
    _buildListPartId: string,
    data: BuildListPartUpdate
  ) => {
    try {
      setIsUpdating(true);
      await buildListPartsApi.updateBuildListPart(
        buildListId,
        editingPart!.part_id,
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

  const handleDelete = (buildListPartId: string) => {
    // Find the build list part to get the part_id
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

    // Find the build list part to get the part_id
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
        buildListPart.part_id
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

  const handleAddPhase = async () => {
    const name = newPhaseName.trim();
    if (!name) return;
    setPhaseError(null);
    setIsAddingPhase(true);
    try {
      await buildListsApi.createPhase(buildListId, { name });
      setNewPhaseName('');
      void fetchPhases(buildListId);
    } catch (err) {
      setPhaseError(err instanceof Error ? err.message : 'Failed to add phase');
    } finally {
      setIsAddingPhase(false);
    }
  };

  const handleStartEditPhase = (phase: BuildListPhaseRead) => {
    setEditingPhaseId(phase.id);
    setEditingPhaseName(phase.name);
    setPhaseError(null);
  };

  const handleSaveEditPhase = async () => {
    if (editingPhaseId == null) return;
    const name = editingPhaseName.trim();
    if (!name) return;
    setPhaseError(null);
    try {
      await buildListPhasesApi.updatePhase(editingPhaseId, { name });
      setEditingPhaseId(null);
      setEditingPhaseName('');
      void fetchPhases(buildListId);
    } catch (err) {
      setPhaseError(
        err instanceof Error ? err.message : 'Failed to update phase'
      );
    }
  };

  const handleCancelEditPhase = () => {
    setEditingPhaseId(null);
    setEditingPhaseName('');
    setPhaseError(null);
  };

  const handleDeletePhase = async () => {
    if (deletingPhaseId == null) return;
    try {
      await buildListPhasesApi.deletePhase(deletingPhaseId);
      setDeletingPhaseId(null);
      void fetchPhases(buildListId);
      void fetchBuildListParts(buildListId);
    } catch (err) {
      setPhaseError(
        err instanceof Error ? err.message : 'Failed to delete phase'
      );
    }
  };

  const handleCloseDeletePhaseDialog = () => {
    setDeletingPhaseId(null);
    setPhaseError(null);
  };

  const handleTogglePurchased = useCallback(
    async (buildListPart: BuildListPartReadWithPart) => {
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
          buildListPart.part_id,
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
    (part: BuildListPartReadWithPart) => {
      void handleTogglePurchased(part);
    },
    [handleTogglePurchased]
  );

  const parts = localBuildListParts || buildListParts || [];
  const hasCarMismatchParts =
    buildListCarId != null &&
    parts.some((p) => {
      const gp = p.part;
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

  const phasesList: BuildListPhaseRead[] = phases ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-4 flex-wrap">
          <SectionHeader title={title} />
          {/* View mode: By category | By phase */}
          <div className="flex gap-2 pb-2">
            <button
              type="button"
              onClick={() => setViewMode('category')}
              className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
                viewMode === 'category'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              By category
            </button>
            <button
              type="button"
              onClick={() => setViewMode('phase')}
              className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
                viewMode === 'phase'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              By phase
            </button>
          </div>
        </div>
        {canManageParts && onAddPartClick && (
          <ActionButton onClick={() => void onAddPartClick()}>
            Add Part
          </ActionButton>
        )}
      </div>

      {canManageParts && (
        <Card className="p-4">
          <h3 className="text-base font-semibold text-gray-200 mb-2">Phases</h3>
          <p className="text-sm text-gray-400 mb-3">
            Organize parts into phases or priority groups. Assign phases when
            adding or editing parts.
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            <input
              type="text"
              value={newPhaseName}
              onChange={(e) => setNewPhaseName(e.target.value)}
              placeholder="New phase name"
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white text-sm w-48 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
            <ActionButton
              onClick={() => void handleAddPhase()}
              disabled={!newPhaseName.trim() || isAddingPhase}
            >
              {isAddingPhase ? 'Adding...' : 'Add phase'}
            </ActionButton>
          </div>
          {phaseError && (
            <div className="text-red-400 text-sm mb-2">{phaseError}</div>
          )}
          {phasesList.length > 0 ? (
            <ul className="space-y-2">
              {[...phasesList]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((phase) => (
                  <li
                    key={phase.id}
                    className="flex items-center gap-2 py-1 border-b border-gray-700 last:border-0"
                  >
                    {editingPhaseId === phase.id ? (
                      <>
                        <input
                          type="text"
                          value={editingPhaseName}
                          onChange={(e) => setEditingPhaseName(e.target.value)}
                          className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                        />
                        <SecondaryButton
                          type="button"
                          onClick={handleCancelEditPhase}
                        >
                          Cancel
                        </SecondaryButton>
                        <ActionButton
                          type="button"
                          onClick={() => void handleSaveEditPhase()}
                        >
                          Save
                        </ActionButton>
                      </>
                    ) : (
                      <>
                        <span className="text-gray-200 flex-1">
                          {phase.name}
                        </span>
                        <SecondaryButton
                          type="button"
                          onClick={() => handleStartEditPhase(phase)}
                        >
                          Edit
                        </SecondaryButton>
                        <button
                          type="button"
                          onClick={() => setDeletingPhaseId(phase.id)}
                          className="text-red-400 hover:text-red-300 text-sm"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">
              No phases yet. Add one above to group parts by phase.
            </p>
          )}
        </Card>
      )}

      <DeleteConfirmationDialog
        isOpen={deletingPhaseId !== null}
        onClose={handleCloseDeletePhaseDialog}
        onConfirm={() => void handleDeletePhase()}
        itemName={
          phasesList.find((p) => p.id === deletingPhaseId)?.name ?? 'phase'
        }
        itemType="phase"
        isProcessing={false}
        error={null}
      />

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
        viewMode={viewMode}
        phases={phasesList}
        part_manufacturers={part_manufacturers}
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
          phases={phasesList}
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
          buildListParts?.find((p) => p.id === deletingPartId)?.part.name || ''
        }
        itemType="part"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
};

export default BuildListParts;
