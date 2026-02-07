import React from 'react';
import { filterChipClass } from '../common/VehicleFilterChips';
import type { BrandResponse, CarRead, CategoryResponse } from '../../types/Api';

export interface GlobalPartsActiveFilterChipsProps {
  hasActiveFilters: boolean;
  selectedCategoryIds: number[];
  activeCategories: CategoryResponse[];
  toggleCategory: (id: number) => void;
  selectedBrandIds: number[];
  availableBrands: BrandResponse[];
  toggleBrand: (id: number) => void;
  selectedGeneration: CarRead | null;
  showUniversalParts: boolean;
  clearVehicleFilter: () => void;
  hasPriceRange: boolean;
  priceMin: string;
  priceMax: string;
  clearPriceRange: () => void;
}

const GlobalPartsActiveFilterChips: React.FC<GlobalPartsActiveFilterChipsProps> = (
  props
) => {
  const {
    hasActiveFilters,
    selectedCategoryIds,
    activeCategories,
    toggleCategory,
    selectedBrandIds,
    availableBrands,
    toggleBrand,
    selectedGeneration,
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
      {selectedBrandIds.map((id) => {
        const brand = availableBrands.find((b) => b.id === id);
        if (!brand) return null;
        return (
          <span key={`brand-${id}`} className={filterChipClass}>
            {brand.name}
            <button
              type="button"
              onClick={() => toggleBrand(id)}
              className={removeButtonClass}
              aria-label="Remove brand filter"
            >
              ×
            </button>
          </span>
        );
      })}
      {(selectedGeneration || showUniversalParts) && (
        <span className={filterChipClass}>
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

export default GlobalPartsActiveFilterChips;
