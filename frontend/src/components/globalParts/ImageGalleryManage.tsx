import { useState } from 'react';
import { globalPartsApi } from '../../services/Api';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import DeleteConfirmationDialog from '../common/DeleteConfirmationDialog';
import { ErrorAlert } from '../common/Alerts';

const CAROUSEL_SIZE = 5;

interface ImageGalleryManageProps {
  /** Primary image URL (fallback when no gallery) */
  imageUrl?: string | null;
  /** Gallery image URLs (presigned from API) */
  imageUrls?: string[] | null;
  altText: string;
  /** Global part ID (required for manage actions) */
  partId: number;
  /** Called after an image is removed or primary is changed so parent can refresh part */
  onPartUpdated: () => void | Promise<void>;
}

/**
 * Displays part images with management actions for users with edit permission:
 * set primary image, remove image. Uses the same carousel/grid layout as ImageGallery.
 */
function ImageGalleryManage({
  imageUrl,
  imageUrls,
  altText,
  partId,
  onPartUpdated,
}: ImageGalleryManageProps) {
  const [showAll, setShowAll] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [imageIndexToRemove, setImageIndexToRemove] = useState<number | null>(
    null
  );
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [settingPrimaryIndex, setSettingPrimaryIndex] = useState<
    number | null
  >(null);

  const allUrls =
    imageUrls && imageUrls.length > 0 ? imageUrls : imageUrl ? [imageUrl] : [];

  const handleSetPrimary = async (index: number) => {
    if (index < 0 || index >= allUrls.length) return;
    setSettingPrimaryIndex(index);
    setRemoveError(null);
    try {
      await globalPartsApi.setGlobalPartPrimaryImage(partId, index);
      await onPartUpdated();
    } catch (e) {
      setRemoveError(
        e instanceof Error ? e.message : 'Failed to set primary image'
      );
    } finally {
      setSettingPrimaryIndex(null);
    }
  };

  const openRemoveDialog = (index: number) => {
    setImageIndexToRemove(index);
    setRemoveError(null);
    setRemoveDialogOpen(true);
  };

  const closeRemoveDialog = () => {
    setRemoveDialogOpen(false);
    setImageIndexToRemove(null);
    setRemoveError(null);
  };

  const handleConfirmRemove = async () => {
    if (imageIndexToRemove == null) return;
    setIsRemoving(true);
    setRemoveError(null);
    try {
      await globalPartsApi.removeGlobalPartImage(partId, imageIndexToRemove);
      await onPartUpdated();
      closeRemoveDialog();
    } catch (e) {
      setRemoveError(
        e instanceof Error ? e.message : 'Failed to remove image'
      );
    } finally {
      setIsRemoving(false);
    }
  };

  if (allUrls.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center border border-gray-600 bg-gray-800/50 rounded-lg p-4">
        <p className="text-gray-400">No images available for this part.</p>
      </div>
    );
  }

  const visibleUrls = showAll ? allUrls : allUrls.slice(0, CAROUSEL_SIZE);
  const hasMore = allUrls.length > CAROUSEL_SIZE;
  const remainingCount = allUrls.length - CAROUSEL_SIZE;

  return (
    <div className="space-y-3">
      {removeError && <ErrorAlert message={removeError} />}
      <div
        className={
          showAll
            ? 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3'
            : 'flex gap-3 overflow-x-auto pb-2 rounded-lg'
        }
      >
        {visibleUrls.map((url, idx) => {
          const imageIndex = idx;
          const isPrimary = imageIndex === 0;
          const isSettingPrimary = settingPrimaryIndex === imageIndex;

          return (
            <div
              key={`${url}-${imageIndex}`}
              className={
                showAll
                  ? 'aspect-square rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50 relative group'
                  : 'shrink-0 w-40 h-40 rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50 relative group'
              }
            >
              <ImageWithPlaceholder
                srcUrl={url}
                altText={`${altText} - image ${imageIndex + 1}`}
                imageClassName="w-full h-full object-cover"
                containerClassName="w-full h-full"
                fallbackText="Failed to load"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2 p-2">
                {isPrimary ? (
                  <span className="text-xs font-medium text-emerald-300 bg-emerald-900/80 px-2 py-1 rounded">
                    Primary
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleSetPrimary(imageIndex)}
                    disabled={isSettingPrimary}
                    className="text-xs font-medium text-white bg-primary-600 hover:bg-primary-500 px-2 py-1 rounded disabled:opacity-50"
                  >
                    {isSettingPrimary ? 'Updating…' : 'Set as primary'}
                  </button>
                )}
                  <button
                  type="button"
                  onClick={() => openRemoveDialog(imageIndex)}
                  className="text-xs font-medium text-white bg-red-600 hover:bg-red-500 px-2 py-1 rounded"
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {hasMore && !showAll && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="text-sm text-primary-400 hover:text-primary-300 font-medium transition-colors"
        >
          Show {remainingCount} more image{remainingCount !== 1 ? 's' : ''}
        </button>
      )}
      {hasMore && showAll && (
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="text-sm text-gray-400 hover:text-gray-300 font-medium transition-colors"
        >
          Show less
        </button>
      )}

      <DeleteConfirmationDialog
        isOpen={removeDialogOpen}
        onClose={closeRemoveDialog}
        onConfirm={() => void handleConfirmRemove()}
        itemName="this image"
        itemType="image"
        isProcessing={isRemoving}
        error={removeError}
      />
    </div>
  );
}

export default ImageGalleryManage;
