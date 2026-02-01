import React, { useMemo } from 'react';
import type {
  BuildListPartReadWithGlobalPart,
  CategoryResponse,
} from '../../types/Api';
import Card from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';
import BuildListPartListItem from './BuildListPartListItem';

interface BuildListPartListProps {
  buildListParts: BuildListPartReadWithGlobalPart[];
  categories: CategoryResponse[];
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

const BuildListPartList: React.FC<BuildListPartListProps> = ({
  buildListParts,
  categories,
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

      {/* Parts grouped by category */}
      {groupedParts.map((group) => {
        const categoryName =
          group.category?.display_name ||
          group.category?.name ||
          'Uncategorized';
        const categoryIcon = group.category?.icon || '📦';
        // Use category ID as key, or fallback to first part's category_id for uncategorized items
        const groupKey =
          group.category?.id ??
          group.parts[0]?.global_part.category_id ??
          'uncategorized';

        return (
          <div key={groupKey} className="space-y-1">
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

            {/* Parts in this category */}
            <div className="space-y-0.5">
              {group.parts.map((buildListPart) => (
                <BuildListPartListItem
                  key={buildListPart.id}
                  buildListPart={buildListPart}
                  category={group.category}
                  {...(onEdit && { onEdit })}
                  {...(onDelete && { onDelete })}
                  {...(onTogglePurchased && { onTogglePurchased })}
                  canEdit={
                    canEdit && (!canEditPart || canEditPart(buildListPart))
                  }
                  canDelete={
                    canDelete &&
                    (!canDeletePart || canDeletePart(buildListPart))
                  }
                  canMarkPurchased={canMarkPurchased}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default BuildListPartList;
