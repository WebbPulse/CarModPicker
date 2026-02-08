import React, { useMemo, useState } from 'react';
import Card from '../common/Card';
import VehicleFilterSection from '../common/VehicleFilterSection';
import type { BrandResponse, CarRead, CategoryResponse } from '../../types/Api';

const MAX_BRANDS_VISIBLE = 40;
const MAX_CATEGORIES_VISIBLE = 20;

export interface GlobalPartsFilterSidebarProps {
  hasActiveFilters: boolean;
  clearAllFilters: () => void;
  // Car / Vehicle
  showUniversalParts: boolean;
  setShowUniversalParts: (v: boolean) => void;
  selectedMake: string;
  selectedModel: string;
  selectedGeneration: CarRead | null;
  setSelectedMake: (make: string) => void;
  setSelectedModel: (model: string) => void;
  setSelectedGeneration: (car: CarRead | null) => void;
  availableMakes: string[];
  uniqueModels: string[];
  generations: CarRead[];
  isLoadingMakes: boolean;
  isLoadingCars: boolean;
  // Price
  priceMin: string;
  priceMax: string;
  setPriceMin: (s: string) => void;
  setPriceMax: (s: string) => void;
  // Categories (multi-select)
  activeCategories: CategoryResponse[];
  availableCategoryIds: number[];
  selectedCategoryIds: number[];
  toggleCategory: (id: number) => void;
  setSelectedCategoryIds: (ids: number[]) => void;
  // Brands (multi-select)
  availableBrands: BrandResponse[];
  availableBrandIds: number[];
  selectedBrandIds: number[];
  toggleBrand: (id: number) => void;
  setSelectedBrandIds: (ids: number[]) => void;
}

