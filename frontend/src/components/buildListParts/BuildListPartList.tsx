import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useContainerWidth } from '../../hooks/useContainerWidth';
import { useResponsiveColumns } from '../../hooks/useResponsiveColumns';
import ResponsiveTableWrapper from '../tables/ResponsiveTableWrapper';
import type {
  PartManufacturerResponse,
  BuildListPartReadWithPart,
  BuildListPhaseRead,
  CarGenerationRead,
  CategoryResponse,
} from '../../types/Api';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import Spinner from '../ui/spinner';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import { carFullDisplayName } from '../../utils/carUtils';

type TableColumnKey =
  | 'checkbox'
  | 'part'
  | 'part_manufacturer'
  | 'part_number'
  | 'fit'
  | 'qty'
  | 'price'
  | 'actions';

// Lower = higher priority (kept longer). `part` and `price` are pinned and never drop.
const COLUMN_PRIORITY: Record<TableColumnKey, number> = {
  part: 0,
  price: 1,
  qty: 2,
  actions: 3,
  checkbox: 4,
  fit: 5,
  part_manufacturer: 6,
  part_number: 7,
};

const COLUMN_MIN_WIDTH: Record<TableColumnKey, number> = {
  part: 280,
  price: 100,
  qty: 70,
  actions: 130,
  checkbox: 60,
  fit: 160,
  part_manufacturer: 140,
  part_number: 140,
};

const DEFAULT_PART_MANUFACTURERS: PartManufacturerResponse[] = [];
const DEFAULT_CARS_BY_ID: Record<string, CarGenerationRead> = {};

interface GroupedPart {
  category: CategoryResponse | null;
  parts: BuildListPartReadWithPart[];
}

interface BuildListPartTableProps {
  group: GroupedPart;
  categoryName: string;
  categoryIcon: string;
  part_manufacturers: PartManufacturerResponse[];
  carsById: Record<string, CarGenerationRead>;
  containerWidth: number;
  onEdit?: (buildListPart: BuildListPartReadWithPart) => void;
  onDelete?: (buildListPartId: string) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithPart) => boolean;
}

function formatCarName(car: CarGenerationRead): string {
  return carFullDisplayName(car).trim() || 'Vehicle';
}

function getFitCell(
  part: BuildListPartReadWithPart,
  carsById: Record<string, CarGenerationRead>
): { label: string; title?: string } {
  const gp = part.part;
  if (gp.is_universal) return { label: 'Universal' };
  const ids = gp.car_ids ?? [];
  const n = ids.length;
  if (n === 0) return { label: '—' };
  if (n === 1) {
    const firstId = ids[0];
    const car = firstId != null ? carsById[firstId] : undefined;
    return { label: car ? formatCarName(car) : '1 vehicle' };
  }
  const names = ids
    .map((id) => carsById[id])
    .filter((c): c is CarGenerationRead => c != null)
    .map(formatCarName);
  const title = names.length > 0 ? names.join('\n') : undefined;
  return title != null
    ? { label: `${n} vehicles`, title }
    : { label: `${n} vehicles` };
}

function getPartManufacturerName(
  part: BuildListPartReadWithPart,
  part_manufacturers: PartManufacturerResponse[]
): string {
  const gp = part.part;
  if (gp.part_manufacturer) return gp.part_manufacturer;
  if (gp.part_manufacturer_id != null && part_manufacturers.length > 0) {
    const b = part_manufacturers.find(
      (br) => br.id === gp.part_manufacturer_id
    );
    return b?.name ?? '—';
  }
  return '—';
}

