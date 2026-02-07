import React from 'react';
import type { CarRead } from '../../types/Api';

export interface VehicleFilterChipsProps {
  selectedGeneration: CarRead | null;
  showUniversalParts: boolean;
  clearVehicleFilter: () => void;
  searchTerm?: string;
  onClearSearch?: () => void;
}

const chipClass =
  'inline-flex items-center gap-1.5 pl-3 pr-1 py-1.5 rounded-full bg-gray-800 border border-gray-600/80 text-gray-200 text-sm';
const removeButtonClass =
  'p-0.5 rounded-full hover:bg-gray-600/80 hover:text-white transition-colors';

const VehicleFilterChips: React.FC<VehicleFilterChipsProps> = ({
  selectedGeneration,
  showUniversalParts,
  clearVehicleFilter,
  searchTerm = '',
  onClearSearch,
}) => {
  const hasVehicle =
    selectedGeneration !== null || showUniversalParts;
  const hasSearch = searchTerm.trim() !== '' && onClearSearch;
  if (!hasVehicle && !hasSearch) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {hasVehicle && (
        <span className={chipClass}>
          {showUniversalParts
            ? 'Universal'
            : `${selectedGeneration?.make} ${selectedGeneration?.model} ${selectedGeneration?.generation_name}`}
          <button
            type="button"
            onClick={clearVehicleFilter}
            className={removeButtonClass}
            aria-label="Remove vehicle filter"
          >
            ×
          </button>
        </span>
      )}
      {hasSearch && (
        <span className={chipClass}>
          Search: &quot;{searchTerm.trim()}&quot;
          <button
            type="button"
            onClick={onClearSearch}
            className={removeButtonClass}
            aria-label="Clear search"
          >
            ×
          </button>
        </span>
      )}
    </div>
  );
};

export default VehicleFilterChips;
