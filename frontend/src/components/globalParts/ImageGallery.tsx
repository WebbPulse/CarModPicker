import { useState } from 'react';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';

const CAROUSEL_SIZE = 5;

interface ImageGalleryProps {
  /** Primary image URL (fallback when no gallery) */
  imageUrl?: string | null;
  /** Gallery image URLs (presigned from API) */
  imageUrls?: string[] | null;
  altText: string;
}

/**
 * Displays a carousel of part images with first 5 visible and "Show more" to expand.
 */
function ImageGallery({ imageUrl, imageUrls, altText }: ImageGalleryProps) {
  const [showAll, setShowAll] = useState(false);

  // Build display list: prefer image_urls, fallback to single image_url
  const allUrls =
    imageUrls && imageUrls.length > 0 ? imageUrls : imageUrl ? [imageUrl] : [];

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
      <div
        className={
          showAll
            ? 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3'
            : 'flex gap-3 overflow-x-auto pb-2 rounded-lg'
        }
      >
        {visibleUrls.map((url, idx) => (
          <div
            key={url}
            className={
              showAll
                ? 'aspect-square rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50'
                : 'shrink-0 w-40 h-40 rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50'
            }
          >
            <ImageWithPlaceholder
              srcUrl={url}
              altText={`${altText} - image ${idx + 1}`}
              imageClassName="w-full h-full object-cover"
              containerClassName="w-full h-full"
              fallbackText="Failed to load"
            />
          </div>
        ))}
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
    </div>
  );
}

export default ImageGallery;
