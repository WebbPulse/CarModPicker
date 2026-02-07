import React, { useCallback, useEffect, useMemo, useState } from 'react';
import BuildListCatalogList from '../../components/buildLists/BuildListCatalogList';
import BuildListCard from '../../components/buildLists/BuildListCard';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import VehicleFilterChips from '../../components/common/VehicleFilterChips';
import VehicleFilterSection from '../../components/common/VehicleFilterSection';
import PageHeader from '../../components/layout/PageHeader';
import {
  BUILD_LISTS_CATALOG_ITEMS_PER_PAGE,
  FEATURED_BUILD_LISTS_LIMIT,
  LARGE_FETCH_LIMIT,
} from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi, carsApi } from '../../services/Api';
import type { CarRead } from '../../types/Api';

const BuildListsCatalog: React.FC = () => {
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = BUILD_LISTS_CATALOG_ITEMS_PER_PAGE;

  // Debounce search so API is called only after user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchFeaturedBuildListsFn = useCallback(
    () =>
      buildListsApi.getBuildListsWithVotes({
        limit: FEATURED_BUILD_LISTS_LIMIT,
        skip: 0,
      }),
    []
  );

  const {
    data: featuredBuildListsData,
    isLoading: isLoadingFeatured,
    error: featuredBuildListsError,
    executeRequest: fetchFeaturedBuildLists,
  } = useApiRequest(fetchFeaturedBuildListsFn);

  const fetchMakeStatsFn = useCallback(() => carsApi.getCarMakeStats(), []);
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  const fetchCarsByMakeFn = useCallback(
    (make: string) => carsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
    []
  );
  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  useEffect(() => {
    void fetchMakes();
    void fetchFeaturedBuildLists();
  }, [fetchMakes, fetchFeaturedBuildLists]);

  useEffect(() => {
    if (makeStats) {
      setAvailableMakes(Object.keys(makeStats).sort());
    }
  }, [makeStats]);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      setSelectedModel('');
      setSelectedGeneration(null);
    } else {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, fetchCarsByMake]);

  useEffect(() => {
    if (carsByMake) {
      setAvailableCars(carsByMake);
    }
  }, [carsByMake]);

  useEffect(() => {
    if (selectedModel) {
      setSelectedGeneration(null);
    }
  }, [selectedModel]);

  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchTerm, selectedMake, selectedModel]);

  const clearAllFilters = () => {
    setSearchTerm('');
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  };

  const clearVehicleFilter = () => {
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  };

  const hasActiveFilters =
    selectedGeneration !== null || searchTerm.trim() !== '';

  const uniqueModels = Array.from(
    new Set(availableCars.map((car) => car.model))
  ).sort();

  const generations = availableCars
    .filter((car) => car.make === selectedMake && car.model === selectedModel)
    .sort((a, b) => {
      if (a.start_year !== b.start_year) return a.start_year - b.start_year;
      return a.generation_name.localeCompare(b.generation_name);
    });

  const hasVehicleSelected = selectedGeneration !== null;

  // When no vehicle selected, filter featured list by search (client-side)
  const featuredBuildListsFiltered = useMemo(() => {
    const list = featuredBuildListsData?.data ?? [];
    const term = searchTerm.trim().toLowerCase();
    if (!term) return list;
    return list.filter(
      (bl) =>
        bl.name?.toLowerCase().includes(term) ||
        bl.description?.toLowerCase().includes(term)
    );
  }, [featuredBuildListsData?.data, searchTerm]);

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="mb-6">
        <PageHeader title="Build Lists Catalog" />
      </div>

      {/* Same layout as global-parts: sidebar + main from the start */}
      <div className="flex flex-col lg:flex-row gap-6">
        <aside className="lg:w-64 flex-shrink-0">
          <Card className="sticky top-4 overflow-hidden">
            <div className="p-4 space-y-6">
              <div className="flex items-center justify-between pb-2 border-b border-gray-700/60">
                <h2 className="text-base font-semibold text-gray-100">
                  Filters
                </h2>
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
              <VehicleFilterSection
                showUniversalParts={false}
                setShowUniversalParts={() => {}}
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
                hideUniversalOption
              />
            </div>
          </Card>
        </aside>

        <main className="flex-1 min-w-0">
          <div className="mb-4">
            <Input
              type="text"
              placeholder="Search build lists..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full max-w-md"
            />
          </div>

          <VehicleFilterChips
            selectedGeneration={selectedGeneration}
            showUniversalParts={false}
            clearVehicleFilter={clearVehicleFilter}
            searchTerm={searchTerm}
            onClearSearch={() => setSearchTerm('')}
          />

          {hasVehicleSelected && selectedGeneration ? (
            <BuildListCatalogList
              carIds={[selectedGeneration.id]}
              params={{
                skip: (currentPage - 1) * itemsPerPage,
                limit: itemsPerPage,
                ...(debouncedSearchTerm.trim() && {
                  search: debouncedSearchTerm.trim(),
                }),
              }}
              title={`${selectedGeneration.make} ${selectedGeneration.model} ${selectedGeneration.generation_name} Build Lists`}
              emptyMessage="No build lists found for this car. Try adjusting your search or select a different vehicle."
              showVoteButtons={false}
              layout="card"
            />
          ) : (
            <Card>
              <div className="p-4">
                <h3 className="text-lg font-semibold text-gray-200 mb-2">
                  Featured Build Lists
                </h3>
                <p className="text-sm text-gray-400 mb-4">
                  Select a vehicle in the sidebar to browse build lists for that
                  car, or explore featured builds below.
                </p>
                {isLoadingFeatured ? (
                  <div className="flex justify-center py-12">
                    <LoadingSpinner />
                  </div>
                ) : featuredBuildListsError ? (
                  <ErrorAlert
                    message={`Failed to load featured build lists: ${featuredBuildListsError}`}
                  />
                ) : featuredBuildListsFiltered.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {featuredBuildListsFiltered.map((buildList) => (
                      <BuildListCard
                        key={buildList.id}
                        buildList={buildList}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-center py-8">
                    {featuredBuildListsData?.data &&
                    featuredBuildListsData.data.length > 0 &&
                    searchTerm.trim()
                      ? 'No build lists match your search.'
                      : 'No featured build lists available.'}
                  </p>
                )}
              </div>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
};

export default BuildListsCatalog;
