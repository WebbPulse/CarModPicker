/**
 * Asset path helpers for static UI assets (manufacturer logos, part category icons).
 *
 * Assets live in public/assets/ and are served at /assets/:
 * - public/assets/manufacturers/<slug>.(svg|png|webp) → /assets/manufacturers/<slug>.(svg|png|webp)
 * - public/assets/categories/<name>.(svg|png|webp) → /assets/categories/<name>.(svg|png|webp)
 *
 * Use these helpers so the app resolves paths consistently and can fall back when a file is missing.
 */

/**
 * Convert a manufacturer/make name to a URL-safe slug for filenames.
 * e.g. "Aston Martin" → "aston-martin", "Honda" → "honda"
 */
export function manufacturerNameToSlug(make: string): string {
  return make
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/**
 * Return the base path for a manufacturer logo (no extension).
 * Use with <img src={getManufacturerLogoPath(make) + '.svg'} /> or let the UI try extensions.
 */
export function getManufacturerLogoPath(make: string): string {
  const slug = manufacturerNameToSlug(make);
  return `/assets/manufacturers/${slug}`;
}

/**
 * Return the first likely logo URL for a manufacturer (with .svg extension).
 * The UI should handle 404 (e.g. onError fallback to text). Add more extensions if you add PNGs.
 */
export function getManufacturerLogoUrl(make: string): string {
  return getManufacturerLogoPath(make) + '.svg';
}

/**
 * Part category names from backend part_categories_data (canonical list for asset filenames).
 * Category assets should be named exactly like these (e.g. exhaust.svg, suspension.svg).
 */
export const PART_CATEGORY_NAMES = [
  'exhaust',
  'suspension',
  'engine',
  'wheels',
  'body',
  'interior',
  'brakes',
] as const;

export type PartCategoryName = (typeof PART_CATEGORY_NAMES)[number];

/**
 * Return the base path for a part category icon (no extension).
 * categoryName should match backend part_categories_data name (e.g. "exhaust", "suspension").
 */
export function getPartCategoryAssetPath(categoryName: string): string {
  const slug = categoryName.trim().toLowerCase().replace(/\s+/g, '-');
  return `/assets/categories/${slug}`;
}

/**
 * Return a part category icon URL (with .svg extension).
 * Use category.name from CategoryResponse for consistency with backend.
 */
export function getPartCategoryAssetUrl(categoryName: string): string {
  return getPartCategoryAssetPath(categoryName) + '.svg';
}

/**
 * Convert a model or generation name to a URL-safe slug for filenames.
 * e.g. "10th Gen" → "10th-gen", "Civic" → "civic"
 */
export function modelOrGenerationToSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/**
 * Return the base path for an optional generation image.
 * Structure: /assets/generations/<make-slug>/<model-slug>/<generation-slug>
 * Use when you have static fallback images (e.g. generations/honda/civic/10th-gen.svg).
 */
export function getGenerationAssetPath(
  make: string,
  model: string,
  generationName: string
): string {
  const makeSlug = manufacturerNameToSlug(make);
  const modelSlug = modelOrGenerationToSlug(model);
  const genSlug = modelOrGenerationToSlug(generationName);
  return `/assets/generations/${makeSlug}/${modelSlug}/${genSlug}`;
}

/** Return a generation image URL (with .svg extension). */
export function getGenerationAssetUrl(
  make: string,
  model: string,
  generationName: string
): string {
  return getGenerationAssetPath(make, model, generationName) + '.svg';
}
