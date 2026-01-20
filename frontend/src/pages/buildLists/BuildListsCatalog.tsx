import React, { useCallback, useEffect, useState } from 'react';
import BuildListCatalogList from '../../components/buildLists/BuildListCatalogList';
import BuildListItem from '../../components/buildLists/BuildListItem';
import Card from '../../components/common/Card';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
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
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // Fetch featured build lists (top 4 voted)
  const fetchFeaturedBuildListsFn = useCallback(
    () => buildListsApi.getBuildListsWithVotes({ limit: 4, skip: 0 }),
    []
  );

  const {
    data: featuredBuildListsData,
    isLoading: isLoadingFeatured,
    executeRequest: fetchFeaturedBuildLists,
  } = useApiRequest(fetchFeaturedBuildListsFn);

  // Memoize request functions to prevent infinite re-renders
  const fetchMakeStatsFn = useCallback(() => carsApi.getCarMakeStats(), []);

  // Fetch available manufacturers
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  // Memoize cars by make request function
  const fetchCarsByMakeFn = useCallback(
    (make: string) => carsApi.getCarsByMake(make, { limit: 1000 }),
    []
  );

  // Fetch cars by make when make is selected
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
      const makes = Object.keys(makeStats).sort();
      setAvailableMakes(makes);
    }
  }, [makeStats]);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      setSelectedModel(''); // Reset model when make changes
      setSelectedGeneration(null); // Reset generation when make changes
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
    // Reset generation when model changes
    if (selectedModel) {
      setSelectedGeneration(null);
    }
  }, [selectedModel]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedMake, selectedModel]);

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  };

  // Get unique models for selected make
  const uniqueModels = Array.from(
    new Set(availableCars.map((car) => car.model))
  ).sort();

  // Get generations (cars) for selected make and model
  const generations = availableCars
    .filter((car) => car.make === selectedMake && car.model === selectedModel)
    .sort((a, b) => {
      // Sort by start_year, then generation_name
      if (a.start_year !== b.start_year) {
        return a.start_year - b.start_year;
      }
      return a.generation_name.localeCompare(b.generation_name);
    });

  const showBuildLists = selectedGeneration !== null;

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
              Select a manufacturer and car model to browse build lists for that
              specific vehicle.
            </p>
            <p>
              Click on any build list to view its details and see what parts are
              included.
            </p>
          </div>
        </div>
      </Card>

      {/* Car Selection Tiles - 3 Layer Selection */}
      <div className="space-y-6 mb-6">
        {/* Layer 1: Make Selection */}
        <div>
          {selectedMake ? (
            <h3 className="text-lg font-semibold text-gray-200 mb-4">
              <button
                type="button"
                onClick={() => {
                  if (selectedModel) {
                    // On generation page, go back to models
                    setSelectedModel('');
                    setSelectedGeneration(null);
                  } else {
                    // On model page, go back to manufacturers
                    setSelectedMake('');
                    setSelectedModel('');
                    setSelectedGeneration(null);
                  }
                }}
                className="text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                {selectedModel
                  ? '← Back to Car Models'
                  : '← Back to Manufacturers'}
              </button>
            </h3>
          ) : (
            <Card className="mb-6">
              <SectionHeader title="Select Manufacturer" />
              {isLoadingMakes ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner />
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mt-4">
                  {availableMakes.map((make) => (
                    <Card
                      key={make}
                      onClick={() => setSelectedMake(make)}
                      interactive
                      className="text-center p-4 cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                    >
                      <h4 className="text-lg font-semibold text-gray-200">
                        {make}
                      </h4>
                    </Card>
                  ))}
                </div>
              )}
            </Card>
          )}
          {!selectedMake && (
            <>
              {/* Featured Build Lists Section - Only show when no make is selected */}
              <Card className="mb-6 mt-6">
                <SectionHeader title="Featured Build Lists" />
                {isLoadingFeatured ? (
                  <div className="flex items-center justify-center py-8">
                    <LoadingSpinner />
                  </div>
                ) : featuredBuildListsData?.data &&
                  featuredBuildListsData.data.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-4">
                    {featuredBuildListsData.data.map((buildList) => (
                      <BuildListItem
                        key={buildList.id}
                        buildList={buildList}
                        showVoteButtons={false}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-400">
                    <p>No featured build lists available.</p>
                  </div>
                )}
              </Card>
            </>
          )}

          {/* Layer 2: Model Selection */}
          {selectedMake && !selectedModel && (
            <>
              <Card className="mb-4 bg-indigo-900/20 border-indigo-500/50">
                <div className="p-4">
                  <p className="text-sm text-gray-400 mb-1">
                    Selected Manufacturer
                  </p>
                  <h3 className="text-xl font-semibold text-indigo-400">
                    {selectedMake}
                  </h3>
                </div>
              </Card>
              <h3 className="text-lg font-semibold text-gray-200 mb-4 mt-6">
                Select Model
              </h3>
              {isLoadingCars ? (
                <Card>
                  <div className="flex items-center justify-center py-8">
                    <LoadingSpinner />
                  </div>
                </Card>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                  {uniqueModels.map((model) => (
                    <Card
                      key={model}
                      onClick={() => setSelectedModel(model)}
                      interactive
                      className="text-center p-4 cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                    >
                      <h4 className="text-lg font-semibold text-gray-200">
                        {model}
                      </h4>
                    </Card>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Layer 3: Generation Selection */}
          {selectedMake && selectedModel && !selectedGeneration && (
            <>
              <Card className="mb-4 bg-indigo-900/20 border-indigo-500/50">
                <div className="p-4">
                  <p className="text-sm text-gray-400 mb-1">Selected Vehicle</p>
                  <h3 className="text-xl font-semibold text-indigo-400">
                    {selectedMake} {selectedModel}
                  </h3>
                </div>
              </Card>
              <h3 className="text-lg font-semibold text-gray-200 mb-4 mt-6">
                Select Generation
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {generations.map((car) => (
                  <Card
                    key={car.id}
                    onClick={() => setSelectedGeneration(car)}
                    interactive
                    className="cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                  >
                    {car.image_url && (
                      <img
                        src={car.image_url}
                        alt={`${car.make} ${car.model} ${car.generation_name}`}
                        className="w-full h-32 object-cover rounded-md mb-3"
                      />
                    )}
                    <h4 className="text-lg font-semibold text-indigo-400 mb-1">
                      {car.generation_name}
                    </h4>
                    <p className="text-sm text-gray-400">
                      {car.start_year} - {car.end_year}
                    </p>
                    {car.description && (
                      <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                        {car.description}
                      </p>
                    )}
                  </Card>
                ))}
              </div>
            </>
          )}

          {/* Selected Generation Info */}
          {selectedGeneration && (
            <Card className="mb-4">
              <div className="flex items-center gap-6">
                <div className="flex-shrink-0">
                  <ImageWithPlaceholder
                    srcUrl={selectedGeneration.image_url ?? null}
                    altText={`${selectedGeneration.make} ${selectedGeneration.model} ${selectedGeneration.generation_name}`}
                    containerClassName="w-32 h-32 rounded-lg overflow-hidden"
                    imageClassName="w-full h-full object-cover"
                    fallbackText="No image"
                    fallbackTextClassName="text-gray-500 text-xs"
                  />
                </div>
                <div className="flex-1 flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-200">
                      Selected: {selectedGeneration.make}{' '}
                      {selectedGeneration.model}{' '}
                      {selectedGeneration.generation_name}
                    </h3>
                    <p className="text-sm text-gray-400">
                      {selectedGeneration.start_year} -{' '}
                      {selectedGeneration.end_year}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-sm"
                  >
                    Change Selection
                  </button>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Build Lists List */}
      {showBuildLists && selectedGeneration ? (
        <>
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
                  id="search-build-lists"
                  type="text"
                  placeholder="Search by name or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          <BuildListCatalogList
            carIds={[selectedGeneration.id]}
            params={{
              skip: (currentPage - 1) * itemsPerPage,
              limit: itemsPerPage,
              ...(searchTerm && { search: searchTerm }),
            }}
            title={`${selectedGeneration.make} ${selectedGeneration.model} ${selectedGeneration.generation_name} Build Lists`}
            emptyMessage="No build lists found for this car. Try adjusting your search or select a different vehicle."
            showVoteButtons={false}
          />
        </>
      ) : null}
    </div>
  );
};

export default BuildListsCatalog;
