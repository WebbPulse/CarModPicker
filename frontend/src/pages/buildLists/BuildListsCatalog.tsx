import React, { useEffect, useState } from 'react';
import BuildListCatalogList from '../../components/buildLists/BuildListCatalogList';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import PageHeader from '../../components/layout/PageHeader';

const BuildListsCatalog: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm]);

  const params = {
    skip: (currentPage - 1) * itemsPerPage,
    limit: itemsPerPage,
    ...(searchTerm && { search: searchTerm }),
  };

  const clearFilters = () => {
    setSearchTerm('');
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Build Lists Catalog" />

      {/* Information Panel */}
      <Card className="mb-6">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-gray-200 mb-3">
            Explore Build Lists
          </h3>
          <div className="text-sm text-gray-400">
            <p className="mb-2">
              Browse through build lists created by the community. Each build
              list represents a collection of parts for a specific car project.
            </p>
            <p>
              Click on any build list to view its details and see what parts are
              included.
            </p>
          </div>
        </div>
      </Card>

      {/* Search Filter */}
      <div className="mb-8 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <label
              htmlFor="search-build-lists"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Search Build Lists
            </label>
            <Input
              type="text"
              placeholder="Search by name or description..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={clearFilters}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Build Lists List */}
      <BuildListCatalogList
        params={params}
        title="All Build Lists"
        emptyMessage="No build lists found. Try adjusting your search."
      />
    </div>
  );
};

export default BuildListsCatalog;
