import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import SecondaryButton from '../../components/buttons/SecondaryButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import AddToBuildListDialog from '../../components/globalParts/AddToBuildListDialog';
import GlobalPartList from '../../components/globalParts/GlobalPartList';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { carsApi, categoriesApi } from '../../services/Api';
import type {
  CarRead,
  CategoryResponse,
  GlobalPartReadWithVotes,
  PaginationInfo,
} from '../../types/Api';
import {
  GLOBAL_PARTS_ITEMS_PER_PAGE,
  LARGE_FETCH_LIMIT,
} from '../../constants';

const GlobalPartsCatalog: React.FC = () => {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [showUniversalParts, setShowUniversalParts] = useState(false);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedCategoryData, setSelectedCategoryData] =
    useState<CategoryResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = GLOBAL_PARTS_ITEMS_PER_PAGE;
  const [selectedGlobalPart, setSelectedGlobalPart] =
    useState<GlobalPartReadWithVotes | null>(null);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo | null>(
    null
  );
  // Fetch available manufacturers
  const fetchMakeStatsFn = useCallback(() => carsApi.getCarMakeStats(), []);

  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    error: makesError,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  // Memoize cars by make request function
  const fetchCarsByMakeFn = useCallback(
    (make: string) => carsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
    []
  );

  // Fetch cars by make when make is selected
  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    error: carsError,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  // Fetch car by ID (for URL parameter support)
  const fetchCarByIdFn = useCallback(
    (carId: number) => carsApi.getCar(carId),
    []
  );

  const {
    data: carFromUrl,
    isLoading: isLoadingCarFromUrl,
    error: carFromUrlError,
    executeRequest: fetchCarById,
  } = useApiRequest(fetchCarByIdFn);

  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch {
      // Failed to load categories
    }
  }, []);

  useEffect(() => {
    void fetchMakes();
    void loadCategories();
    setLoading(false);
  }, [fetchMakes, loadCategories]);

  // Handle car_id from URL parameters
  useEffect(() => {
    const carIdParam = searchParams.get('car_id');
    if (carIdParam) {
      const carId = Number.parseInt(carIdParam, 10);
      if (!Number.isNaN(carId)) {
        void fetchCarById(carId);
      }
    }
  }, [searchParams, fetchCarById]);

  useEffect(() => {
    if (makeStats) {
      const makes = Object.keys(makeStats).sort();
      setAvailableMakes(makes);
    }
  }, [makeStats]);

  // Track if we're initializing from URL to prevent resetting
  const [isInitializingFromUrl, setIsInitializingFromUrl] = useState(false);
  const isInitializingFromUrlRef = useRef(false);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      // Only reset if we're not initializing from URL (check ref for synchronous access)
      if (!isInitializingFromUrlRef.current) {
        setSelectedModel(''); // Reset model when make changes
        setSelectedGeneration(null); // Reset generation when make changes
        setShowUniversalParts(false); // Reset universal parts when selecting a make
      }
    } else if (!showUniversalParts) {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, fetchCarsByMake, showUniversalParts]);

  useEffect(() => {
    if (carsByMake) {
      setAvailableCars(carsByMake);
    }
  }, [carsByMake]);

  // When car is loaded from URL, set the filters
  useEffect(() => {
    if (carFromUrl) {
      // Set ref first so other effects can check it synchronously
      isInitializingFromUrlRef.current = true;
      setIsInitializingFromUrl(true);
      // Set all filters at once to avoid intermediate resets
      setSelectedMake(carFromUrl.make);
      setSelectedModel(carFromUrl.model);
      setSelectedGeneration(carFromUrl); // Set immediately from URL data
      setShowUniversalParts(false);
      // Fetch cars for the make so the dropdowns are populated
      void fetchCarsByMake(carFromUrl.make);
    }
  }, [carFromUrl, fetchCarsByMake]);

  // Update generation with matching car from loaded list (if available)
  useEffect(() => {
    if (
      isInitializingFromUrl &&
      carFromUrl &&
      carsByMake &&
      carsByMake.length > 0
    ) {
      // Find the matching car in the loaded list (in case it has more complete data)
      const matchingCar = carsByMake.find((car) => car.id === carFromUrl.id);
      if (matchingCar) {
        setSelectedGeneration(matchingCar);
      }
      // Mark initialization as complete
      isInitializingFromUrlRef.current = false;
      setIsInitializingFromUrl(false);
    }
  }, [isInitializingFromUrl, carFromUrl, carsByMake]);

  useEffect(() => {
    // Reset generation when model changes (but not when initializing from URL)
    // Also don't reset if we already have a generation selected that matches the current make/model
    if (selectedModel && !isInitializingFromUrlRef.current) {
      // Only reset if the current generation doesn't match the selected model
      if (selectedGeneration && selectedGeneration.model !== selectedModel) {
        setSelectedGeneration(null);
      }
    }
  }, [selectedModel, selectedGeneration]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedCategory, selectedGeneration, showUniversalParts]);

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

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
    setShowUniversalParts(false);
    setSelectedCategory(null);
    setSelectedCategoryData(null);
    setCurrentPage(1);
  };

  const handleUniversalPartsSelect = () => {
    setShowUniversalParts(true);
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
    setSelectedCategory(null);
    setSelectedCategoryData(null);
    setSearchTerm('');
    setCurrentPage(1);
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

  // Memoize params to prevent infinite re-render loop
  const params = useMemo(
    () => ({
      skip: (currentPage - 1) * itemsPerPage,
      limit: itemsPerPage,
      ...(selectedCategory && { category_id: selectedCategory }),
      // Only include car_id if a specific generation is selected (not for universal parts)
      ...(selectedGeneration &&
        !showUniversalParts && { car_id: selectedGeneration.id }),
      ...(searchTerm && { search: searchTerm }),
    }),
    [
      currentPage,
      itemsPerPage,
      selectedCategory,
      selectedGeneration,
      showUniversalParts,
      searchTerm,
    ]
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

      {/* Information Panel */}
      <Card className="mb-6">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-gray-200 mb-3">
            Explore Parts Catalog
          </h3>
          <div className="text-sm text-gray-400">
            <p className="mb-2">
              Select a manufacturer, car model, and generation to browse parts
              for that specific vehicle, or choose "Universal Parts" for parts
              not tied to a specific car.
            </p>
            <p>
              After selecting a car or universal parts, you can browse parts by
              category or search for specific parts.
            </p>
          </div>
        </div>
      </Card>

      {/* Car Selection Tiles - 3 Layer Selection */}
      <div className="space-y-6 mb-6">
        {/* Layer 1: Make Selection */}
        <div>
          <h3 className="text-lg font-semibold text-gray-200 mb-4">
            {selectedMake || showUniversalParts ? (
              <button
                type="button"
                onClick={() => {
                  if (selectedModel) {
                    // On generation page, go back to models
                    setSelectedModel('');
                    setSelectedGeneration(null);
                    setSelectedCategory(null);
                    setSelectedCategoryData(null);
                  } else {
                    // On model page or universal parts, go back to manufacturers
                    setSelectedMake('');
                    setSelectedModel('');
                    setSelectedGeneration(null);
                    setShowUniversalParts(false);
                    setSelectedCategory(null);
                    setSelectedCategoryData(null);
                  }
                }}
                className="text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                {selectedModel ? '← Back to Car Models' : '← Back to Selection'}
              </button>
            ) : (
              'Select Manufacturer or Universal Parts'
            )}
          </h3>
          {!selectedMake && !showUniversalParts && (
            <>
              {isLoadingMakes || isLoadingCarFromUrl ? (
                <Card>
                  <div className="flex items-center justify-center py-8">
                    <LoadingSpinner />
                  </div>
                </Card>
              ) : makesError ? (
                <Card>
                  <ErrorAlert
                    message={`Failed to load manufacturers: ${makesError}`}
                  />
                </Card>
              ) : carFromUrlError ? (
                <Card>
                  <ErrorAlert
                    message={`Failed to load car from URL: ${carFromUrlError}`}
                  />
                </Card>
              ) : (
                <>
                  {/* Universal Parts Option */}
                  <Card
                    onClick={handleUniversalPartsSelect}
                    interactive
                    className="text-center p-6 cursor-pointer hover:border-indigo-500 border-2 border-indigo-500/50 bg-indigo-900/20 transition-colors mb-4"
                  >
                    <div className="text-4xl mb-2">🌐</div>
                    <h4 className="text-lg font-semibold text-indigo-400 mb-1">
                      Universal Parts
                    </h4>
                    <p className="text-sm text-gray-400">
                      Parts not tied to a specific car (wheels, tools, etc.)
                    </p>
                  </Card>

                  {/* Manufacturer Options */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
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
                </>
              )}
            </>
          )}

          {/* Layer 2: Model Selection */}
          {selectedMake && !selectedModel && !isLoadingCarFromUrl && (
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
              ) : carsError ? (
                <Card>
                  <ErrorAlert
                    message={`Failed to load car models: ${carsError}`}
                  />
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
          {selectedMake &&
            selectedModel &&
            !selectedGeneration &&
            !isLoadingCarFromUrl && (
              <>
                <Card className="mb-4 bg-indigo-900/20 border-indigo-500/50">
                  <div className="p-4">
                    <p className="text-sm text-gray-400 mb-1">
                      Selected Vehicle
                    </p>
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

      {/* Universal Parts Selected Info */}
      {showUniversalParts && !selectedCategory && (
        <Card className="mb-4">
          <div className="flex items-center gap-6">
            <div className="flex-shrink-0">
              <div className="w-32 h-32 rounded-lg bg-indigo-900/20 border-2 border-indigo-500/50 flex items-center justify-center">
                <span className="text-6xl">🌐</span>
              </div>
            </div>
            <div className="flex-1 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-200">
                  Universal Parts
                </h3>
                <p className="text-sm text-gray-400">
                  Parts not tied to a specific car (wheels, tools, accessories,
                  etc.)
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

      {/* Category View - Only show after car or universal parts is selected */}
      {(selectedGeneration || showUniversalParts) && !selectedCategory && (
        <>
          <div className="mb-6">
            <SectionHeader title="Browse by Category" />
            <p className="text-gray-400 text-sm mt-2">
              Select a category to browse parts for this vehicle, or use search
              to find specific parts.
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
                  Search Parts
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
          ) : loading ? (
            <Card>
              <div className="flex justify-center py-8">
                <LoadingSpinner />
              </div>
            </Card>
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
      {paginationInfo &&
        (selectedGeneration || showUniversalParts) &&
        (selectedCategory || searchTerm) && (
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
