import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type {
  BrandResponse,
  BuildListPartReadWithGlobalPart,
  BuildListPhaseRead,
  CarRead,
  CategoryResponse,
} from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import LoadingSpinner from '../common/LoadingSpinner';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';

const DEFAULT_BRANDS: BrandResponse[] = [];
const DEFAULT_CARS_BY_ID: Record<number, CarRead> = {};

interface GroupedPart {
  category: CategoryResponse | null;
  parts: BuildListPartReadWithGlobalPart[];
}

interface BuildListPartTableProps {
  group: GroupedPart;
  categoryName: string;
  categoryIcon: string;
  brands: BrandResponse[];
  carsById: Record<number, CarRead>;
  onEdit?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  onDelete?: (buildListPartId: number) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
}

function formatCarName(car: CarRead): string {
  return (
    `${car.make ?? ''} ${car.model ?? ''} ${car.generation_name ?? ''}`.trim() ||
    'Vehicle'
  );
}

function getFitCell(
  part: BuildListPartReadWithGlobalPart,
  carsById: Record<number, CarRead>
): { label: string; title?: string } {
  const gp = part.global_part;
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
    .filter((c): c is CarRead => c != null)
    .map(formatCarName);
  const title = names.length > 0 ? names.join('\n') : undefined;
  return title != null
    ? { label: `${n} vehicles`, title }
    : { label: `${n} vehicles` };
}

function getBrandName(
  part: BuildListPartReadWithGlobalPart,
  brands: BrandResponse[]
): string {
  const gp = part.global_part;
  if (gp.brand) return gp.brand;
  if (gp.brand_id != null && brands.length > 0) {
    const b = brands.find((br) => br.id === gp.brand_id);
    return b?.name ?? '—';
  }
  return '—';
}

