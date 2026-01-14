import React from 'react';
import { Link } from 'react-router-dom';
import type {
  BuildListPartReadWithGlobalPart,
  CategoryResponse,
} from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import Card from '../common/Card';

interface BuildListPartListItemProps {
  buildListPart: BuildListPartReadWithGlobalPart;
  category?: CategoryResponse | null;
  onEdit?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  onDelete?: (buildListPartId: number) => void;
  canEdit?: boolean;
  canDelete?: boolean;
}

const BuildListPartListItem: React.FC<BuildListPartListItemProps> = ({
  buildListPart,
  category,
  onEdit,
  onDelete,
  canEdit = false,
  canDelete = false,
}) => {
  const { global_part, notes, quantity } = buildListPart;

  const formatPrice = (price: number | null | undefined) => {
    if (price === null || price === undefined) return null;
    return price;
  };

  const partPrice = formatPrice(global_part.price);
  const qty = quantity || 1;
  const totalPrice = partPrice !== null ? partPrice * qty : null;

  const formatPriceDisplay = (price: number) => {
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <Card className="py-1 px-2">
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3">
        {/* Left side: Part name, category, brand, notes */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-white">
              <Link
                to={`/global-parts/${global_part.id}`}
                className="hover:text-blue-400 transition-colors"
              >
                {global_part.name}
              </Link>
            </h3>
            {category && (
              <span className="text-xs text-gray-400 bg-gray-700 px-1.5 py-0.5 rounded">
                {category.display_name || category.name}
              </span>
            )}
            {global_part.brand && (
              <span className="text-xs text-gray-500">{global_part.brand}</span>
            )}
            {notes && (
              <span className="text-xs text-gray-500 italic line-clamp-1">
                📝 {notes}
              </span>
            )}
          </div>
        </div>

        {/* Actions column: Fixed width, always rendered for alignment */}
        <div className="flex items-center gap-1.5 flex-shrink-0 w-32 justify-end">
          {canEdit && onEdit && (
            <SecondaryButton
              onClick={() => onEdit(buildListPart)}
              className="text-xs px-1.5 py-0.5"
            >
              Edit
            </SecondaryButton>
          )}
          {canDelete && onDelete && (
            <ActionButton
              onClick={() => onDelete(buildListPart.id)}
              className="text-xs px-1.5 py-0.5 bg-red-600 hover:bg-red-700"
            >
              Remove
            </ActionButton>
          )}
        </div>

        {/* Price column: Fixed width, rightmost element */}
        <div className="text-right w-24 flex-shrink-0">
          {partPrice !== null ? (
            qty > 1 && totalPrice !== null ? (
              <div>
                {/* Total price is prominent when multiple quantities */}
                <div className="text-sm font-semibold text-gray-300">
                  {formatPriceDisplay(totalPrice)}
                </div>
                <div className="text-xs text-gray-400">
                  {formatPriceDisplay(partPrice)} × {qty}
                </div>
              </div>
            ) : (
              <div className="text-sm font-semibold text-gray-300">
                {formatPriceDisplay(partPrice)}
              </div>
            )
          ) : (
            <div className="text-sm text-gray-500">No price</div>
          )}
        </div>
      </div>
    </Card>
  );
};

export default BuildListPartListItem;
