import React, { useState } from 'react';
import Card from '../common/Card';
import VehicleFilterSection from '../common/VehicleFilterSection';
import type {
  PartManufacturerResponse,
  CarGenerationRead,
  CategoryResponse,
} from '../../types/Api';

export interface PartsFilterSidebarProps {
  hasActiveFilters: boolean;
  clearAllFilters: () => void;
  // Car / Vehicle
  showUniversalParts: boolean;
  setShowUniversalParts: (v: boolean) => void;
  // Community-contributed (UGC) visibility
  hideUgc: boolean;
  setHideUgc: (v: boolean) => void;
  selectedMake: string;
  selectedModel: string;
  selectedGeneration: CarGenerationRead | null;
  setSelectedMake: (make: string) => void;
  setSelectedModel: (model: string) => void;
  setSelectedGeneration: (car: CarGenerationRead | null) => void;
  availableMakes: string[];
  uniqueModels: string[];
  generations: CarGenerationRead[];
  isLoadingMakes: boolean;
  isLoadingCars: boolean;
  // Price
  priceMin: string;
  priceMax: string;
  setPriceMin: (s: string) => void;
  setPriceMax: (s: string) => void;
  // Categories (multi-select)
  activeCategories: CategoryResponse[];
  availableCategoryIds: string[];
  selectedCategoryIds: string[];
  toggleCategory: (id: string) => void;
  setSelectedCategoryIds: (ids: string[]) => void;
  // PartManufacturers (multi-select)
  availablePartManufacturers: PartManufacturerResponse[];
  availablePartManufacturerIds: string[];
  selectedPartManufacturerIds: string[];
  togglePartManufacturer: (id: string) => void;
  setSelectedPartManufacturerIds: (ids: string[]) => void;
}

const PartsFilterSidebar: React.FC<PartsFilterSidebarProps> = (props) => {
  const [part_manufacturerSearchTerm, setPartManufacturerSearchTerm] =
    useState('');
  const {
    hasActiveFilters,
    clearAllFilters,
    showUniversalParts,
    setShowUniversalParts,
    hideUgc,
    setHideUgc,
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
    availablePartManufacturers,
    availablePartManufacturerIds,
    selectedPartManufacturerIds,
    togglePartManufacturer,
    setSelectedPartManufacturerIds,
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

  return (
    <aside className="lg:w-64 flex-shrink-0">
      <Card className="sticky top-4 overflow-hidden">
        <div className="p-4 space-y-6 overflow-y-auto max-h-[calc(100vh-5rem)]">
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

          {/* Quality / source filter */}
          <div>
            <h3 className={sectionTitleClass}>Source</h3>
            <label className={checkboxRowClass}>
              <input
                type="checkbox"
                checked={hideUgc}
                onChange={(e) => setHideUgc(e.target.checked)}
                className={checkboxInputClass}
              />
              <span className="flex-1">
                Hide community-contributed
                <span className="block text-xs text-gray-500">
                  Show only scraped catalog parts (more reliable details).
                </span>
              </span>
            </label>
          </div>

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
              {activeCategories
                .filter((cat) => availableCategoryIds.includes(cat.id))
                .map((cat) => (
                  <label key={cat.id} className={checkboxRowClass}>
                    <input
                      type="checkbox"
                      checked={selectedCategoryIds.includes(cat.id)}
                      onChange={() => toggleCategory(cat.id)}
                      className={checkboxInputClass}
                    />
                    <span>{cat.display_name || cat.name}</span>
                  </label>
                ))}
            </div>
          </div>

          {/* PartManufacturer Filter */}
          <div>
            <h3 className={sectionTitleClass}>Part Manufacturer</h3>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Search part manufacturers..."
                value={part_manufacturerSearchTerm}
                onChange={(e) => setPartManufacturerSearchTerm(e.target.value)}
                className={inputClass}
              />
              {selectedPartManufacturerIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedPartManufacturerIds([])}
                  className={clearButtonClass}
                >
                  Clear part manufacturers
                </button>
              )}
              {availablePartManufacturers
                .filter((b) => availablePartManufacturerIds.includes(b.id))
                .filter(
                  (b) =>
                    !part_manufacturerSearchTerm.trim() ||
                    b.name
                      .toLowerCase()
                      .includes(
                        part_manufacturerSearchTerm.trim().toLowerCase()
                      )
                )
                .map((part_manufacturer) => (
                  <label
                    key={part_manufacturer.id}
                    className={checkboxRowClass}
                  >
                    <input
                      type="checkbox"
                      checked={selectedPartManufacturerIds.includes(
                        part_manufacturer.id
                      )}
                      onChange={() =>
                        togglePartManufacturer(part_manufacturer.id)
                      }
                      className={checkboxInputClass}
                    />
                    <span>{part_manufacturer.name}</span>
                  </label>
                ))}
            </div>
          </div>
        </div>
      </Card>
    </aside>
  );
};

export default PartsFilterSidebar;
