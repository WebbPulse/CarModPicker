import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi, buildListsApi } from '../../services/Api';
import type {
  BuildListPartCreate,
  BuildListRead,
  GlobalPartReadWithVotes,
} from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import Dialog from '../common/Dialog';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import LoadingSpinner from '../common/LoadingSpinner';

interface AddToBuildListDialogProps {
  isOpen: boolean;
  onClose: () => void;
  globalPart: GlobalPartReadWithVotes | null;
  onPartAdded: () => void;
}

function AddToBuildListDialog({
  isOpen,
  onClose,
  globalPart,
  onPartAdded,
}: AddToBuildListDialogProps) {
  const { user } = useAuth();
  const [selectedBuildListIds, setSelectedBuildListIds] = useState<Set<number>>(
    () => new Set()
  );
  const [quantity, setQuantity] = useState(1);
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildLists, setBuildLists] = useState<BuildListRead[]>([]);
  const [isLoadingBuildLists, setIsLoadingBuildLists] = useState(false);
  const [buildListsError, setBuildListsError] = useState<string | null>(null);

  const toggleBuildListSelection = (id: number) => {
    setSelectedBuildListIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Check if any selected build list is for a different car model than the part
  const hasCarMismatch =
    globalPart != null &&
    !globalPart.is_universal &&
    (globalPart.car_ids?.length ?? 0) > 0 &&
    Array.from(selectedBuildListIds).some((blId) => {
      const buildList = buildLists.find((bl) => bl.id === blId);
      return (
        buildList?.car_id != null &&
        !globalPart.car_ids.includes(buildList.car_id)
      );
    });

  useEffect(() => {
    if (isOpen && user) {
      const fetchUserBuildLists = async () => {
        try {
          setIsLoadingBuildLists(true);
          const response = await buildListsApi.getBuildListsByUser(user.id);
          setBuildLists(response.data);
        } catch (error) {
          setBuildListsError(
            error instanceof Error
              ? error.message
              : 'Failed to load build lists'
          );
        } finally {
          setIsLoadingBuildLists(false);
        }
      };

      void fetchUserBuildLists();
    }
  }, [isOpen, user]);

  useEffect(() => {
    if (isOpen) {
      setSelectedBuildListIds(new Set());
      setQuantity(1);
      setError(null);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!globalPart || selectedBuildListIds.size === 0) {
      setError('Please select at least one build list');
      return;
    }

    setIsAdding(true);
    setError(null);

    const buildListPartData: BuildListPartCreate = {
      quantity: Math.max(1, quantity),
      notes: null,
    };

    try {
      for (const buildListId of selectedBuildListIds) {
        await buildListPartsApi.addGlobalPartToBuildList(
          buildListId,
          globalPart.id,
          buildListPartData
        );
      }

      onPartAdded();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to add part to build list'
      );
    } finally {
      setIsAdding(false);
    }
  };

  if (!globalPart) {
    return null;
  }

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={`Add ${globalPart.name} to Build List`}
    >
      <form
        onSubmit={(e) => {
          void handleSubmit(e);
        }}
        className="space-y-6"
      >
        {error && <ErrorAlert message={error} />}

        {/* Part Preview */}
        <Card>
          <div className="mb-4">
            <p className="text-sm text-neutral-400">
              This will add the part to your build list where you can add notes
              and customize it.
            </p>
          </div>
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <ImageWithPlaceholder
                srcUrl={globalPart.image_url ?? null}
                altText={globalPart.name}
                imageClassName="w-24 h-24 object-cover rounded-lg"
                containerClassName="w-24 h-24 flex justify-center items-center"
                fallbackText="No image"
              />
            </div>
            <div className="flex-grow">
              <h3 className="text-lg font-semibold text-white mb-2">
                {globalPart.name}
              </h3>
              {globalPart.brand && (
                <p className="text-sm text-gray-400 mb-1">{globalPart.brand}</p>
              )}
              {globalPart.best_price_cents != null && (
                <p className="text-sm font-medium text-green-400">
                  ${(globalPart.best_price_cents / 100).toFixed(2)}
                </p>
              )}
              {globalPart.description && (
                <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                  {globalPart.description.length > 120
                    ? `${globalPart.description.slice(0, 120).trim()}…`
                    : globalPart.description}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Quantity */}
        <div className="space-y-2">
          <label
            htmlFor="add-to-build-list-quantity"
            className="block text-sm font-medium text-neutral-200"
          >
            Quantity
          </label>
          <input
            id="add-to-build-list-quantity"
            type="number"
            min={1}
            max={999}
            value={quantity}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!Number.isNaN(v) && v >= 1) setQuantity(v);
            }}
            className="w-24 px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        {/* Build List Selection */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-neutral-200">
            Select Build List(s)
          </h3>
          <p className="text-sm text-neutral-400">
            Select one or more build lists, then add the part to all selected at
            once.
          </p>

          {isLoadingBuildLists ? (
            <LoadingSpinner />
          ) : buildListsError ? (
            <ErrorAlert message="Failed to load build lists" />
          ) : buildLists && buildLists.length > 0 ? (
            <div className="max-h-64 overflow-y-auto space-y-1">
              {buildLists.map((buildList: BuildListRead) => {
                const isSelected = selectedBuildListIds.has(buildList.id);
                const isCarMismatch =
                  !globalPart.is_universal &&
                  (globalPart.car_ids?.length ?? 0) > 0 &&
                  buildList.car_id != null &&
                  !globalPart.car_ids.includes(buildList.car_id);
                return (
                  <Card
                    key={buildList.id}
                    padding="sm"
                    className={`cursor-pointer transition-all duration-200 flex items-center gap-2 py-2 px-3 min-h-0 ${
                      isSelected
                        ? 'border-2 border-primary-500 bg-primary-500/25 shadow-md ring-2 ring-primary-500/30'
                        : 'border border-transparent hover:bg-white/5 hover:border-white/20'
                    }`}
                    onClick={() => toggleBuildListSelection(buildList.id)}
                  >
                    <div
                      className={`flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                        isSelected
                          ? 'bg-primary-500 border-primary-500'
                          : 'border-neutral-500 bg-transparent'
                      }`}
                    >
                      {isSelected && (
                        <svg
                          className="w-2.5 h-2.5 text-white"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2.5}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      )}
                    </div>
                    <div className="flex-grow min-w-0 flex items-center gap-2 overflow-hidden">
                      <span className="text-sm font-medium text-gray-200 truncate">
                        {buildList.name}
                      </span>
                      {isCarMismatch && (
                        <span
                          className="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          title="This build list is for a different car model than this part"
                        >
                          Different car
                        </span>
                      )}
                      {buildList.description && (
                        <span className="flex-shrink text-xs text-gray-500 truncate max-w-[8rem]">
                          {buildList.description.length > 40
                            ? `${buildList.description.slice(0, 40).trim()}…`
                            : buildList.description}
                        </span>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-neutral-400">
              <p>No build lists found.</p>
              <p className="text-sm mt-2">
                Create a build list first to add parts to it.
              </p>
            </div>
          )}
        </div>

        {/* Car mismatch disclaimer */}
        {hasCarMismatch && (
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
                  Car mismatch
                </p>
                <p className="text-sm text-amber-200/90 mt-1">
                  This part is associated with a different car model than one or
                  more of the selected build lists. Parts may not be compatible
                  across vehicles. Please verify fitment and do your own due
                  diligence before adding.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end space-x-3 pt-4">
          <SecondaryButton type="button" onClick={onClose} disabled={isAdding}>
            Cancel
          </SecondaryButton>
          <ActionButton
            type="submit"
            disabled={isAdding || selectedBuildListIds.size === 0}
          >
            {isAdding ? (
              <LoadingSpinner />
            ) : selectedBuildListIds.size === 1 ? (
              'Add to Build List'
            ) : (
              `Add to ${selectedBuildListIds.size} Build Lists`
            )}
          </ActionButton>
        </div>
      </form>
    </Dialog>
  );
}

export default AddToBuildListDialog;
