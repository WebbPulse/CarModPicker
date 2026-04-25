import React, { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import AddToBuildListDialog from '../../components/parts/AddToBuildListDialog';
import PartList from '../../components/parts/PartList';
import PartsFilterSidebar from '../../components/parts/PartsFilterSidebar';
import PartsActiveFilterChips from '../../components/parts/PartsActiveFilterChips';
import PageHeader from '../../components/layout/PageHeader';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import Pagination from '../../components/ui/pagination';
import { useAuth } from '../../hooks/useAuth';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { usePartsFilters } from '../../hooks/usePartsFilters';
import type { PartReadWithVotes, PaginationInfo } from '../../types/Api';

const PartsCatalog: React.FC = () => {
  useDocumentMeta({
    title: 'Parts Catalog',
    description:
      'Browse car modification parts shared by the CarModPicker community. Filter by make, model, and generation to find parts that fit your build.',
    canonicalPath: '/parts',
  });
  const { isAuthenticated } = useAuth();
  const [selectedPart, setSelectedPart] = useState<PartReadWithVotes | null>(
    null
  );
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);

  const filters = usePartsFilters({ syncToUrl: true });

  const handlePaginationChange = useCallback(
    (pagination: PaginationInfo | null) => {
      filters.setPaginationInfo(pagination);
    },
    [filters]
  );

  const handleAddToBuildList = useCallback((part: PartReadWithVotes) => {
    setSelectedPart(part);
    setIsAddToBuildListDialogOpen(true);
  }, []);

  const sidebarProps = {
    hasActiveFilters: filters.hasActiveFilters,
    clearAllFilters: filters.clearAllFilters,
    showUniversalParts: filters.showUniversalParts,
    setShowUniversalParts: filters.setShowUniversalParts,
    hideUgc: filters.hideUgc,
    setHideUgc: filters.setHideUgc,
    selectedMake: filters.selectedMake,
    selectedModel: filters.selectedModel,
    selectedGeneration: filters.selectedGeneration,
    setSelectedMake: filters.setSelectedMake,
    setSelectedModel: filters.setSelectedModel,
    setSelectedGeneration: filters.setSelectedGeneration,
    availableMakes: filters.availableMakes,
    uniqueModels: filters.uniqueModels,
    generations: filters.generations,
    isLoadingMakes: filters.isLoadingMakes,
    isLoadingCars: filters.isLoadingCars,
    priceMin: filters.priceMin,
    priceMax: filters.priceMax,
    setPriceMin: filters.setPriceMin,
    setPriceMax: filters.setPriceMax,
    activeCategories: filters.activeCategories,
    availableCategoryIds: filters.availableCategoryIds,
    selectedCategoryIds: filters.selectedCategoryIds,
    toggleCategory: filters.toggleCategory,
    setSelectedCategoryIds: filters.setSelectedCategoryIds,
    availablePartManufacturers: filters.availablePartManufacturers,
    availablePartManufacturerIds: filters.availablePartManufacturerIds,
    selectedPartManufacturerIds: filters.selectedPartManufacturerIds,
    togglePartManufacturer: filters.togglePartManufacturer,
    setSelectedPartManufacturerIds: filters.setSelectedPartManufacturerIds,
  };

  const chipsProps = {
    hasActiveFilters: filters.hasActiveFilters,
    selectedCategoryIds: filters.selectedCategoryIds,
    activeCategories: filters.activeCategories,
    toggleCategory: filters.toggleCategory,
    selectedPartManufacturerIds: filters.selectedPartManufacturerIds,
    availablePartManufacturers: filters.availablePartManufacturers,
    togglePartManufacturer: filters.togglePartManufacturer,
    selectedGeneration: filters.selectedGeneration,
    selectedMake: filters.selectedMake,
    selectedModel: filters.selectedModel,
    showUniversalParts: filters.showUniversalParts,
    clearVehicleFilter: filters.clearVehicleFilter,
    hasPriceRange: filters.hasPriceRange,
    priceMin: filters.priceMin,
    priceMax: filters.priceMax,
    clearPriceRange: filters.clearPriceRange,
  };

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="Parts Catalog" />
        {isAuthenticated && (
          <Button asChild variant="outline">
            <Link to="/my-parts">My Parts</Link>
          </Button>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <PartsFilterSidebar {...sidebarProps} />

        <main className="flex-1 min-w-0">
          <div className="mb-4">
            <Input
              type="text"
              placeholder="Search parts..."
              value={filters.searchTerm}
              onChange={(e) => filters.setSearchTerm(e.target.value)}
              className="w-full max-w-md"
              data-testid="parts-catalog-search"
            />
          </div>

          <PartsActiveFilterChips {...chipsProps} />

          <PartList
            params={filters.params}
            title=""
            emptyMessage="No parts found. Try adjusting your filters."
            showVoteButtons
            onVoteUpdate={() => {}}
            showAddToBuildListButton
            onAddToBuildList={handleAddToBuildList}
            onPaginationChange={handlePaginationChange}
            sortParam={filters.sortParam}
            onSortChange={filters.setSortParam}
            layout="table"
            categories={filters.activeCategories}
            part_manufacturers={filters.availablePartManufacturers}
          />

          {filters.paginationInfo && filters.paginationInfo.total_pages > 1 && (
            <Pagination
              currentPage={filters.paginationInfo.current_page}
              totalPages={filters.paginationInfo.total_pages}
              totalItems={filters.paginationInfo.total_items}
              itemsPerPage={filters.paginationInfo.items_per_page}
              onPageChange={filters.setCurrentPage}
            />
          )}
        </main>
      </div>

      <AddToBuildListDialog
        isOpen={isAddToBuildListDialogOpen}
        onClose={() => setIsAddToBuildListDialogOpen(false)}
        part={selectedPart}
        onPartAdded={() => {}}
      />
    </div>
  );
};

export default PartsCatalog;
