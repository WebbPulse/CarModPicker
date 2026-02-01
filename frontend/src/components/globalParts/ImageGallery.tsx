import { useState } from 'react';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';

const CAROUSEL_SIZE = 5;

interface ImageGalleryProps {
  /** Primary image URL (fallback when no gallery) */
  imageUrl?: string | null;
  /** Gallery image URLs (presigned from API) */
  imageUrls?: string[] | null;
  altText: string;
  /** When "hero", show large primary image with carousel of others beneath */
  layout?: 'carousel' | 'hero';
}

/**
 * Displays part images: carousel (default) or hero (large primary + carousel of others).
 */
function ImageGallery({
  imageUrl,
  imageUrls,
  altText,
  layout = 'carousel',
}: ImageGalleryProps) {
  const [showAll, setShowAll] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

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

  if (layout === 'hero') {
    const displayIndex = Math.min(selectedIndex, allUrls.length - 1);
    const selectedUrl = allUrls[displayIndex];

    return (
      <div className="space-y-3">
        {/* Large image: shows whichever thumbnail is selected (primary by default) */}
        <div className="aspect-[4/3] max-h-[420px] w-full rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50">
          <ImageWithPlaceholder
            srcUrl={selectedUrl}
            altText={`${altText} - image ${displayIndex + 1}`}
            imageClassName="w-full h-full object-contain"
            containerClassName="w-full h-full"
            fallbackText="Failed to load"
          />
        </div>
        {/* Selector carousel: click a thumbnail to show it in the large view */}
        {allUrls.length > 1 && (
          <div className="flex gap-3 overflow-x-auto pb-2 rounded-lg">
            {allUrls.map((url, idx) => (
              <button
                type="button"
                key={url}
                onClick={() => setSelectedIndex(idx)}
                className={`shrink-0 w-24 h-24 rounded-lg overflow-hidden border-2 bg-gray-800/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${
                  idx === displayIndex
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'border-gray-600 hover:border-gray-500'
                }`}
              >
                <ImageWithPlaceholder
                  srcUrl={url}
                  altText={`${altText} - image ${idx + 1}`}
                  imageClassName="w-full h-full object-cover"
                  containerClassName="w-full h-full"
                  fallbackText="Failed to load"
                />
              </button>
            ))}
          </div>
        )}
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
