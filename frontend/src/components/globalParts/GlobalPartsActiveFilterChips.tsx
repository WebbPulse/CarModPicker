import React from 'react';
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

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {selectedCategoryIds.map((id) => {
        const cat = activeCategories.find((c) => c.id === id);
        if (!cat) return null;
        return (
          <span
            key={`cat-${id}`}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-900/50 text-indigo-300 text-sm"
          >
            {cat.display_name || cat.name}
            <button
              type="button"
              onClick={() => toggleCategory(id)}
              className="hover:text-white"
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
          <span
            key={`brand-${id}`}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-900/50 text-indigo-300 text-sm"
          >
            {brand.name}
            <button
              type="button"
              onClick={() => toggleBrand(id)}
              className="hover:text-white"
              aria-label="Remove brand filter"
            >
              ×
            </button>
          </span>
        );
      })}
      {(selectedGeneration || showUniversalParts) && (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-900/50 text-indigo-300 text-sm">
          {showUniversalParts
            ? 'Universal'
            : `${selectedGeneration?.make} ${selectedGeneration?.model} ${selectedGeneration?.generation_name}`}
          <button
            type="button"
            onClick={clearVehicleFilter}
            className="hover:text-white"
            aria-label="Remove vehicle filter"
          >
            ×
          </button>
        </span>
      )}
      {hasPriceRange && (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-900/50 text-indigo-300 text-sm">
          {priceMin.trim() && priceMax.trim()
            ? `$${priceMin.trim()} – $${priceMax.trim()}`
            : priceMin.trim()
              ? `Min $${priceMin.trim()}`
              : `Max $${priceMax.trim()}`}
          <button
            type="button"
            onClick={clearPriceRange}
            className="hover:text-white"
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