const BuildListPartTable: React.FC<BuildListPartTableProps> = ({
  group,
  categoryName,
  categoryIcon,
  brands,
  carsById,
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

  // Percentages that sum to 100% so the table fills horizontal space (checkbox, part, brand, part#, fit, qty, price, actions).
  const columnWidths = ((): { key: string; width: number }[] => {
    if (showCheckbox && showActions)
      return [
        { key: 'cb', width: 4 },
        { key: 'part', width: 28 },
        { key: 'brand', width: 12 },
        { key: 'partNum', width: 12 },
        { key: 'fit', width: 10 },
        { key: 'qty', width: 8 },
        { key: 'price', width: 12 },
        { key: 'actions', width: 14 },
      ];
    if (showCheckbox && !showActions)
      return [
        { key: 'cb', width: 4 },
        { key: 'part', width: 38 },
        { key: 'brand', width: 14 },
        { key: 'partNum', width: 14 },
        { key: 'fit', width: 12 },
        { key: 'qty', width: 10 },
        { key: 'price', width: 8 },
      ];
    if (!showCheckbox && showActions)
      return [
        { key: 'part', width: 30 },
        { key: 'brand', width: 12 },
        { key: 'partNum', width: 12 },
        { key: 'fit', width: 10 },
        { key: 'qty', width: 10 },
        { key: 'price', width: 12 },
        { key: 'actions', width: 14 },
      ];
    return [
      { key: 'part', width: 35 },
      { key: 'brand', width: 15 },
      { key: 'partNum', width: 15 },
      { key: 'fit', width: 12 },
      { key: 'qty', width: 10 },
      { key: 'price', width: 13 },
    ];
  })();

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

      {/* Table - matching global-parts/search layout; columns use % so table fills width */}
      <Card className="p-0 !overflow-visible">
        <div className="overflow-x-auto min-w-0 rounded-inherit">
          <table className="w-full text-sm table-fixed">
            <colgroup>
              {columnWidths.map((col) => (
                <col key={col.key} style={{ width: `${col.width}%` }} />
              ))}
            </colgroup>
            <thead>
              <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
                {showCheckbox && (
                  <th
                    className="px-3 py-3 font-medium whitespace-nowrap"
                    title="Mark as purchased"
                  >
                    Purchased
                  </th>
                )}
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Part name
                </th>
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Brand
                </th>
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Part #
                </th>
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Fit
                </th>
                <th className="px-4 py-3 font-medium whitespace-nowrap min-w-0">
                  Qty
                </th>
                <th className="px-4 py-3 font-medium whitespace-nowrap text-right">
                  Price
                </th>
                {(onEdit || onDelete) && (
                  <th
                    className="relative px-4 py-3 font-medium whitespace-nowrap min-w-0"
                    aria-label="Actions"
                  />
                )}
              </tr>
            </thead>
            <tbody>
              {group.parts.map((buildListPart) => {
                const { global_part, notes, quantity, purchased } =
                  buildListPart;
                const gp = global_part;
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
                    {showCheckbox && (
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
                        to={`/global-parts/${gp.id}`}
                        className="flex items-center gap-2 hover:no-underline"
                      >
                        <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                          <ImageWithPlaceholder
                            srcUrl={buildExternalImageUrl(
                              gp.image_url ?? gp.image_urls?.[0],
                              'thumbnail'
                            )}
                            altText={gp.name}
                            imageClassName="w-full h-full object-cover"
                            containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                            fallbackText=""
                          />
                        </div>
                        <span
                          className={`font-medium truncate block min-w-0 group-hover:text-indigo-300 ${
                            purchased
                              ? 'text-gray-400 line-through'
                              : 'text-gray-200'
                          }`}
                        >
                          {gp.name}
                        </span>
                      </Link>
                    </td>
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getBrandName(buildListPart, brands)}
                    >
                      <span className="block truncate">
                        {getBrandName(buildListPart, brands)}
                      </span>
                    </td>
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                      title={gp.part_number ?? '—'}
                    >
                      <span className="block truncate">
                        {gp.part_number ?? '—'}
                      </span>
                    </td>
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
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                      {qty}
                    </td>
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
                    {(onEdit || onDelete) && (
                      <td className="px-4 py-2 whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          {showEdit && (
                            <SecondaryButton
                              onClick={() => onEdit(buildListPart)}
                              className="text-xs px-2 py-1"
                            >
                              Edit
                            </SecondaryButton>
                          )}
                          {showDelete && (
                            <ActionButton
                              onClick={() => onDelete(buildListPart.id)}
                              className="text-xs px-2 py-1 bg-red-600 hover:bg-red-700"
                            >
                              Remove
                            </ActionButton>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

interface BuildListPartListProps {
  buildListParts: BuildListPartReadWithGlobalPart[];
  categories: CategoryResponse[];
  viewMode?: 'category' | 'phase';
  phases?: BuildListPhaseRead[];
  brands?: BrandResponse[];
  carsById?: Record<number, CarRead>;
  loading?: boolean;
  onEdit?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  onDelete?: (buildListPartId: number) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
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
  brands = DEFAULT_BRANDS,
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
  // Create a map of category_id to category for quick lookup
  const categoryMap = useMemo(() => {
    const map = new Map<number, CategoryResponse>();
    categories.forEach((cat) => map.set(cat.id, cat));
    return map;
  }, [categories]);

  // Group and sort parts by category
  const groupedParts = useMemo(() => {
    const groups = new Map<
      number,
      {
        category: CategoryResponse | null;
        parts: BuildListPartReadWithGlobalPart[];
      }
    >();

    // Group parts by category_id
    buildListParts.forEach((part) => {
      const categoryId = part.global_part.category_id;
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
      group.parts.sort((a, b) =>
        a.global_part.name.localeCompare(b.global_part.name)
      );
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
    const map = new Map<number, number>();
    phases.forEach((p) => map.set(p.id, p.sort_order));
    return map;
  }, [phases]);
  const phaseNameMap = useMemo(() => {
    const map = new Map<number, string>();
    phases.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [phases]);

  // Group and sort parts by phase (build_list_phase_id; null = Unassigned)
  const groupedByPhase = useMemo(() => {
    const groups = new Map<
      number | 'unassigned',
      {
        phaseName: string;
        phaseSortOrder: number;
        parts: BuildListPartReadWithGlobalPart[];
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
      group.parts.sort((a, b) =>
        a.global_part.name.localeCompare(b.global_part.name)
      );
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
      const price = part.global_part.best_price_cents;
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
      const price = part.global_part.best_price_cents;
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
      const price = part.global_part.best_price_cents;
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
        <LoadingSpinner />
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
    <div className="space-y-3">
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
                <p className="text-xl font-bold text-emerald-400 mt-2">
                  {formatPrice(purchasedPrice)}
                </p>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Parts grouped by category or phase - table layout matching global-parts/search */}
      {displayGroups.map((group, index) => {
        const groupKey =
          viewMode === 'phase'
            ? `phase-${group.groupLabel}-${index}`
            : String(
                group.category?.id ??
                  group.parts[0]?.global_part.category_id ??
                  'uncategorized'
              );
        return (
          <BuildListPartTable
            key={groupKey}
            group={group}
            categoryName={group.groupLabel}
            categoryIcon={group.groupIcon}
            brands={brands}
            carsById={carsById}
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
