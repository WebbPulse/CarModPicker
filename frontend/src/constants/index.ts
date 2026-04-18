/**
 * Centralized constants for the frontend application
 * All pagination limits, display limits, and other configuration values should be defined here
 */

// ============================================================================
// Pagination Constants
// ============================================================================

/** Default items per page for admin pages (bug reports, user management, reports) */
export const ADMIN_ITEMS_PER_PAGE = 10;

/** Items per page for build lists in builder view */
export const BUILDER_ITEMS_PER_PAGE = 8;

/** Items per page for global parts catalog */
export const GLOBAL_PARTS_ITEMS_PER_PAGE = 10;

/** Items per page for build lists catalog (when filtering by vehicle) */
export const BUILD_LISTS_CATALOG_ITEMS_PER_PAGE = 20;

/** Items per page when showing all build lists (no vehicle filter) */
export const BUILD_LISTS_ALL_PAGE_SIZE = 12;

/** Posts per page for build logs */
export const BUILD_LOG_POSTS_PER_PAGE = 10;

// ============================================================================
// Search Constants
// ============================================================================

/** Default search results limit */
export const SEARCH_RESULTS_LIMIT = 20;

/** Initial display limits for search results by category */
export const SEARCH_INITIAL_LIMITS = {
  build_lists: 8,
  users: 8,
  parts: 4,
} as const;

/** Increment amount when loading more search results */
export const SEARCH_LOAD_MORE_INCREMENT = {
  build_lists: 8,
  users: 8,
  parts: 4,
} as const;

// ============================================================================
// Display/Featured Limits
// ============================================================================

/** Number of featured build lists to display */
export const FEATURED_BUILD_LISTS_LIMIT = 4;

/** Number of featured items to display on home page */
export const HOME_FEATURED_ITEMS_LIMIT = 6;

/** Number of build lists to show in car view */
export const CAR_VIEW_BUILD_LISTS_LIMIT = 5;

// ============================================================================
// Large Fetch Limits
// ============================================================================

/**
 * Large limit used when fetching all items (cars, build lists, etc.)
 * Used for dropdowns, selects, and other scenarios where we need all data
 */
export const LARGE_FETCH_LIMIT = 1000;

// ============================================================================
// Cache Constants
// ============================================================================

/** Cache duration in milliseconds (30 seconds) */
export const CACHE_DURATION_MS = 30000;

// ============================================================================
// UI Constants
// ============================================================================

/** Maximum number of page buttons to show in pagination component */
export const PAGINATION_MAX_VISIBLE_PAGES = 10;

// ============================================================================
// Form/Input Constants
// ============================================================================

/** Maximum length for 2FA verification codes */
export const TWO_FACTOR_AUTH_CODE_LENGTH = 6;

// ============================================================================
// Builder-Specific Constants
// ============================================================================

/** Build lists per page on first page (accounts for create button) */
export const BUILDER_FIRST_PAGE_BUILD_LISTS = 7;

/** Build lists per page on subsequent pages */
export const BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS = 8;