const BuildListPartTable: React.FC<BuildListPartTableProps> = ({
  group,
  categoryName,
  categoryIcon,
  part_manufacturers,
  carsById,
  containerWidth,
  onEdit,
  onDelete,
  onTogglePurchased,
  canEdit = false,
  canDelete = false,
  canMarkPurchased = false,
  canEditPart,
  canDeletePart,
}) => {
  const showCheckbox = canMarkPurchased && onTogglePurchased;
  const showActions = Boolean(onEdit || onDelete);

  const tableColumnKeys = useMemo((): TableColumnKey[] => {
    const keys: TableColumnKey[] = [];
    if (showCheckbox) keys.push('checkbox');
    keys.push(
      'part',
      'part_manufacturer',
      'part_number',
      'fit',
      'qty',
      'price'
    );
    if (showActions) keys.push('actions');
    return keys;
  }, [showCheckbox, showActions]);

  const { visibleColumns, totalMinWidth } = useResponsiveColumns(
    tableColumnKeys,
    COLUMN_PRIORITY,
    COLUMN_MIN_WIDTH,
    containerWidth
  );

  return (
    <div className="space-y-2">
      {/* Category Header */}
      <div className="flex items-center gap-2 px-1 py-0.5">
        <span className="text-base">{categoryIcon}</span>
        <h2 className="text-base font-semibold text-gray-200">
          {categoryName}
        </h2>
        <span className="text-xs text-gray-400">
          ({group.parts.length} part{group.parts.length !== 1 ? 's' : ''})
        </span>
      </div>

      {/* Table - matching parts/search layout; columns use % so table fills width */}
      <Card className="p-0 !overflow-visible">
        <ResponsiveTableWrapper
          visibleColumns={visibleColumns}
          columnMinWidths={COLUMN_MIN_WIDTH}
          totalMinWidth={totalMinWidth}
        >
          <thead>
            <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
              {visibleColumns.includes('checkbox') && (
                <th
                  className="px-3 py-3 font-medium whitespace-nowrap"
                  title="Mark as purchased"
                >
                  Purchased
                </th>
              )}
              {visibleColumns.includes('part') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Part name
                </th>
              )}
              {visibleColumns.includes('part_manufacturer') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Part Manufacturer
                </th>
              )}
              {visibleColumns.includes('part_number') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Part #
                </th>
              )}
              {visibleColumns.includes('fit') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Fit
                </th>
              )}
              {visibleColumns.includes('qty') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Qty
                </th>
              )}
              {visibleColumns.includes('price') && (
                <th className="px-4 py-3 font-medium whitespace-nowrap text-right">
                  Price
                </th>
              )}
              {visibleColumns.includes('actions') && (
                <th
                  className="relative px-4 py-3 font-medium whitespace-nowrap min-w-0"
                  aria-label="Actions"
                />
              )}
            </tr>
          </thead>
          <tbody>
            {group.parts.map((buildListPart) => {
              const { part, notes, quantity, purchased } = buildListPart;
              const gp = part;
              const qty = quantity || 1;
              const partPriceInCents = gp.best_price_cents;
              const totalPriceInCents =
                partPriceInCents != null ? partPriceInCents * qty : null;
              const showEdit =
                canEdit &&
                onEdit &&
                (!canEditPart || canEditPart(buildListPart));
              const showDelete =
                canDelete &&
                onDelete &&
                (!canDeletePart || canDeletePart(buildListPart));

              return (
                <tr
                  key={buildListPart.id}
                  className={`border-b border-gray-700/70 hover:bg-gray-800/50 transition-colors group ${
                    purchased ? 'opacity-60' : ''
                  }`}
                >
                  {visibleColumns.includes('checkbox') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <label
                        className="relative flex items-center cursor-pointer"
                        title={
                          purchased
                            ? 'Mark as not purchased'
                            : 'Mark as purchased'
                        }
                      >
                        <input
                          type="checkbox"
                          checked={purchased}
                          onChange={() => onTogglePurchased?.(buildListPart)}
                          className="sr-only peer"
                          aria-label={
                            purchased
                              ? 'Mark as not purchased'
                              : 'Mark as purchased'
                          }
                        />
                        <div className="w-6 h-6 min-w-[1.5rem] min-h-[1.5rem] aspect-square flex-shrink-0 bg-gray-700 border-2 border-gray-500 rounded-sm peer-checked:bg-blue-600 peer-checked:border-blue-500 peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-800 transition-all duration-200 flex items-center justify-center hover:border-gray-400 peer-checked:hover:bg-blue-500">
                          {purchased && (
                            <svg
                              className="w-4 h-4 text-white"
                              fill="none"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="3"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </label>
                    </td>
                  )}
                  <td
                    className="px-4 py-2 min-w-0 overflow-hidden"
                    title={
                      notes
                        ? `${gp.name}${notes ? ` — ${notes}` : ''}`
                        : gp.name
                    }
                  >
                    <Link
                      to={`/parts/${gp.id}`}
                      className="flex items-center gap-2 hover:no-underline"
                    >
                      <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                        <ImageWithPlaceholder
                          srcUrl={buildExternalImageUrl(
                            gp.image_urls?.[0],
                            'thumbnail'
                          )}
                          altText={gp.name}
                          imageClassName="w-full h-full object-cover"
                          containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                          fallbackText=""
                        />
                      </div>
                      <span
                        className={`font-medium truncate block min-w-0 group-hover:text-info ${
                          purchased
                            ? 'text-gray-400 line-through'
                            : 'text-gray-200'
                        }`}
                      >
                        {gp.name}
                      </span>
                    </Link>
                  </td>
                  {visibleColumns.includes('part_manufacturer') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getPartManufacturerName(
                        buildListPart,
                        part_manufacturers
                      )}
                    >
                      <span className="block truncate">
                        {getPartManufacturerName(
                          buildListPart,
                          part_manufacturers
                        )}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('part_number') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                      title={gp.part_number ?? '—'}
                    >
                      <span className="block truncate">
                        {gp.part_number ?? '—'}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('fit') && (
                    <td className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden">
                      {(() => {
                        const { label, title } = getFitCell(
                          buildListPart,
                          carsById
                        );
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
                  {visibleColumns.includes('qty') && (
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                      {qty}
                    </td>
                  )}
                  {visibleColumns.includes('price') && (
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      {totalPriceInCents != null ? (
                        <span
                          className={
                            purchased
                              ? 'font-semibold text-gray-500 line-through'
                              : 'font-semibold text-green-400'
                          }
                        >
                          $
                          {(totalPriceInCents / 100).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                          {qty > 1 && (
                            <span className="text-xs text-gray-400 block">
                              ${(partPriceInCents! / 100).toFixed(2)} × {qty}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                  )}
                  {visibleColumns.includes('actions') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        {showEdit && (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => onEdit(buildListPart)}
                            className="text-xs"
                          >
                            Edit
                          </Button>
                        )}
                        {showDelete && (
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => onDelete(buildListPart.id)}
                            className="text-xs"
                          >
                            Remove
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </ResponsiveTableWrapper>
      </Card>
    </div>
  );
};

interface BuildListPartListProps {
  buildListParts: BuildListPartReadWithPart[];
  categories: CategoryResponse[];
  viewMode?: 'category' | 'phase';
  phases?: BuildListPhaseRead[];
  part_manufacturers?: PartManufacturerResponse[];
  carsById?: Record<string, CarGenerationRead>;
  loading?: boolean;
  onEdit?: (buildListPart: BuildListPartReadWithPart) => void;
  onDelete?: (buildListPartId: string) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  emptyMessage?: string;
}

const PHASE_ICON = '📋';
const UNASSIGNED_LABEL = 'Unassigned';
const DEFAULT_PHASES: BuildListPhaseRead[] = [];

const BuildListPartList: React.FC<BuildListPartListProps> = ({
  buildListParts,
  categories,
  viewMode = 'category',
  phases = DEFAULT_PHASES,
  part_manufacturers = DEFAULT_PART_MANUFACTURERS,
  carsById = DEFAULT_CARS_BY_ID,
  loading = false,
  onEdit,
  onDelete,
  onTogglePurchased,
  canEdit = false,
  canDelete = false,
  canMarkPurchased = false,
  canEditPart,
  canDeletePart,
  emptyMessage = 'No parts added to this build list yet.',
}) => {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();

  // Create a map of category_id to category for quick lookup
  const categoryMap = useMemo(() => {
    const map = new Map<string, CategoryResponse>();
    categories.forEach((cat) => map.set(cat.id, cat));
    return map;
  }, [categories]);

  // Group and sort parts by category
  const groupedParts = useMemo(() => {
    const groups = new Map<
      string,
      {
        category: CategoryResponse | null;
        parts: BuildListPartReadWithPart[];
      }
    >();

    // Group parts by category_id
    buildListParts.forEach((part) => {
      const categoryId = part.part.category_id;
      if (!groups.has(categoryId)) {
        groups.set(categoryId, {
          category: categoryMap.get(categoryId) || null,
          parts: [],
        });
      }
      groups.get(categoryId)!.parts.push(part);
    });

    // Sort parts within each category alphabetically by part name
    groups.forEach((group) => {
      group.parts.sort((a, b) => a.part.name.localeCompare(b.part.name));
    });

    // Convert to array and sort by category display_name
    return Array.from(groups.values()).sort((a, b) => {
      const nameA =
        a.category?.display_name || a.category?.name || 'Uncategorized';
      const nameB =
        b.category?.display_name || b.category?.name || 'Uncategorized';
      return nameA.localeCompare(nameB);
    });
  }, [buildListParts, categoryMap]);

  // Phase map: id -> sort_order and id -> name
  const phaseOrderMap = useMemo(() => {
    const map = new Map<string, number>();
    phases.forEach((p) => map.set(p.id, p.sort_order));
    return map;
  }, [phases]);
  const phaseNameMap = useMemo(() => {
    const map = new Map<string, string>();
    phases.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [phases]);

  // Group and sort parts by phase (build_list_phase_id; null = Unassigned)
  const groupedByPhase = useMemo(() => {
    const groups = new Map<
      string,
      {
        phaseName: string;
        phaseSortOrder: number;
        parts: BuildListPartReadWithPart[];
      }
    >();

    buildListParts.forEach((part) => {
      const phaseId = part.build_list_phase_id ?? 'unassigned';
      const phaseName =
        phaseId === 'unassigned'
          ? UNASSIGNED_LABEL
          : (phaseNameMap.get(phaseId) ?? part.phase_name ?? UNASSIGNED_LABEL);
      const phaseSortOrder =
        phaseId === 'unassigned'
          ? 999999
          : (phaseOrderMap.get(phaseId) ?? 999999);
      if (!groups.has(phaseId)) {
        groups.set(phaseId, { phaseName, phaseSortOrder, parts: [] });
      }
      const g = groups.get(phaseId)!;
      if (phaseId !== 'unassigned') g.phaseName = phaseName;
      g.parts.push(part);
    });

    groups.forEach((group) => {
      group.parts.sort((a, b) => a.part.name.localeCompare(b.part.name));
    });

    return Array.from(groups.values()).sort(
      (a, b) => a.phaseSortOrder - b.phaseSortOrder
    );
  }, [buildListParts, phaseOrderMap, phaseNameMap]);

  const displayGroups = useMemo(() => {
    if (viewMode === 'phase') {
      return groupedByPhase.map((g) => ({
        category: null as CategoryResponse | null,
        parts: g.parts,
        groupLabel: g.phaseName,
        groupIcon: PHASE_ICON,
      }));
    }
    return groupedParts.map((g) => ({
      category: g.category,
      parts: g.parts,
      groupLabel:
        g.category?.display_name || g.category?.name || 'Uncategorized',
      groupIcon: g.category?.icon || '📦',
    }));
  }, [viewMode, groupedParts, groupedByPhase]);

  // Calculate total price (from best_price_cents when available)
  const totalPrice = useMemo(() => {
    return buildListParts.reduce((sum, part) => {
      const price = part.part.best_price_cents;
      const quantity = part.quantity || 1;
      if (price != null) {
        return sum + price * quantity;
      }
      return sum;
    }, 0);
  }, [buildListParts]);

  // Calculate remaining price (unpurchased parts)
  const remainingPrice = useMemo(() => {
    return buildListParts.reduce((sum, part) => {
      if (part.purchased) return sum; // Skip purchased parts
      const price = part.part.best_price_cents;
      const quantity = part.quantity || 1;
      if (price != null) {
        return sum + price * quantity;
      }
      return sum;
    }, 0);
  }, [buildListParts]);

  // Calculate purchased price (purchased parts)
  const purchasedPrice = useMemo(() => {
    return buildListParts.reduce((sum, part) => {
      if (!part.purchased) return sum; // Skip unpurchased parts
      const price = part.part.best_price_cents;
      const quantity = part.quantity || 1;
      if (price != null) {
        return sum + price * quantity;
      }
      return sum;
    }, 0);
  }, [buildListParts]);

  // Calculate purchase progress percentage
  const purchaseProgress = useMemo(() => {
    if (totalPrice === 0) return 0;
    return Math.round((purchasedPrice / totalPrice) * 100);
  }, [totalPrice, purchasedPrice]);

  const formatPrice = (priceInCents: number) => {
    // Convert cents to dollars
    const priceInDollars = priceInCents / 100;
    return `$${priceInDollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <Spinner />
      </div>
    );
  }

  if (buildListParts.length === 0) {
    return (
      <Card>
        <div className="text-center py-8">
          <p className="text-gray-400 text-lg">{emptyMessage}</p>
        </div>
      </Card>
    );
  }

  const purchasedCount = buildListParts.filter((p) => p.purchased).length;
  const remainingCount = buildListParts.filter((p) => !p.purchased).length;

  return (
    <div ref={containerRef} className="space-y-3">
      {/* Cost Summary Card */}
      <Card className="bg-gray-800 border-2 border-blue-600">
        <div className="space-y-3 p-4">
          {/* Total Build Cost - Always shown */}
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold text-gray-200">
                Total Build Cost
              </h3>
              <p className="text-xs text-gray-400 mt-1">
                {buildListParts.length} part
                {buildListParts.length !== 1 ? 's' : ''} total
                {purchasedCount > 0 || remainingCount > 0 ? (
                  <>
                    {' '}
                    • {purchasedCount} purchased • {remainingCount} remaining
                  </>
                ) : null}
              </p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-blue-400">
                {formatPrice(totalPrice)}
              </p>
            </div>
          </div>

          {/* Purchase Progress Bar - Shown when there are purchased parts */}
          {totalPrice > 0 && (purchasedCount > 0 || remainingCount > 0) && (
            <div className="pt-2 border-t border-gray-700">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-gray-400">Purchase Progress</span>
                <span className="text-xs font-semibold text-gray-300">
                  {purchaseProgress}%
                </span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2.5">
                <div
                  className="bg-green-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${purchaseProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Remaining and Purchased Costs - Shown when there are purchased parts */}
          {(purchasedCount > 0 || remainingCount > 0) && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-700">
              {/* Remaining Cost */}
              <div className="bg-gray-900/50 rounded-lg p-3">
                <div className="flex justify-between items-start mb-1">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-300">
                      Remaining
                    </h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {remainingCount} part{remainingCount !== 1 ? 's' : ''} to
                      purchase
                    </p>
                  </div>
                </div>
                <p className="text-xl font-bold text-green-400 mt-2">
                  {formatPrice(remainingPrice)}
                </p>
              </div>

              {/* Purchased Cost */}
              <div className="bg-gray-900/50 rounded-lg p-3">
                <div className="flex justify-between items-start mb-1">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-300">
                      Purchased
                    </h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {purchasedCount} part{purchasedCount !== 1 ? 's' : ''}{' '}
                      acquired
                    </p>
                  </div>
                </div>
                <p className="text-xl font-bold text-success mt-2">
                  {formatPrice(purchasedPrice)}
                </p>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Parts grouped by category or phase - table layout matching parts/search */}
      {displayGroups.map((group, index) => {
        const groupKey =
          viewMode === 'phase'
            ? `phase-${group.groupLabel}-${index}`
            : String(
                group.category?.id ??
                  group.parts[0]?.part.category_id ??
                  'uncategorized'
              );
        return (
          <BuildListPartTable
            key={groupKey}
            group={group}
            categoryName={group.groupLabel}
            categoryIcon={group.groupIcon}
            part_manufacturers={part_manufacturers}
            carsById={carsById}
            containerWidth={containerWidth}
            {...(onEdit != null && { onEdit })}
            {...(onDelete != null && { onDelete })}
            {...(onTogglePurchased != null && { onTogglePurchased })}
            canEdit={canEdit}
            canDelete={canDelete}
            canMarkPurchased={canMarkPurchased}
            {...(canEditPart != null && { canEditPart })}
            {...(canDeletePart != null && { canDeletePart })}
          />
        );
      })}
    </div>
  );
};

export default BuildListPartList;
