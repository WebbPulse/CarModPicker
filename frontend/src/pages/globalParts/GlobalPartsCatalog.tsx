import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import SecondaryButton from '../../components/buttons/SecondaryButton';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import AddToBuildListDialog from '../../components/globalParts/AddToBuildListDialog';
import GlobalPartList from '../../components/globalParts/GlobalPartList';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { useAuth } from '../../hooks/useAuth';
import { categoriesApi } from '../../services/Api';
import type {
  CategoryResponse,
  GlobalPartReadWithVotes,
  PaginationInfo,
} from '../../types/Api';

const GlobalPartsCatalog: React.FC = () => {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedCategoryData, setSelectedCategoryData] =
    useState<CategoryResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;
  const [selectedGlobalPart, setSelectedGlobalPart] =
    useState<GlobalPartReadWithVotes | null>(null);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo | null>(
    null
  );
  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
    setLoading(false);
  }, [loadCategories]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedCategory]);

  const handleVoteUpdate = () => {
    // Do nothing - let the VoteButtons component handle optimistic updates
    // This prevents the entire catalog from re-rendering
  };

  const handleAddToBuildList = (globalPart: GlobalPartReadWithVotes) => {
    setSelectedGlobalPart(globalPart);
    setIsAddToBuildListDialogOpen(true);
  };

  const handlePartAdded = () => {
    // Refresh the global parts list if needed
    console.log('Part added to build list');
  };

  const handleCategorySelect = (category: CategoryResponse) => {
    setSelectedCategory(category.id);
    setSelectedCategoryData(category);
    setSearchTerm('');
    setCurrentPage(1);
  };

  const handleBackToCategories = () => {
    setSelectedCategory(null);
    setSelectedCategoryData(null);
    setSearchTerm('');
    setCurrentPage(1);
  };

  // Memoize params to prevent infinite re-render loop
  const params = useMemo(
    () => ({
      skip: (currentPage - 1) * itemsPerPage,
      limit: itemsPerPage,
      ...(selectedCategory && { category_id: selectedCategory }),
      ...(searchTerm && { search: searchTerm }),
    }),
    [currentPage, itemsPerPage, selectedCategory, searchTerm]
  );

  // Memoize the pagination change handler to prevent unnecessary re-renders
  const handlePaginationChange = useCallback(
    (pagination: PaginationInfo | null) => {
      setPaginationInfo(pagination);
    },
    []
  );

  // Filter active categories and sort by sort_order
  const activeCategories = useMemo(() => {
    return categories
      .filter((category) => category.is_active)
      .sort((a, b) => a.sort_order - b.sort_order);
  }, [categories]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white">
        <PageHeader title="Parts Catalog" />
        <div className="flex justify-center items-center h-64">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Parts Catalog" />

      {/* Tab Navigation */}
      {isAuthenticated && (
        <div className="mb-6">
          <div className="flex space-x-1 bg-gray-800 p-1 rounded-lg border border-gray-700">
            <Link
              to="/global-parts"
              className={`flex-1 text-center px-4 py-2 rounded-md font-medium transition-all duration-200 ${
                location.pathname === '/global-parts'
                  ? 'bg-primary-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              Parts Catalog
            </Link>
            <Link
              to="/my-global-parts"
              className={`flex-1 text-center px-4 py-2 rounded-md font-medium transition-all duration-200 ${
                location.pathname === '/my-global-parts'
                  ? 'bg-primary-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              My Parts
            </Link>
          </div>
        </div>
      )}

      {/* Category View (default) */}
      {!selectedCategory && (
        <>
          <div className="mb-6">
            <SectionHeader title="Browse by Category" />
            <p className="text-gray-400 text-sm mt-2">
              Select a category to browse parts, or use search to find specific
              parts.
            </p>
          </div>

          {/* Search Bar */}
          <div className="mb-8">
            <div className="flex gap-4">
              <div className="flex-1">
                <label
                  htmlFor="search-parts"
                  className="block text-sm font-medium text-gray-300 mb-2"
                >
                  Search All Parts
                </label>
                <Input
                  type="text"
                  placeholder="Search parts..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full"
                />
              </div>
            </div>
            {searchTerm && (
              <div className="mt-4">
                <SecondaryButton onClick={() => setSearchTerm('')}>
                  Clear Search
                </SecondaryButton>
              </div>
            )}
          </div>

          {/* Show parts if searching, otherwise show categories */}
          {searchTerm ? (
            <GlobalPartList
              params={params}
              title="Search Results"
              emptyMessage="No parts found. Try adjusting your search."
              showVoteButtons={true}
              onVoteUpdate={handleVoteUpdate}
              showAddToBuildListButton={true}
              onAddToBuildList={handleAddToBuildList}
              onPaginationChange={handlePaginationChange}
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {activeCategories.map((category: CategoryResponse) => (
                <Card
                  key={category.id}
                  className="cursor-pointer hover:bg-gray-800 transition-colors border-2 border-gray-700 hover:border-blue-500"
                  onClick={() => handleCategorySelect(category)}
                >
                  <div className="p-6 text-center">
                    <div className="text-4xl mb-3">{category.icon || '📦'}</div>
                    <h3 className="text-lg font-semibold text-white mb-2">
                      {category.display_name || category.name}
                    </h3>
                    {category.description && (
                      <p className="text-sm text-gray-400 line-clamp-2">
                        {category.description}
                      </p>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {/* Category Parts View */}
      {selectedCategory && selectedCategoryData && (
        <>
          <div className="mb-6 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-3xl">
                  {selectedCategoryData.icon || '📦'}
                </span>
                <SectionHeader
                  title={
                    selectedCategoryData.display_name ||
                    selectedCategoryData.name
                  }
                />
              </div>
              {selectedCategoryData.description && (
                <p className="text-gray-400 text-sm">
                  {selectedCategoryData.description}
                </p>
              )}
            </div>
            <SecondaryButton onClick={handleBackToCategories}>
              ← Back to Categories
            </SecondaryButton>
          </div>

          {/* Search within category */}
          <div className="mb-8">
            <div className="flex gap-4">
              <div className="flex-1">
                <label
                  htmlFor="search-parts"
                  className="block text-sm font-medium text-gray-300 mb-2"
                >
                  Search in Category
                </label>
                <Input
                  type="text"
                  placeholder="Search parts in this category..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full"
                />
              </div>
              {searchTerm && (
                <div className="flex items-end">
                  <SecondaryButton onClick={() => setSearchTerm('')}>
                    Clear
                  </SecondaryButton>
                </div>
              )}
            </div>
          </div>

          {/* Parts List */}
          <GlobalPartList
            params={params}
            title=""
            emptyMessage="No parts found in this category. Try adjusting your search."
            showVoteButtons={true}
            onVoteUpdate={handleVoteUpdate}
            showAddToBuildListButton={true}
            onAddToBuildList={handleAddToBuildList}
            onPaginationChange={handlePaginationChange}
          />
        </>
      )}

      {/* Pagination - Only show when viewing parts (category selected or searching) */}
      {paginationInfo && (selectedCategory || searchTerm) && (
        <Pagination
          currentPage={paginationInfo.current_page}
          totalPages={paginationInfo.total_pages}
          totalItems={paginationInfo.total_items}
          itemsPerPage={paginationInfo.items_per_page}
          onPageChange={(page) => setCurrentPage(page)}
        />
      )}

      {/* Add to Build List Dialog */}
      <AddToBuildListDialog
        isOpen={isAddToBuildListDialogOpen}
        onClose={() => setIsAddToBuildListDialogOpen(false)}
        globalPart={selectedGlobalPart}
        onPartAdded={handlePartAdded}
      />
    </div>
  );
};

export default GlobalPartsCatalog;