const GlobalPartsFilterSidebar: React.FC<GlobalPartsFilterSidebarProps> = (
  props
) => {
  const [brandSearchTerm, setBrandSearchTerm] = useState('');
  const [brandsExpanded, setBrandsExpanded] = useState(false);
  const [categoriesExpanded, setCategoriesExpanded] = useState(false);
  const {
    hasActiveFilters,
    clearAllFilters,
    showUniversalParts,
    setShowUniversalParts,
    selectedMake,
    selectedModel,
    selectedGeneration,
    setSelectedMake,
    setSelectedModel,
    setSelectedGeneration,
    availableMakes,
    uniqueModels,
    generations,
    isLoadingMakes,
    isLoadingCars,
    priceMin,
    priceMax,
    setPriceMin,
    setPriceMax,
    activeCategories,
    availableCategoryIds,
    selectedCategoryIds,
    toggleCategory,
    setSelectedCategoryIds,
    availableBrands,
    availableBrandIds,
    selectedBrandIds,
    toggleBrand,
    setSelectedBrandIds,
  } = props;

  const sectionTitleClass =
    'text-xs font-medium text-gray-500 uppercase tracking-wider pb-2 mb-3 border-b border-gray-700/60';
  const clearButtonClass =
    'block w-full text-left px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-700/50 hover:text-gray-300 transition-colors';
  const inputClass =
    'w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500/50 transition-colors';
  const checkboxRowClass =
    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer text-gray-300 hover:bg-gray-700/50 hover:text-gray-100 transition-colors';
  const checkboxInputClass =
    'rounded border-gray-500 bg-gray-800 text-indigo-500 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-0 focus:ring-offset-gray-900';

  const allowedCategoryIds = useMemo(
    () => new Set(availableCategoryIds),
    [availableCategoryIds]
  );
  const allowedBrandIds = useMemo(
    () => new Set(availableBrandIds),
    [availableBrandIds]
  );
  const selectedCategoryIdsSet = useMemo(
    () => new Set(selectedCategoryIds),
    [selectedCategoryIds]
  );
  const selectedBrandIdsSet = useMemo(
    () => new Set(selectedBrandIds),
    [selectedBrandIds]
  );

  const visibleCategories = useMemo(
    () =>
      activeCategories.filter((cat) => allowedCategoryIds.has(cat.id)),
    [activeCategories, allowedCategoryIds]
  );
  const visibleBrands = useMemo(() => {
    const byAllowed = availableBrands.filter((b) => allowedBrandIds.has(b.id));
    const bySearch = brandSearchTerm.trim()
      ? byAllowed.filter((b) =>
          b.name
            .toLowerCase()
            .includes(brandSearchTerm.trim().toLowerCase())
        )
      : byAllowed;
    return bySearch;
  }, [availableBrands, allowedBrandIds, brandSearchTerm]);

  const categoriesToRender = categoriesExpanded
    ? visibleCategories
    : visibleCategories.slice(0, MAX_CATEGORIES_VISIBLE);
  const categoriesHasMore = visibleCategories.length > MAX_CATEGORIES_VISIBLE;
  const brandsToRender = brandsExpanded
    ? visibleBrands
    : visibleBrands.slice(0, MAX_BRANDS_VISIBLE);
  const brandsHasMore = visibleBrands.length > MAX_BRANDS_VISIBLE;

  return (
    <aside className="lg:w-64 flex-shrink-0">
      <Card className="sticky top-4 overflow-hidden">
        <div className="p-4 space-y-6">
          <div className="flex items-center justify-between pb-2 border-b border-gray-700/60">
            <h2 className="text-base font-semibold text-gray-100">Filters</h2>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Car / Vehicle Filter */}
          <VehicleFilterSection
            showUniversalParts={showUniversalParts}
            setShowUniversalParts={setShowUniversalParts}
            selectedMake={selectedMake}
            selectedModel={selectedModel}
            selectedGeneration={selectedGeneration}
            setSelectedMake={setSelectedMake}
            setSelectedModel={setSelectedModel}
            setSelectedGeneration={setSelectedGeneration}
            availableMakes={availableMakes}
            uniqueModels={uniqueModels}
            generations={generations}
            isLoadingMakes={isLoadingMakes}
            isLoadingCars={isLoadingCars}
          />

          {/* Price range filter */}
          <div>
            <h3 className={sectionTitleClass}>Price Range</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label
                  htmlFor="price-min"
                  className="text-sm text-gray-500 shrink-0 w-12"
                >
                  Min ($)
                </label>
                <input
                  id="price-min"
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="No min"
                  value={priceMin}
                  onChange={(e) => setPriceMin(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="flex items-center gap-2">
                <label
                  htmlFor="price-max"
                  className="text-sm text-gray-500 shrink-0 w-12"
                >
                  Max ($)
                </label>
                <input
                  id="price-max"
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="No max"
                  value={priceMax}
                  onChange={(e) => setPriceMax(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
          </div>

          {/* Category Filter */}
          <div>
            <h3 className={sectionTitleClass}>Part Category</h3>
            <div className="space-y-2">
              {selectedCategoryIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedCategoryIds([])}
                  className={clearButtonClass}
                >
                  Clear categories
                </button>
              )}
              {categoriesToRender.map((cat) => (
                <label key={cat.id} className={checkboxRowClass}>
                  <input
                    type="checkbox"
                    checked={selectedCategoryIdsSet.has(cat.id)}
                    onChange={() => toggleCategory(cat.id)}
                    className={checkboxInputClass}
                  />
                  <span>{cat.display_name || cat.name}</span>
                </label>
              ))}
              {categoriesHasMore && (
                <button
                  type="button"
                  onClick={() => setCategoriesExpanded((e) => !e)}
                  className={clearButtonClass}
                >
                  {categoriesExpanded
                    ? 'Show less'
                    : `Show ${visibleCategories.length - MAX_CATEGORIES_VISIBLE} more`}
                </button>
              )}
            </div>
          </div>

          {/* Brand Filter */}
          <div>
            <h3 className={sectionTitleClass}>Part Brand</h3>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Search brands..."
                value={brandSearchTerm}
                onChange={(e) => setBrandSearchTerm(e.target.value)}
                className={inputClass}
              />
              {selectedBrandIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedBrandIds([])}
                  className={clearButtonClass}
                >
                  Clear brands
                </button>
              )}
              <div className="max-h-60 overflow-y-auto">
                {brandsToRender.map((brand) => (
                  <label key={brand.id} className={checkboxRowClass}>
                    <input
                      type="checkbox"
                      checked={selectedBrandIdsSet.has(brand.id)}
                      onChange={() => toggleBrand(brand.id)}
                      className={checkboxInputClass}
                    />
                    <span>{brand.name}</span>
                  </label>
                ))}
              </div>
              {brandsHasMore && (
                <button
                  type="button"
                  onClick={() => setBrandsExpanded((e) => !e)}
                  className={clearButtonClass}
                >
                  {brandsExpanded
                    ? 'Show less'
                    : `Show ${visibleBrands.length - MAX_BRANDS_VISIBLE} more`}
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>
    </aside>
  );
};

export default GlobalPartsFilterSidebar;
