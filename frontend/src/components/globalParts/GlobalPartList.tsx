import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useContainerWidth } from '../../hooks/useContainerWidth';
import {
  carsApi,
  globalPartVotesApi,
  globalPartsApi,
} from '../../services/Api';
import type {
  BrandResponse,
  CarRead,
  CategoryResponse,
  GlobalPartReadWithVotes,
  PaginationInfo,
} from '../../types/Api';

import { CACHE_DURATION_MS } from '../../constants';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import VoteButtons from './VoteButtons';

// Simple cache for global parts data to improve UX when switching between pages
interface CachedData {
  data: GlobalPartReadWithVotes[];
  pagination: PaginationInfo | null;
  timestamp: number;
}
const globalPartsCache = new Map<string, CachedData>();

// Persistent car lookup cache — populated on-demand, survives page navigations
const carByIdCache: Record<string, CarRead> = {};

type TableColumnKey =
  | 'part'
  | 'brand'
  | 'part_number'
  | 'category'
  | 'fit'
  | 'rating'
  | 'price'
  | 'actions';

// Lower = higher priority (kept longer). `part` and `price` are pinned and never drop.
const COLUMN_PRIORITY: Record<TableColumnKey, number> = {
  part: 0,
  price: 1,
  rating: 2,
  brand: 3,
  category: 4,
  fit: 5,
  part_number: 6,
  actions: 7,
};

// Minimum width where a column's content renders without truncation for typical
// values (brand names, part numbers, fit strings, etc.). A column is dropped
// once the sum of these values across visible columns would exceed the
// container width. Also used as the flex share for proportional width
// distribution among the surviving columns.
const COLUMN_MIN_WIDTH: Record<TableColumnKey, number> = {
  part: 280,
  price: 100,
  fit: 160,
  rating: 160,
  actions: 200,
  brand: 160,
  part_number: 150,
  category: 140,
};

const DEFAULT_CATEGORIES: CategoryResponse[] = [];
const DEFAULT_BRANDS: BrandResponse[] = [];
const DEFAULT_CARS_BY_ID: Record<string, CarRead> = {};

type SortColumn =
  | 'part'
  | 'brand'
  | 'part_number'
  | 'category'
  | 'fit'
  | 'rating'
  | 'price';

interface SortableThProps {
  column: SortColumn;
  children: React.ReactNode;
  align?: 'left' | 'right';
  sortColumn: SortColumn;
  sortDirection: 'asc' | 'desc';
  onSort: (column: SortColumn) => void;
}

