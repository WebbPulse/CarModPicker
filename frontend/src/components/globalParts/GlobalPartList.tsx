import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { globalPartVotesApi, globalPartsApi } from '../../services/Api';
import type {
  BrandResponse,
  CarRead,
  CategoryResponse,
  GlobalPartReadWithVotes,
  PaginationInfo,
} from '../../types/Api';

import { CACHE_DURATION_MS } from '../../constants';
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

const COLUMN_WIDTH_STORAGE_KEY = 'globalPartsTableColumnWidths';

type TableColumnKey =
  | 'part'
  | 'brand'
  | 'part_number'
  | 'category'
  | 'fit'
  | 'rating'
  | 'price'
  | 'actions';

// Part ~25 chars + thumb; price/rating/actions get more space; part_number truncated more; fit less.
const DEFAULT_COLUMN_WIDTHS: Record<TableColumnKey, number> = {
  part: 200,
  brand: 50,
  part_number: 24,
  category: 60,
  fit: 80,
  rating: 120,
  price: 100,
  actions: 192,
};

const MIN_COLUMN_WIDTHS: Record<TableColumnKey, number> = {
  part: 100,
  brand: 40,
  part_number: 20,
  category: 50,
  fit: 56,
  rating: 80,
  price: 70,
  actions: 120,
};

function getCacheKey(params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  category_ids?: number[];
  car_id?: number;
  brand_id?: number;
  brand_ids?: number[];
  user_id?: number;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
}): string {
  return JSON.stringify(params || {});
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
    category_id?: number;
    category_ids?: number[];
    car_id?: number;
    brand_id?: number;
    brand_ids?: number[];
    user_id?: number;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
  };
  data?: GlobalPartReadWithVotes[]; // Optional: pass pre-fetched data instead of fetching
  pagination?: PaginationInfo | null; // Optional: pass pagination info when using pre-fetched data
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
  onAddToBuildList?: (globalPart: GlobalPartReadWithVotes) => void;
  showAddToBuildListButton?: boolean;
  onEdit?: (globalPart: GlobalPartReadWithVotes) => void;
  onDelete?: (globalPart: GlobalPartReadWithVotes) => void;
  canEdit?: (globalPart: GlobalPartReadWithVotes) => boolean;
  canDelete?: (globalPart: GlobalPartReadWithVotes) => boolean;
  onPaginationChange?: (pagination: PaginationInfo | null) => void;
  /** Called when sort column/direction changes (e.g. to reset pagination). */
  onSortChange?: () => void;
  /** Table layout: dense columns (Part | Brand | P/N | Category | Fit | Rating | Price). Requires categories for Category column, brands for Brand column lookup. */
  layout?: 'card' | 'table';
  categories?: CategoryResponse[];
  brands?: BrandResponse[];
  /** Map of car ID to CarRead for Fit column car names. */
  carsById?: Record<number, CarRead>;
}

const fetchGlobalPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  category_ids?: number[];
  car_id?: number;
  brand_id?: number;
  brand_ids?: number[];
  user_id?: number;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
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
  layout = 'card',
  categories = [],
  brands = [],
  carsById = {},
}: GlobalPartListProps) {
  type SortColumn =
    | 'part'
    | 'brand'
    | 'part_number'
    | 'category'
    | 'fit'
    | 'rating'
    | 'price';
  const [sortColumn, setSortColumn] = useState<SortColumn>('rating');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const [columnWidths, setColumnWidths] = useState<
    Partial<Record<TableColumnKey, number>>
  >(() => {
    try {
      const raw = localStorage.getItem(COLUMN_WIDTH_STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw) as Record<string, number>;
      const out: Partial<Record<TableColumnKey, number>> = {};
      const keys: TableColumnKey[] = [
        'part',
        'brand',
        'part_number',
        'category',
        'fit',
        'rating',
        'price',
        'actions',
      ];
      keys.forEach((k) => {
        if (typeof parsed[k] === 'number' && parsed[k] >= MIN_COLUMN_WIDTHS[k]) {
          out[k] = parsed[k];
        }
      });
      return out;
    } catch {
      return {};
    }
  });

  const tableColumnKeys = useMemo((): TableColumnKey[] => {
    const keys: TableColumnKey[] = ['part', 'brand', 'part_number'];
    if (categories.length > 0) keys.push('category');
    keys.push('fit');
    if (showVoteButtons) keys.push('rating');
    keys.push('price');
    if (showAddToBuildListButton || onEdit || onDelete) keys.push('actions');
    return keys;
  }, [categories.length, showVoteButtons, showAddToBuildListButton, onEdit, onDelete]);

  const getColumnWidth = useCallback(
    (key: TableColumnKey) => columnWidths[key] ?? DEFAULT_COLUMN_WIDTHS[key],
    [columnWidths]
  );

  const resizeRef = useRef<{
    leftKey: TableColumnKey;
    rightKey: TableColumnKey;
    startX: number;
    startLeft: number;
    startRight: number;
  } | null>(null);

  const handleResizeStart = useCallback(
    (leftKey: TableColumnKey, rightKey: TableColumnKey) =>
      (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        resizeRef.current = {
          leftKey,
          rightKey,
          startX: e.clientX,
          startLeft: getColumnWidth(leftKey),
          startRight: getColumnWidth(rightKey),
        };
        const onMove = (moveEvent: MouseEvent) => {
          const r = resizeRef.current;
          if (!r) return;
          const delta = moveEvent.clientX - r.startX;
          const minLeft = MIN_COLUMN_WIDTHS[r.leftKey];
          const minRight = MIN_COLUMN_WIDTHS[r.rightKey];
          let newLeft = r.startLeft + delta;
          let newRight = r.startRight - delta;
          if (newLeft < minLeft) {
            newLeft = minLeft;
            newRight = r.startLeft + r.startRight - minLeft;
          } else if (newRight < minRight) {
            newRight = minRight;
            newLeft = r.startLeft + r.startRight - minRight;
          }
          setColumnWidths((prev) => {
            const next = {
              ...prev,
              [r.leftKey]: newLeft,
              [r.rightKey]: newRight,
            };
            try {
              localStorage.setItem(
                COLUMN_WIDTH_STORAGE_KEY,
                JSON.stringify(next)
              );
            } catch {
              // ignore
            }
            return next;
          });
        };
        const onUp = () => {
          resizeRef.current = null;
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          document.body.style.cursor = '';
          document.body.style.userSelect = '';
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
      },
    [getColumnWidth]
  );

  const handleSort = useCallback(
    (column: SortColumn) => {
      if (sortColumn === column) {
        setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortColumn(column);
        setSortDirection(
          column === 'rating' || column === 'price' ? 'desc' : 'asc'
        );
      }
      onSortChange?.();
    },
    [sortColumn, onSortChange]
  );

  const effectiveParams = useMemo(
    () => ({
      ...params,
      ...(layout === 'table' &&
        sortColumn === 'price' && { sort: 'lowest_price' as const }),
    }),
    [params, layout, sortColumn]
  );

  const {
    data: paginatedResponse,
    isLoading,
    error,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  // Initialize with cached data if available (for instant display)
  const cacheKey = getCacheKey(effectiveParams);
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

  const memoizedFetchGlobalParts = useCallback(() => {
    void fetchGlobalParts(effectiveParams);
  }, [fetchGlobalParts, effectiveParams]);

  // Only fetch if data is not provided
  useEffect(() => {
    if (!providedData) {
      // Check cache first - if we have cached data, show it immediately and fetch in background
      const cached = getCachedData(cacheKey);
      if (cached) {
        setDisplayData(cached.data);
        setDisplayPagination(cached.pagination);
      }
      // Always fetch fresh data in background
      memoizedFetchGlobalParts();
    }
  }, [memoizedFetchGlobalParts, refreshKey, providedData, cacheKey]);

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
    (categoryId: number) => {
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

  const formatCarName = (car: CarRead) =>
    `${car.make} ${car.model} ${car.generation_name}`;

  const getFitCell = (part: GlobalPartReadWithVotes) => {
    if (part.is_universal) return { label: 'Universal', title: undefined };
    const ids = part.car_ids ?? [];
    const n = ids.length;
    if (n === 0) return { label: '—', title: undefined };
    if (n === 1) {
      const firstId = ids[0];
      const car = firstId != null ? carsById[firstId] : undefined;
      return {
        label: car ? formatCarName(car) : '1 vehicle',
        title: undefined,
      };
    }
    const names = ids
      .map((id) => carsById[id])
      .filter((c): c is CarRead => c != null)
      .map(formatCarName);
    return {
      label: `${n} vehicles`,
      title: names.length > 0 ? names.join('\n') : undefined,
    };
  };

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
    carsById,
  ]);

  const totalTableWidth = useMemo(
    () =>
      tableColumnKeys.reduce(
        (sum, key) => sum + getColumnWidth(key),
        0
      ),
    [tableColumnKeys, getColumnWidth]
  );

  const SortableTh = ({
    column,
    children,
    align = 'left',
    columnKey,
    nextColumnKey,
  }: {
    column: SortColumn;
    children: React.ReactNode;
    align?: 'left' | 'right';
    columnKey: TableColumnKey;
    nextColumnKey?: TableColumnKey | undefined;
  }) => {
    const isActive = sortColumn === column;
    return (
      <th
        className={`relative px-4 py-3 font-medium whitespace-nowrap cursor-pointer select-none hover:bg-gray-700/50 transition-colors ${
          align === 'right' ? 'text-right' : 'text-left'
        } ${isActive ? 'text-indigo-300' : 'text-gray-400'}`}
        onClick={() => handleSort(column)}
        role="columnheader"
        aria-sort={
          isActive
            ? sortDirection === 'asc'
              ? 'ascending'
              : 'descending'
            : undefined
        }
      >
        <span className="flex items-center gap-1">
          {children}
          {isActive && (
            <span className="text-indigo-400" aria-hidden>
              {sortDirection === 'asc' ? '↑' : '↓'}
            </span>
          )}
        </span>
        {nextColumnKey != null && (
          <div
            role="separator"
            aria-label="Resize column"
            className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize touch-none hover:bg-indigo-500/50 active:bg-indigo-500/70 z-10"
            onMouseDown={handleResizeStart(columnKey, nextColumnKey)}
          />
        )}
      </th>
    );
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
          <div className="overflow-x-auto min-w-0 rounded-inherit">
            <table className="w-full text-sm table-fixed">
              <colgroup>
                {tableColumnKeys.map((key) => (
                  <col
                    key={key}
                    style={{
                      width: `${(getColumnWidth(key) / totalTableWidth) * 100}%`,
                    }}
                  />
                ))}
              </colgroup>
              <thead>
                <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
                  <SortableTh
                    column="part"
                    columnKey="part"
                    nextColumnKey={tableColumnKeys[1]}
                  >
                    Part name
                  </SortableTh>
                  <SortableTh
                    column="brand"
                    columnKey="brand"
                    nextColumnKey={tableColumnKeys[2]}
                  >
                    Brand
                  </SortableTh>
                  <SortableTh
                    column="part_number"
                    columnKey="part_number"
                    nextColumnKey={
                      categories.length > 0
                        ? 'category'
                        : 'fit'
                    }
                  >
                    Part #
                  </SortableTh>
                  {categories.length > 0 && (
                    <SortableTh
                      column="category"
                      columnKey="category"
                      nextColumnKey="fit"
                    >
                      Category
                    </SortableTh>
                  )}
                  <SortableTh
                    column="fit"
                    columnKey="fit"
                    nextColumnKey={
                      showVoteButtons ? 'rating' : 'price'
                    }
                  >
                    Fit
                  </SortableTh>
                  {showVoteButtons && (
                    <SortableTh
                      column="rating"
                      columnKey="rating"
                      nextColumnKey="price"
                    >
                      Rating
                    </SortableTh>
                  )}
                  <SortableTh
                    column="price"
                    align="right"
                    columnKey="price"
                    nextColumnKey={
                      showAddToBuildListButton || onEdit || onDelete
                        ? 'actions'
                        : undefined
                    }
                  >
                    Price
                  </SortableTh>
                  {(showAddToBuildListButton || onEdit || onDelete) && (
                    <th
                      className="relative px-4 py-3 font-medium whitespace-nowrap min-w-0"
                      aria-label="Actions"
                    />
                  )}
                </tr>
              </thead>
              <tbody>
                {sortedParts.map((globalPart: GlobalPartReadWithVotes) => (
                  <tr
                    key={globalPart.id}
                    className="border-b border-gray-700/70 hover:bg-gray-800/50 transition-colors group"
                  >
                    {/* Part: thumb + name */}
                    <td className="px-4 py-2 min-w-0 overflow-hidden" title={globalPart.name}>
                      <Link
                        to={`/global-parts/${globalPart.id}`}
                        className="flex items-center gap-2 hover:no-underline"
                      >
                        <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                          <ImageWithPlaceholder
                            srcUrl={globalPart.image_url ?? null}
                            altText={globalPart.name}
                            imageClassName="w-full h-full object-cover"
                            containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                            fallbackText=""
                          />
                        </div>
                        <span className="font-medium text-gray-200 group-hover:text-indigo-300 truncate block min-w-0">
                          {globalPart.name}
                        </span>
                      </Link>
                    </td>
                    {/* Brand */}
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getBrandName(globalPart)}
                    >
                      <span className="block truncate">
                        {getBrandName(globalPart)}
                      </span>
                    </td>
                    {/* Part # */}
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                      title={globalPart.part_number ?? '—'}
                    >
                      <span className="block truncate">
                        {globalPart.part_number ?? '—'}
                      </span>
                    </td>
                    {/* Category */}
                    {categories.length > 0 && (
                      <td
                        className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                        title={getCategoryName(globalPart.category_id)}
                      >
                        <span className="block truncate">
                          {getCategoryName(globalPart.category_id)}
                        </span>
                      </td>
                    )}
                    {/* Fit */}
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
                    {/* Rating */}
                    {showVoteButtons && (
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
                    {/* Price */}
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      {globalPart.best_price_cents != null ? (
                        <span className="font-semibold text-green-400">
                          ${(globalPart.best_price_cents / 100).toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                    {/* Actions */}
                    {(showAddToBuildListButton || onEdit || onDelete) && (
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
                      srcUrl={globalPart.image_url ?? null}
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
