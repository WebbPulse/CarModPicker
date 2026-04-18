import React from 'react';
import { filterChipClass } from '../common/VehicleFilterChips';
import type {
  PartManufacturerResponse,
  CarGenerationRead,
  CategoryResponse,
} from '../../types/Api';

export interface PartsActiveFilterChipsProps {
  hasActiveFilters: boolean;
  selectedCategoryIds: string[];
  activeCategories: CategoryResponse[];
  toggleCategory: (id: string) => void;
  selectedPartManufacturerIds: string[];
  availablePartManufacturers: PartManufacturerResponse[];
  togglePartManufacturer: (id: string) => void;
  selectedGeneration: CarGenerationRead | null;
  selectedMake?: string;
  selectedModel?: string;
  showUniversalParts: boolean;
  clearVehicleFilter: () => void;
  hasPriceRange: boolean;
  priceMin: string;
  priceMax: string;
  clearPriceRange: () => void;
}

const PartsActiveFilterChips: React.FC<PartsActiveFilterChipsProps> = (
  props
) => {
  const {
    hasActiveFilters,
    selectedCategoryIds,
    activeCategories,
    toggleCategory,
    selectedPartManufacturerIds,
    availablePartManufacturers,
    togglePartManufacturer,
    selectedGeneration,
    selectedMake = '',
    selectedModel = '',
    showUniversalParts,
    clearVehicleFilter,
    hasPriceRange,
    priceMin,
    priceMax,
    clearPriceRange,
  } = props;

  if (!hasActiveFilters) return null;

  const removeButtonClass =
    'p-0.5 rounded-full hover:bg-gray-600/80 hover:text-white transition-colors shrink-0';

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {selectedCategoryIds.map((id) => {
        const cat = activeCategories.find((c) => c.id === id);
        if (!cat) return null;
        return (
          <span key={`cat-${id}`} className={filterChipClass}>
            {cat.display_name || cat.name}
            <button
              type="button"
              onClick={() => toggleCategory(id)}
              className={removeButtonClass}
              aria-label="Remove category filter"
            >
              ×
            </button>
          </span>
        );
      })}
      {selectedPartManufacturerIds.map((id) => {
        const part_manufacturer = availablePartManufacturers.find(
          (b) => b.id === id
        );
        if (!part_manufacturer) return null;
        return (
          <span key={`part_manufacturer-${id}`} className={filterChipClass}>
            {part_manufacturer.name}
            <button
              type="button"
              onClick={() => togglePartManufacturer(id)}
              className={removeButtonClass}
              aria-label="Remove part manufacturer filter"
            >
              ×
            </button>
          </span>
        );
      })}
      {(selectedGeneration || showUniversalParts || selectedMake) && (
        <span className={filterChipClass}>
          {showUniversalParts
            ? 'Universal'
            : selectedGeneration
              ? `${selectedGeneration.make ?? ''} ${selectedGeneration.model ?? ''} ${selectedGeneration.generation_name ?? ''}`.trim()
              : `${selectedMake}${selectedModel ? ` ${selectedModel}` : ''}`.trim() ||
                'Vehicle'}
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
      {hasPriceRange && (
        <span className={filterChipClass}>
          {priceMin.trim() && priceMax.trim()
            ? `$${priceMin.trim()} – $${priceMax.trim()}`
            : priceMin.trim()
              ? `Min $${priceMin.trim()}`
              : `Max $${priceMax.trim()}`}
          <button
            type="button"
            onClick={clearPriceRange}
            className={removeButtonClass}
            aria-label="Remove price range filter"
          >
            ×
          </button>
        </span>
      )}
    </div>
  );
};

export default PartsActiveFilterChips;
