import React, { useState } from 'react';
import Card from '../common/Card';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import type { BrandResponse, CarRead, CategoryResponse } from '../../types/Api';

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

  return (
    <aside className="lg:w-64 flex-shrink-0">
      <Card className="sticky top-4 overflow-hidden">
        <div className="p-4 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-200">Filters</h2>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="text-sm text-indigo-400 hover:text-indigo-300"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Car / Vehicle Filter */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2 uppercase tracking-wider">
              Car / Vehicle
            </h3>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => {
                  setShowUniversalParts(false);
                  setSelectedMake('');
                  setSelectedModel('');
                  setSelectedGeneration(null);
                }}
                className={`block w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  !showUniversalParts && !selectedGeneration
                    ? 'bg-indigo-600/30 text-indigo-300 font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
              >
                All Vehicles
              </button>

              {!showUniversalParts && (
                <>
                  {isLoadingMakes ? (
                    <div className="flex justify-center py-2">
                      <LoadingSpinner />
                    </div>
                  ) : (
                    <select
                      value={selectedMake}
                      onChange={(e) => {
                        setSelectedMake(e.target.value);
                        setSelectedModel('');
                        setSelectedGeneration(null);
                      }}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">Select Make</option>
                      {availableMakes.map((make) => (
                        <option key={make} value={make}>
                          {make}
                        </option>
                      ))}
                    </select>
                  )}

                  {selectedMake && (
                    <>
                      <select
                        value={selectedModel}
                        onChange={(e) => {
                          setSelectedModel(e.target.value);
                          setSelectedGeneration(null);
                        }}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">Select Model</option>
                        {uniqueModels.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>

                      {selectedModel && (
                        <div className="space-y-1">
                          {isLoadingCars ? (
                            <LoadingSpinner />
                          ) : (
                            generations.map((car) => (
                              <button
                                key={car.id}
                                type="button"
                                onClick={() => setSelectedGeneration(car)}
                                className={`block w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
                                  selectedGeneration?.id === car.id
                                    ? 'bg-indigo-600/30 text-indigo-300 font-medium'
                                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                                }`}
                              >
                                {car.generation_name} ({car.start_year}-
                                {car.end_year})
                              </button>
                            ))
                          )}
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              <button
                type="button"
                onClick={() => {
                  setShowUniversalParts(true);
                  setSelectedMake('');
                  setSelectedModel('');
                  setSelectedGeneration(null);
                }}
                className={`block w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  showUniversalParts
                    ? 'bg-indigo-600/30 text-indigo-300 font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
              >
                Universal Parts
              </button>
            </div>
          </div>

          {/* Price range filter */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2 uppercase tracking-wider">
              Price Range
            </h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label htmlFor="price-min" className="text-sm text-gray-400 shrink-0">
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
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="price-max" className="text-sm text-gray-400 shrink-0">
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
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Category Filter */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2 uppercase tracking-wider">
              Part Category
            </h3>
            <div className="space-y-1">
              {selectedCategoryIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedCategoryIds([])}
                  className="block w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                >
                  Clear categories
                </button>
              )}
              {activeCategories
                .filter((cat) => availableCategoryIds.includes(cat.id))
                .map((cat) => (
                  <label
                    key={cat.id}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-gray-800 text-gray-300 hover:text-gray-200"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCategoryIds.includes(cat.id)}
                      onChange={() => toggleCategory(cat.id)}
                      className="rounded border-gray-500 bg-gray-800 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span>{cat.display_name || cat.name}</span>
                  </label>
                ))}
            </div>
          </div>

          {/* Brand Filter */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2 uppercase tracking-wider">
              Part Brand
            </h3>
            <div className="space-y-1">
              <Input
                type="text"
                placeholder="Search brands..."
                value={brandSearchTerm}
                onChange={(e) => setBrandSearchTerm(e.target.value)}
                className="w-full text-sm"
              />
              {selectedBrandIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedBrandIds([])}
                  className="block w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                >
                  Clear brands
                </button>
              )}
              {availableBrands
                .filter((b) => availableBrandIds.includes(b.id))
                .filter(
                  (b) =>
                    !brandSearchTerm.trim() ||
                    b.name
                      .toLowerCase()
                      .includes(brandSearchTerm.trim().toLowerCase())
                )
                .map((brand) => (
                  <label
                    key={brand.id}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-gray-800 text-gray-300 hover:text-gray-200"
                  >
                    <input
                      type="checkbox"
                      checked={selectedBrandIds.includes(brand.id)}
                      onChange={() => toggleBrand(brand.id)}
                      className="rounded border-gray-500 bg-gray-800 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span>{brand.name}</span>
                  </label>
                ))}
            </div>
          </div>
        </div>
      </Card>
    </aside>
  );
};

export default GlobalPartsFilterSidebar;
