import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
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

const BuildListPartListItem: React.FC<BuildListPartListItemProps> = React.memo(
  ({
    buildListPart,
    category,
    onEdit,
    onDelete,
    onTogglePurchased,
    canEdit = false,
    canDelete = false,
    canMarkPurchased = false,
  }) => {
    const navigate = useNavigate();
    const { global_part, notes, quantity, purchased } = buildListPart;

    // Prices from retailer listings (best_price_cents when available)
    const partPriceInCents = global_part.best_price_cents;
    const qty = quantity || 1;
    const totalPriceInCents =
      partPriceInCents !== null && partPriceInCents !== undefined
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

    const handleCardClick = () => {
      void navigate(`/global-parts/${global_part.id}`);
    };

    const handleCardClickWithCheck = (e: React.MouseEvent<HTMLDivElement>) => {
      // Only navigate if the click wasn't on an interactive element
      const target = e.target as HTMLElement;
      const isInteractiveElement =
        target.closest('button') ||
        target.closest('a') ||
        target.closest('input') ||
        target.closest('label');

      if (!isInteractiveElement) {
        handleCardClick();
      }
    };

    const handleInteractiveClick = (e: React.MouseEvent) => {
      e.stopPropagation();
    };

    return (
      <div onClick={handleCardClickWithCheck}>
        <Card
          className={`py-1 px-2 ${purchased ? 'opacity-60' : ''} cursor-pointer hover:border-blue-500 transition-colors`}
        >
          <div className={`grid ${gridCols} items-center gap-3`}>
            {/* Purchased checkbox */}
            {showCheckbox && (
              <div className="flex items-center justify-center min-w-[28px]">
                <label
                  className="relative flex items-center cursor-pointer"
                  title={
                    purchased ? 'Mark as not purchased' : 'Mark as purchased'
                  }
                  onClick={handleInteractiveClick}
                >
                  <input
                    type="checkbox"
                    checked={purchased}
                    onChange={(e) => {
                      e.stopPropagation();
                      onTogglePurchased?.(buildListPart);
                    }}
                    className="sr-only peer"
                    aria-label={
                      purchased ? 'Mark as not purchased' : 'Mark as purchased'
                    }
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
                <h3
                  className={`text-sm font-semibold ${purchased ? 'text-gray-400 line-through' : 'text-white'}`}
                >
                  <Link
                    to={`/global-parts/${global_part.id}`}
                    className="hover:text-blue-400 transition-colors"
                    onClick={handleInteractiveClick}
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
                  <span className="text-xs text-gray-500">
                    {global_part.brand}
                  </span>
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
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(buildListPart);
                  }}
                  className="text-xs px-1.5 py-0.5"
                >
                  Edit
                </SecondaryButton>
              )}
              {canDelete && onDelete && (
                <ActionButton
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(buildListPart.id);
                  }}
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
                    <div
                      className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}
                    >
                      {formatPriceDisplay(totalPriceInCents)}
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatPriceDisplay(partPriceInCents)} × {qty}
                    </div>
                  </div>
                ) : (
                  <div
                    className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}
                  >
                    {formatPriceDisplay(partPriceInCents)}
                  </div>
                )
              ) : (
                <div className="text-sm text-gray-500">No price</div>
              )}
            </div>
          </div>
        </Card>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function to prevent unnecessary re-renders
    // Only re-render if the part data, purchased status, permissions, or callbacks change
    return (
      prevProps.buildListPart.id === nextProps.buildListPart.id &&
      prevProps.buildListPart.purchased === nextProps.buildListPart.purchased &&
      prevProps.buildListPart.quantity === nextProps.buildListPart.quantity &&
      prevProps.buildListPart.notes === nextProps.buildListPart.notes &&
      prevProps.buildListPart.global_part.best_price_cents ===
        nextProps.buildListPart.global_part.best_price_cents &&
      prevProps.canEdit === nextProps.canEdit &&
      prevProps.canDelete === nextProps.canDelete &&
      prevProps.canMarkPurchased === nextProps.canMarkPurchased &&
      prevProps.category?.id === nextProps.category?.id &&
      prevProps.onTogglePurchased === nextProps.onTogglePurchased &&
      prevProps.onEdit === nextProps.onEdit &&
      prevProps.onDelete === nextProps.onDelete
    );
  }
);

BuildListPartListItem.displayName = 'BuildListPartListItem';

export default BuildListPartListItem;
