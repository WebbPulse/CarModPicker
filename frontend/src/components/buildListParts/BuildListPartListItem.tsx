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
  onTogglePurchased?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
}

const BuildListPartListItem: React.FC<BuildListPartListItemProps> = ({
  buildListPart,
  category,
  onEdit,
  onDelete,
  onTogglePurchased,
  canEdit = false,
  canDelete = false,
  canMarkPurchased = false,
}) => {
  const { global_part, notes, quantity, purchased } = buildListPart;

  // Prices are stored in cents, so we keep them in cents for calculations
  const partPriceInCents = global_part.price;
  const qty = quantity || 1;
  const totalPriceInCents = partPriceInCents !== null && partPriceInCents !== undefined 
    ? partPriceInCents * qty 
    : null;

  const formatPriceDisplay = (priceInCents: number) => {
    // Convert cents to dollars for display
    const priceInDollars = priceInCents / 100;
    return `$${priceInDollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const showCheckbox = canMarkPurchased && onTogglePurchased;
  const gridCols = showCheckbox 
    ? 'grid-cols-[auto_1fr_auto_auto]' 
    : 'grid-cols-[1fr_auto_auto]';

  return (
    <Card className={`py-1 px-2 ${purchased ? 'opacity-60' : ''}`}>
      <div className={`grid ${gridCols} items-center gap-3`}>
        {/* Purchased checkbox */}
        {showCheckbox && (
          <div className="flex items-center justify-center min-w-[28px]">
            <label className="relative flex items-center cursor-pointer" title={purchased ? 'Mark as not purchased' : 'Mark as purchased'}>
              <input
                type="checkbox"
                checked={purchased}
                onChange={() => onTogglePurchased?.(buildListPart)}
                className="sr-only peer"
                aria-label={purchased ? 'Mark as not purchased' : 'Mark as purchased'}
              />
              <div className="w-6 h-6 bg-gray-700 border-2 border-gray-500 rounded peer-checked:bg-blue-600 peer-checked:border-blue-500 peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-800 transition-all duration-200 flex items-center justify-center hover:border-gray-400 peer-checked:hover:bg-blue-500">
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
          </div>
        )}
        {/* Left side: Part name, category, brand, notes */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`text-sm font-semibold ${purchased ? 'text-gray-400 line-through' : 'text-white'}`}>
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
          {partPriceInCents !== null && partPriceInCents !== undefined ? (
            qty > 1 && totalPriceInCents !== null ? (
              <div>
                {/* Total price is prominent when multiple quantities */}
                <div className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}>
                  {formatPriceDisplay(totalPriceInCents)}
                </div>
                <div className="text-xs text-gray-400">
                  {formatPriceDisplay(partPriceInCents)} × {qty}
                </div>
              </div>
            ) : (
              <div className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}>
                {formatPriceDisplay(partPriceInCents)}
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
