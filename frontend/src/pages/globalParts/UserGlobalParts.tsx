import React, { useCallback, useState } from 'react';
import LinkButton from '../../components/buttons/LinkButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Input from '../../components/common/Input';
import Pagination from '../../components/common/Pagination';
import GlobalPartList from '../../components/globalParts/GlobalPartList';
import GlobalPartsFilterSidebar from '../../components/globalParts/GlobalPartsFilterSidebar';
import GlobalPartsActiveFilterChips from '../../components/globalParts/GlobalPartsActiveFilterChips';
import PageHeader from '../../components/layout/PageHeader';
import { useAuth } from '../../hooks/useAuth';
import { useGlobalPartsFilters } from '../../hooks/useGlobalPartsFilters';
import { buildListPartsApi, globalPartsApi } from '../../services/Api';
import type { GlobalPartReadWithVotes, PaginationInfo } from '../../types/Api';

const UserGlobalParts: React.FC = () => {
  const { user, isAuthenticated } = useAuth();

  const [deletingPartId, setDeletingPartId] = useState<string | null>(null);
  const [deletingPartName, setDeletingPartName] = useState<string>('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);

  const filterOptions: Parameters<typeof useGlobalPartsFilters>[0] = {
    syncToUrl: false,
  };
  if (user?.id !== undefined) filterOptions.user_id = user.id;
  const filters = useGlobalPartsFilters(filterOptions);

  const handlePaginationChange = useCallback(
    (pagination: PaginationInfo | null) => {
      filters.setPaginationInfo(pagination);
    },
    [filters]
  );

  const handleDeleteClick = useCallback((part: GlobalPartReadWithVotes) => {
    setDeletingPartId(part.id);
    setDeletingPartName(part.name);
    void (async () => {
      try {
        const response =
          await buildListPartsApi.countBuildListsContainingGlobalPart(part.id);
        setBuildListCount(response.data.count);
      } catch {
        setBuildListCount(null);
      }
    })();
  }, []);

  const handleDelete = useCallback(async () => {
    if (!deletingPartId) return;
    setIsDeleting(true);
    try {
      await globalPartsApi.deleteGlobalPart(deletingPartId);
      setDeletingPartId(null);
      setDeletingPartName('');
      setBuildListCount(null);
      filters.setCurrentPage(1);
      setListRefreshKey((k) => k + 1);
    } catch {
      // Failed
    } finally {
      setIsDeleting(false);
    }
  }, [deletingPartId, filters]);

  const canDelete = useCallback(
    (part: GlobalPartReadWithVotes) =>
      !!user &&
      (part.user_id === user.id || user.is_admin || user.is_superuser),
    [user]
  );

  const sidebarProps = {
    hasActiveFilters: filters.hasActiveFilters,
    clearAllFilters: filters.clearAllFilters,
    showUniversalParts: filters.showUniversalParts,
    setShowUniversalParts: filters.setShowUniversalParts,
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
    availableBrands: filters.availableBrands,
    availableBrandIds: filters.availableBrandIds,
    selectedBrandIds: filters.selectedBrandIds,
    toggleBrand: filters.toggleBrand,
    setSelectedBrandIds: filters.setSelectedBrandIds,
  };

  const chipsProps = {
    hasActiveFilters: filters.hasActiveFilters,
    selectedCategoryIds: filters.selectedCategoryIds,
    activeCategories: filters.activeCategories,
    toggleCategory: filters.toggleCategory,
    selectedBrandIds: filters.selectedBrandIds,
    availableBrands: filters.availableBrands,
    toggleBrand: filters.toggleBrand,
    selectedGeneration: filters.selectedGeneration,
    showUniversalParts: filters.showUniversalParts,
    clearVehicleFilter: filters.clearVehicleFilter,
    hasPriceRange: filters.hasPriceRange,
    priceMin: filters.priceMin,
    priceMax: filters.priceMax,
    clearPriceRange: filters.clearPriceRange,
  };

  if (!isAuthenticated || !user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <ErrorAlert message="You must be logged in to view your parts." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="My Parts" />
        <LinkButton to="/global-parts" variant="outline" size="md">
          Browse All Parts
        </LinkButton>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <GlobalPartsFilterSidebar {...sidebarProps} />

        <main className="flex-1 min-w-0">
          <div className="mb-4">
            <Input
              type="text"
              placeholder="Search your parts..."
              value={filters.searchTerm}
              onChange={(e) => filters.setSearchTerm(e.target.value)}
              className="w-full max-w-md"
            />
          </div>

          <GlobalPartsActiveFilterChips {...chipsProps} />

          <GlobalPartList
            params={filters.params}
            refreshKey={listRefreshKey}
            title=""
            emptyMessage="You haven't created any parts yet. Parts you create will appear here."
            showVoteButtons
            onVoteUpdate={() => {}}
            onDelete={handleDeleteClick}
            canDelete={canDelete}
            onPaginationChange={handlePaginationChange}
            sortParam={filters.sortParam}
            onSortChange={filters.setSortParam}
            layout="table"
            categories={filters.activeCategories}
            brands={filters.availableBrands}
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

      <DeleteConfirmationDialog
        isOpen={deletingPartId !== null}
        onClose={() => {
          setDeletingPartId(null);
          setDeletingPartName('');
          setBuildListCount(null);
        }}
        onConfirm={() => void handleDelete()}
        itemName={deletingPartName}
        itemType="part"
        isProcessing={isDeleting}
        error={null}
        buildListCount={buildListCount ?? undefined}
      />
    </div>
  );
};

export default UserGlobalParts;