function SortableTh({
  column,
  children,
  align = 'left',
  sortColumn,
  sortDirection,
  onSort,
}: SortableThProps) {
  const isActive = sortColumn === column;
  return (
    <th
      className={`px-4 py-3 font-medium whitespace-nowrap cursor-pointer select-none hover:bg-gray-700/50 transition-colors ${
        align === 'right' ? 'text-right' : 'text-left'
      } ${isActive ? 'text-indigo-300' : 'text-gray-400'}`}
      onClick={() => onSort(column)}
      role="columnheader"
      aria-sort={
        isActive
          ? sortDirection === 'asc'
            ? 'ascending'
            : 'descending'
          : undefined
      }
    >
      <span
        className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}
      >
        {children}
        {isActive && (
          <span className="text-indigo-400" aria-hidden>
            {sortDirection === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </span>
    </th>
  );
}

function getCacheKey(params?: {
  skip?: number;
  limit?: number;
  category_id?: string;
  category_ids?: string[];
  car_id?: string;
  car_ids?: string[];
  brand_id?: string;
  brand_ids?: string[];
  user_id?: string;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  universal?: boolean;
}): string {
  return JSON.stringify(params || {});
}

/** Map API sort param to (sortColumn, sortDirection) for table header display */
function sortParamToColumnAndDirection(sortParam: string): {
  sortColumn: SortColumn;
  sortDirection: 'asc' | 'desc';
} {
  const map: Record<
    string,
    { sortColumn: SortColumn; sortDirection: 'asc' | 'desc' }
  > = {
    votes_desc: { sortColumn: 'rating', sortDirection: 'desc' },
    votes_asc: { sortColumn: 'rating', sortDirection: 'asc' },
    lowest_price: { sortColumn: 'price', sortDirection: 'asc' },
    highest_price: { sortColumn: 'price', sortDirection: 'desc' },
    name_asc: { sortColumn: 'part', sortDirection: 'asc' },
    name_desc: { sortColumn: 'part', sortDirection: 'desc' },
    part_number_asc: { sortColumn: 'part_number', sortDirection: 'asc' },
    part_number_desc: { sortColumn: 'part_number', sortDirection: 'desc' },
    brand_asc: { sortColumn: 'brand', sortDirection: 'asc' },
    brand_desc: { sortColumn: 'brand', sortDirection: 'desc' },
    category_asc: { sortColumn: 'category', sortDirection: 'asc' },
    category_desc: { sortColumn: 'category', sortDirection: 'desc' },
    fit_asc: { sortColumn: 'fit', sortDirection: 'asc' },
    fit_desc: { sortColumn: 'fit', sortDirection: 'desc' },
  };
  return map[sortParam] ?? { sortColumn: 'rating', sortDirection: 'desc' };
}

/** Map (sortColumn, sortDirection) to API sort param when user clicks column */
function columnAndDirectionToSortParam(
  column: SortColumn,
  direction: 'asc' | 'desc'
): string {
  const key = `${column}_${direction}`;
  const map: Record<string, string> = {
    part_asc: 'name_asc',
    part_desc: 'name_desc',
    brand_asc: 'brand_asc',
    brand_desc: 'brand_desc',
    part_number_asc: 'part_number_asc',
    part_number_desc: 'part_number_desc',
    category_asc: 'category_asc',
    category_desc: 'category_desc',
    fit_asc: 'fit_asc',
    fit_desc: 'fit_desc',
    rating_asc: 'votes_asc',
    rating_desc: 'votes_desc',
    price_asc: 'lowest_price',
    price_desc: 'highest_price',
  };
  return map[key] ?? 'votes_desc';
}

function getCachedData(cacheKey: string): CachedData | null {
  const cached = globalPartsCache.get(cacheKey);
  if (!cached) return null;

  // Check if cache is still valid
  const now = Date.now();
  if (now - cached.timestamp > CACHE_DURATION_MS) {
    globalPartsCache.delete(cacheKey);
    return null;
  }

  return cached;
}

interface GlobalPartListProps {
  params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    category_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    brand_id?: string;
    brand_ids?: string[];
    user_id?: string;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    universal?: boolean;
  };
  data?: GlobalPartReadWithVotes[]; // Optional: pass pre-fetched data instead of fetching
  pagination?: PaginationInfo | null; // Optional: pass pagination info when using pre-fetched data
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    partId: string,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
  onAddToBuildList?: (globalPart: GlobalPartReadWithVotes) => void;
  showAddToBuildListButton?: boolean;
  onEdit?: (globalPart: GlobalPartReadWithVotes) => void;
  onDelete?: (globalPart: GlobalPartReadWithVotes) => void;
  canEdit?: (globalPart: GlobalPartReadWithVotes) => boolean;
  canDelete?: (globalPart: GlobalPartReadWithVotes) => boolean;
  onPaginationChange?: (pagination: PaginationInfo | null) => void;
  /** When provided with onSortChange, sort is controlled: parent passes sortParam (API value) and is notified on change. Enables server-side sort for full result set. */
  sortParam?: string;
  /** When controlled: called with new API sort param. When uncontrolled: called with no args when sort changes (e.g. to reset pagination). */
  onSortChange?: (newSortParam?: string) => void;
  /** Table layout: dense columns (Part | Brand | P/N | Category | Fit | Rating | Price). Requires categories for Category column, brands for Brand column lookup. */
  layout?: 'card' | 'table';
  categories?: CategoryResponse[];
  brands?: BrandResponse[];
  /** Map of car ID to CarRead for Fit column car names. */
  carsById?: Record<string, CarRead>;
}

const fetchGlobalPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: string;
  category_ids?: string[];
  car_id?: string;
  car_ids?: string[];
  brand_id?: string;
  brand_ids?: string[];
  user_id?: string;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  universal?: boolean;
}) => globalPartsApi.getGlobalPartsWithVotes(params);

