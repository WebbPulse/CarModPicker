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
  canEdit?: boolean;
  canDelete?: boolean;
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
  canEdit = false,
  canDelete = false,
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

  // Calculate total price
  const totalPrice = useMemo(() => {
    return buildListParts.reduce((sum, part) => {
      const price = part.global_part.price;
      const quantity = part.quantity || 1;
      if (price !== null && price !== undefined) {
        return sum + price * quantity;
      }
      return sum;
    }, 0);
  }, [buildListParts]);

  const formatPrice = (price: number) => {
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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

  return (
    <div className="space-y-3">
      {/* Total Price Display */}
      <Card className="bg-gray-800 border-2 border-blue-600">
        <div className="flex justify-between items-center p-3">
          <div>
            <h3 className="text-base font-semibold text-gray-300">
              Total Build Cost
            </h3>
            <p className="text-xs text-gray-400">
              {buildListParts.length} part
              {buildListParts.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-blue-400">
              {formatPrice(totalPrice)}
            </p>
          </div>
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
                  canEdit={
                    canEdit && (!canEditPart || canEditPart(buildListPart))
                  }
                  canDelete={
                    canDelete &&
                    (!canDeletePart || canDeletePart(buildListPart))
                  }
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