function GlobalPartList({
  params,
  data: providedData,
  pagination: providedPagination,
  refreshKey = 0,
  title = 'Parts Catalog',
  emptyMessage = 'No parts found.',
  showVoteButtons = false,
  onVoteUpdate,
  onAddToBuildList,
  showAddToBuildListButton = false,
  onEdit,
  onDelete,
  canEdit,
  canDelete,
  onPaginationChange,
  onSortChange,
  sortParam: controlledSortParam,
  layout = 'card',
  categories = DEFAULT_CATEGORIES,
  brands = DEFAULT_BRANDS,
  carsById = DEFAULT_CARS_BY_ID,
}: GlobalPartListProps) {
  const [localSortColumn, setLocalSortColumn] = useState<SortColumn>('rating');
  const [localSortDirection, setLocalSortDirection] = useState<'asc' | 'desc'>(
    'desc'
  );

  const isControlledSort = controlledSortParam != null && onSortChange != null;
  const { sortColumn, sortDirection } = isControlledSort
    ? sortParamToColumnAndDirection(controlledSortParam)
    : { sortColumn: localSortColumn, sortDirection: localSortDirection };

  const [tableWrapperRef, containerWidth] = useContainerWidth<HTMLDivElement>();

  const tableColumnKeys = useMemo((): TableColumnKey[] => {
    const keys: TableColumnKey[] = ['part', 'brand', 'part_number'];
    if (categories.length > 0) keys.push('category');
    keys.push('fit');
    if (showVoteButtons) keys.push('rating');
    keys.push('price');
    if (showAddToBuildListButton || onEdit || onDelete) keys.push('actions');
    return keys;
  }, [
    categories.length,
    showVoteButtons,
    showAddToBuildListButton,
    onEdit,
    onDelete,
  ]);

  // Determine which columns fit in the measured container; drop lowest-priority
  // columns first. `part` and `price` are pinned (priority 0/1) and never drop —
  // if they alone overflow, horizontal scroll kicks in.
  const visibleColumns = useMemo(() => {
    if (containerWidth === 0) return tableColumnKeys;
    const kept = new Set<TableColumnKey>(tableColumnKeys);
    const dropOrder = [...tableColumnKeys].sort(
      (a, b) => COLUMN_PRIORITY[b] - COLUMN_PRIORITY[a]
    );
    let total = tableColumnKeys.reduce((s, k) => s + COLUMN_MIN_WIDTH[k], 0);
    for (const k of dropOrder) {
      if (total <= containerWidth) break;
      if (COLUMN_PRIORITY[k] <= 1) break;
      kept.delete(k);
      total -= COLUMN_MIN_WIDTH[k];
    }
    return tableColumnKeys.filter((k) => kept.has(k));
  }, [tableColumnKeys, containerWidth]);

  const totalMinWidth = useMemo(
    () => visibleColumns.reduce((s, k) => s + COLUMN_MIN_WIDTH[k], 0),
    [visibleColumns]
  );

  const handleSort = useCallback(
    (column: SortColumn) => {
      if (isControlledSort && onSortChange) {
        const nextDirection =
          sortColumn === column
            ? sortDirection === 'asc'
              ? 'desc'
              : 'asc'
            : column === 'rating' || column === 'price'
              ? 'desc'
              : 'asc';
        const newSortParam = columnAndDirectionToSortParam(
          column,
          nextDirection
        );
        onSortChange(newSortParam);
      } else {
        if (localSortColumn === column) {
          setLocalSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
        } else {
          setLocalSortColumn(column);
          setLocalSortDirection(
            column === 'rating' || column === 'price' ? 'desc' : 'asc'
          );
        }
        onSortChange?.();
      }
    },
    [isControlledSort, onSortChange, sortColumn, sortDirection, localSortColumn]
  );

  const effectiveParams = useMemo(() => {
    if (params == null) return undefined;
    if (isControlledSort) {
      return params;
    }
    return {
      ...params,
      ...(layout === 'table' &&
        localSortColumn === 'price' && { sort: 'lowest_price' as const }),
    };
  }, [params, layout, isControlledSort, localSortColumn]);

  const {
    data: paginatedResponse,
    isLoading,
    error,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  // Initialize with cached data if available (for instant display)
  const cacheKey = getCacheKey(effectiveParams);

  // Stable request key so we only refetch when the logical request changes (avoids duplicate fetches from re-renders)
  const fetchRequestKey = `${refreshKey}-${cacheKey}`;

  const [displayData, setDisplayData] = useState<GlobalPartReadWithVotes[]>(
    () => {
      if (providedData) return providedData;
      const cached = getCachedData(cacheKey);
      return cached?.data ?? [];
    }
  );
  const [displayPagination, setDisplayPagination] =
    useState<PaginationInfo | null>(() => {
      if (providedPagination) return providedPagination;
      const cached = getCachedData(cacheKey);
      return cached?.pagination ?? null;
    });

  // On-demand car lookup: fetch only the car IDs that appear in the current page
  const [localCarsById, setLocalCarsById] = useState<Record<string, CarRead>>(
    () => ({ ...carByIdCache })
  );

  useEffect(() => {
    const needed = [
      ...new Set(displayData.flatMap((p) => p.car_ids ?? [])),
    ].filter((id) => !(id in carByIdCache));
    if (!needed.length) return;

    carsApi
      .getCarsByIds(needed)
      .then((res) => {
        const incoming: Record<string, CarRead> = {};
        for (const car of res.data ?? []) {
          if (car.id != null) {
            carByIdCache[car.id] = car;
            incoming[car.id] = car;
          }
        }
        if (Object.keys(incoming).length > 0) {
          setLocalCarsById((prev) => ({ ...prev, ...incoming }));
        }
      })
      .catch(() => {});
  }, [displayData]);

  // Merge prop-supplied map (for callers that manage their own lookup) with
  // the internally-fetched map; prop values take precedence.
  const effectiveCarsById = useMemo(
    () => ({ ...localCarsById, ...carsById }),
    [localCarsById, carsById]
  );

  // Only fetch if data is not provided; run when fetchRequestKey changes (not on every params reference change)
  useEffect(() => {
    if (!providedData) {
      const cached = getCachedData(cacheKey);
      if (cached) {
        setDisplayData(cached.data);
        setDisplayPagination(cached.pagination);
      }
      void fetchGlobalParts(effectiveParams);
    }
  }, [fetchRequestKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only refetch when request key changes; effectiveParams/cacheKey used inside

  // Update display data when fresh data arrives
  useEffect(() => {
    if (paginatedResponse?.data) {
      setDisplayData(paginatedResponse.data);
      setDisplayPagination(paginatedResponse.pagination ?? null);
      // Update cache
      globalPartsCache.set(cacheKey, {
        data: paginatedResponse.data,
        pagination: paginatedResponse.pagination ?? null,
        timestamp: Date.now(),
      });
    }
  }, [paginatedResponse, cacheKey]);

  // Track previous pagination to prevent unnecessary updates
  const prevPaginationRef = useRef<PaginationInfo | null>(null);

  // Notify parent of pagination info when data changes
  useEffect(() => {
    const currentPagination = providedPagination ?? displayPagination;

    // Only notify if pagination actually changed
    if (
      onPaginationChange &&
      JSON.stringify(prevPaginationRef.current) !==
        JSON.stringify(currentPagination)
    ) {
      prevPaginationRef.current = currentPagination;
      onPaginationChange(currentPagination);
    }
  }, [displayPagination, providedPagination, onPaginationChange]);

  // Use provided data if available, otherwise use display data (from cache or fresh fetch)
  const isLoadingState = providedData
    ? false
    : isLoading && displayData.length === 0;
  const errorState = providedData ? null : error;
  const globalParts = providedData ?? displayData;

  // Hooks must be called unconditionally, before any early returns
  const getCategoryName = useCallback(
    (categoryId: string) => {
      const cat = categories.find((c) => c.id === categoryId);
      return cat?.display_name ?? cat?.name ?? '—';
    },
    [categories]
  );

  const getBrandName = useCallback(
    (part: GlobalPartReadWithVotes) => {
      if (part.brand) return part.brand;
      if (part.brand_id && brands.length > 0) {
        const b = brands.find((br) => br.id === part.brand_id);
        return b?.name ?? '—';
      }
      return '—';
    },
    [brands]
  );

  const formatCarName = useCallback(
    (car: CarRead) =>
      `${car.make ?? ''} ${car.model ?? ''} ${car.generation_name ?? ''}`.trim() ||
      'Vehicle',
    []
  );

  const getFitCell = useCallback(
    (part: GlobalPartReadWithVotes) => {
      if (part.is_universal) return { label: 'Universal', title: undefined };
      const ids = part.car_ids ?? [];
      const n = ids.length;
      if (n === 0) return { label: '—', title: undefined };
      if (n === 1) {
        const firstId = ids[0];
        const car = firstId != null ? effectiveCarsById[firstId] : undefined;
        return {
          label: car ? formatCarName(car) : '1 vehicle',
          title: undefined,
        };
      }
      const names = ids
        .map((id) => effectiveCarsById[id])
        .filter((c): c is CarRead => c != null)
        .map(formatCarName);
      return {
        label: `${n} vehicles`,
        title: names.length > 0 ? names.join('\n') : undefined,
      };
    },
    [effectiveCarsById, formatCarName]
  );

  const getNetVotes = (part: GlobalPartReadWithVotes) =>
    (part.upvotes ?? 0) - (part.downvotes ?? 0);

  const sortedParts = useMemo(() => {
    const list = globalParts ?? [];
    if (layout !== 'table' || list.length === 0) return list;
    const mult = sortDirection === 'asc' ? 1 : -1;
    const compare = (
      a: GlobalPartReadWithVotes,
      b: GlobalPartReadWithVotes
    ) => {
      switch (sortColumn) {
        case 'part':
          return mult * (a.name ?? '').localeCompare(b.name ?? '');
        case 'brand':
          return (
            mult * (getBrandName(a) ?? '').localeCompare(getBrandName(b) ?? '')
          );
        case 'part_number':
          return (
            mult * (a.part_number ?? '').localeCompare(b.part_number ?? '')
          );
        case 'category':
          return (
            mult *
            (getCategoryName(a.category_id) ?? '').localeCompare(
              getCategoryName(b.category_id) ?? ''
            )
          );
        case 'fit':
          return (
            mult *
            (getFitCell(a).label ?? '').localeCompare(getFitCell(b).label ?? '')
          );
        case 'rating':
          return mult * (getNetVotes(a) - getNetVotes(b));
        case 'price':
          const pa = a.best_price_cents ?? 0;
          const pb = b.best_price_cents ?? 0;
          return mult * (pa - pb);
        default:
          return 0;
      }
    };
    return [...list].sort(compare);
  }, [
    globalParts,
    layout,
    sortColumn,
    sortDirection,
    getCategoryName,
    getBrandName,
    getFitCell,
  ]);

  // Server-side sort: use API order unless sort is by "fit" (no server support), then client-sort current page
  const displayParts =
    isControlledSort &&
    controlledSortParam !== 'fit_asc' &&
    controlledSortParam !== 'fit_desc'
      ? (globalParts ?? [])
      : sortedParts;

  const sortableThProps = {
    sortColumn,
    sortDirection,
    onSort: handleSort,
  };

  if (isLoadingState) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (errorState) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${errorState}`} />
      </Card>
    );
  }

  if (layout === 'table') {
    return (
      <Card className="p-0 !overflow-visible">
        {title && (
          <div className="p-4 border-b border-gray-700">
            <SectionHeader title={title} />
          </div>
        )}

        {!globalParts || globalParts.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p>{emptyMessage}</p>
          </div>
        ) : (
          <div ref={tableWrapperRef} className="min-w-0">
            <div className="overflow-x-auto min-w-0 rounded-inherit">
              <table className="global-parts-table-scroll-layer w-full text-sm table-fixed">
                <colgroup>
                  {visibleColumns.map((key) => (
                    <col
                      key={key}
                      style={{
                        width: `${(COLUMN_MIN_WIDTH[key] / totalMinWidth) * 100}%`,
                      }}
                    />
                  ))}
                </colgroup>
                <thead>
                  <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
                    {visibleColumns.includes('part') && (
                      <SortableTh {...sortableThProps} column="part">
                        Part name
                      </SortableTh>
                    )}
                    {visibleColumns.includes('brand') && (
                      <SortableTh {...sortableThProps} column="brand">
                        Brand
                      </SortableTh>
                    )}
                    {visibleColumns.includes('part_number') && (
                      <SortableTh {...sortableThProps} column="part_number">
                        Part #
                      </SortableTh>
                    )}
                    {visibleColumns.includes('category') && (
                      <SortableTh {...sortableThProps} column="category">
                        Category
                      </SortableTh>
                    )}
                    {visibleColumns.includes('fit') && (
                      <SortableTh {...sortableThProps} column="fit">
                        Fit
                      </SortableTh>
                    )}
                    {visibleColumns.includes('rating') && (
                      <SortableTh {...sortableThProps} column="rating">
                        Rating
                      </SortableTh>
                    )}
                    {visibleColumns.includes('price') && (
                      <SortableTh
                        {...sortableThProps}
                        column="price"
                        align="right"
                      >
                        Price
                      </SortableTh>
                    )}
                    {visibleColumns.includes('actions') && (
                      <th
                        className="px-4 py-3 font-medium whitespace-nowrap min-w-0"
                        aria-label="Actions"
                      />
                    )}
                  </tr>
                </thead>
                <tbody>
                  {displayParts.map((globalPart: GlobalPartReadWithVotes) => (
                    <tr
                      key={globalPart.id}
                      className="border-b border-gray-700/70 hover:bg-gray-800/50 group"
                    >
                      {visibleColumns.includes('part') && (
                        <td
                          className="px-4 py-2 min-w-0 overflow-hidden"
                          title={globalPart.name}
                        >
                          <Link
                            to={`/global-parts/${globalPart.id}`}
                            className="flex items-center gap-2 hover:no-underline"
                          >
                            <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                              <ImageWithPlaceholder
                                srcUrl={buildExternalImageUrl(
                                  globalPart.image_urls?.[0],
                                  'thumbnail'
                                )}
                                altText={globalPart.name}
                                imageClassName="w-full h-full object-cover"
                                containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                                fallbackText=""
                                loading="lazy"
                              />
                            </div>
                            <span className="font-medium text-gray-200 group-hover:text-indigo-300 truncate block min-w-0">
                              {globalPart.name}
                            </span>
                          </Link>
                        </td>
                      )}
                      {visibleColumns.includes('brand') && (
                        <td
                          className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                          title={getBrandName(globalPart)}
                        >
                          <span className="block truncate">
                            {getBrandName(globalPart)}
                          </span>
                        </td>
                      )}
                      {visibleColumns.includes('part_number') && (
                        <td
                          className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                          title={globalPart.part_number ?? '—'}
                        >
                          <span className="block truncate">
                            {globalPart.part_number ?? '—'}
                          </span>
                        </td>
                      )}
                      {visibleColumns.includes('category') && (
                        <td
                          className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                          title={getCategoryName(globalPart.category_id)}
                        >
                          <span className="block truncate">
                            {getCategoryName(globalPart.category_id)}
                          </span>
                        </td>
                      )}
                      {visibleColumns.includes('fit') && (
                        <td className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden">
                          {(() => {
                            const { label, title } = getFitCell(globalPart);
                            const tooltip = title ?? label;
                            return (
                              <span
                                title={tooltip}
                                className="block truncate cursor-help underline decoration-dotted decoration-gray-500 underline-offset-1"
                              >
                                {label}
                              </span>
                            );
                          })()}
                        </td>
                      )}
                      {visibleColumns.includes('rating') && (
                        <td className="px-4 py-2 whitespace-nowrap">
                          {onVoteUpdate ? (
                            <VoteButtons
                              entityId={globalPart.id}
                              upvotes={globalPart.upvotes}
                              downvotes={globalPart.downvotes}
                              userVote={globalPart.user_vote ?? null}
                              onVoteUpdate={onVoteUpdate}
                              voteApi={{
                                voteOnEntity: (id, data) =>
                                  globalPartVotesApi.voteOnGlobalPart(id, data),
                                removeVote: (id) =>
                                  globalPartVotesApi.removeVote(id),
                              }}
                            />
                          ) : (
                            <span className="text-gray-400">
                              ({getNetVotes(globalPart)})
                            </span>
                          )}
                        </td>
                      )}
                      {visibleColumns.includes('price') && (
                        <td className="px-4 py-2 text-right whitespace-nowrap">
                          {globalPart.best_price_cents != null ? (
                            <span className="font-semibold text-green-400">
                              ${(globalPart.best_price_cents / 100).toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                        </td>
                      )}
                      {visibleColumns.includes('actions') && (
                        <td className="px-4 py-2 whitespace-nowrap">
                          <div className="flex items-center gap-1">
                            {showAddToBuildListButton && onAddToBuildList && (
                              <ActionButton
                                onClick={() => onAddToBuildList(globalPart)}
                                className="text-xs px-2 py-1 whitespace-nowrap shrink-0"
                              >
                                Add to Build List
                              </ActionButton>
                            )}
                            {onEdit && (!canEdit || canEdit(globalPart)) && (
                              <SecondaryButton
                                onClick={() => onEdit(globalPart)}
                                className="text-xs px-2 py-1"
                              >
                                Edit
                              </SecondaryButton>
                            )}
                            {onDelete &&
                              (!canDelete || canDelete(globalPart)) && (
                                <ActionButton
                                  onClick={() => onDelete(globalPart)}
                                  className="text-xs px-2 py-1 bg-red-600 hover:bg-red-700"
                                >
                                  Delete
                                </ActionButton>
                              )}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
    );
  }

  // Card layout (default)
  return (
    <Card>
      {title && (
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
        </div>
      )}

      {!globalParts || globalParts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {globalParts.map((globalPart) => (
            <div
              key={globalPart.id}
              className="bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500 transition-colors"
            >
              <div className="flex flex-row items-center gap-4 p-3">
                {/* Image */}
                <Link
                  to={`/global-parts/${globalPart.id}`}
                  className="flex-shrink-0"
                >
                  <div className="w-20 h-20">
                    <ImageWithPlaceholder
                      srcUrl={buildExternalImageUrl(
                        globalPart.image_urls?.[0],
                        'thumbnail'
                      )}
                      altText={globalPart.name}
                      imageClassName="w-full h-full object-cover rounded"
                      containerClassName="w-full h-full flex justify-center items-center"
                      fallbackText="No image"
                    />
                  </div>
                </Link>

                {/* Main Content */}
                <div className="flex-grow min-w-0">
                  <Link
                    to={`/global-parts/${globalPart.id}`}
                    className="block hover:no-underline"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-grow min-w-0">
                        <h3 className="text-base font-semibold text-gray-200 mb-1 truncate">
                          {globalPart.name}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                          {globalPart.brand && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">Brand:</span>{' '}
                              {globalPart.brand}
                            </span>
                          )}
                          {globalPart.part_number && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">P/N:</span>{' '}
                              {globalPart.part_number}
                            </span>
                          )}
                        </div>
                        {globalPart.description && (
                          <p className="text-sm text-gray-400 mt-1 line-clamp-1">
                            {globalPart.description}
                          </p>
                        )}
                      </div>
                      {globalPart.best_price_cents != null && (
                        <div className="flex-shrink-0 text-right">
                          <p className="text-base font-semibold text-green-400">
                            ${(globalPart.best_price_cents / 100).toFixed(2)}
                          </p>
                        </div>
                      )}
                    </div>
                  </Link>

                  {/* Actions Row */}
                  <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-gray-700">
                    <div className="flex items-center gap-2">
                      {showVoteButtons && onVoteUpdate && (
                        <VoteButtons
                          entityId={globalPart.id}
                          upvotes={globalPart.upvotes}
                          downvotes={globalPart.downvotes}
                          userVote={globalPart.user_vote ?? null}
                          onVoteUpdate={onVoteUpdate}
                          voteApi={{
                            voteOnEntity: (id, data) =>
                              globalPartVotesApi.voteOnGlobalPart(id, data),
                            removeVote: (id) =>
                              globalPartVotesApi.removeVote(id),
                          }}
                        />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {showAddToBuildListButton && onAddToBuildList && (
                        <ActionButton
                          onClick={() => onAddToBuildList(globalPart)}
                          className="text-xs px-3 py-1 whitespace-nowrap shrink-0"
                        >
                          📋 Add to Build List
                        </ActionButton>
                      )}
                      {onEdit && (!canEdit || canEdit(globalPart)) && (
                        <SecondaryButton
                          onClick={() => onEdit(globalPart)}
                          className="text-xs px-3 py-1"
                        >
                          Edit
                        </SecondaryButton>
                      )}
                      {onDelete && (!canDelete || canDelete(globalPart)) && (
                        <ActionButton
                          onClick={() => onDelete(globalPart)}
                          className="text-xs px-3 py-1 bg-red-600 hover:bg-red-700"
                        >
                          Delete
                        </ActionButton>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default GlobalPartList;
