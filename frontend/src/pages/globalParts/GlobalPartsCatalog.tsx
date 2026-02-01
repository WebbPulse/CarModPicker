import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import LinkButton from '../../components/buttons/LinkButton';
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
import {
  GLOBAL_PARTS_ITEMS_PER_PAGE,
  LARGE_FETCH_LIMIT,
} from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import {
  brandsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
} from '../../services/Api';
import type {
  BrandResponse,
  CarRead,
  CategoryResponse,
  GlobalPartReadWithVotes,
  PaginationInfo,
} from '../../types/Api';

type FilterMode = 'car_model' | 'brand' | 'category_car';

const GlobalPartsCatalog: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const [filterMode, setFilterMode] = useState<FilterMode>('category_car');
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [selectedBrand, setSelectedBrand] = useState<BrandResponse | null>(
    null
  );
  const [showUniversalParts, setShowUniversalParts] = useState(false);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [availableBrands, setAvailableBrands] = useState<BrandResponse[]>([]);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedCategoryData, setSelectedCategoryData] =
    useState<CategoryResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isInitializedFromUrl, setIsInitializedFromUrl] = useState(false);
  const itemsPerPage = GLOBAL_PARTS_ITEMS_PER_PAGE;
  const [selectedGlobalPart, setSelectedGlobalPart] =
    useState<GlobalPartReadWithVotes | null>(null);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo | null>(
    null
  );
  const [availableCategoryIds, setAvailableCategoryIds] = useState<Set<number>>(
    new Set()
  );
  const [hasCheckedForParts, setHasCheckedForParts] = useState(false);
  const [hasNoParts, setHasNoParts] = useState(false);

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

  const loadBrands = useCallback(async () => {
    try {
      const response = await brandsApi.getBrands(true);
      setAvailableBrands(response.data);
    } catch {
      // Failed to load brands
    }
  }, []);

  useEffect(() => {
    void fetchMakes();
    void loadCategories();
    void loadBrands();
    setLoading(false);
  }, [fetchMakes, loadCategories, loadBrands]);

  // Handle model selection from URL after cars are loaded
  useEffect(() => {
    if (
      isInitializingFromUrlRef.current &&
      selectedMake &&
      carsByMake &&
      carsByMake.length > 0
    ) {
      const modelParam = searchParams.get('model');
      if (modelParam) {
        const uniqueModels = Array.from(
          new Set(carsByMake.map((car) => car.model))
        );
        if (uniqueModels.includes(modelParam)) {
          setSelectedModel(modelParam);

          // Check if there's a car_id in URL for a specific generation
          const carIdParam = searchParams.get('car_id');
          if (carIdParam) {
            const carId = Number.parseInt(carIdParam, 10);
            if (!Number.isNaN(carId)) {
              const matchingCar = carsByMake.find((car) => car.id === carId);
              if (matchingCar && matchingCar.model === modelParam) {
                setSelectedGeneration(matchingCar);
              }
            }
          }
          isInitializingFromUrlRef.current = false;
          setIsInitializedFromUrl(true);
        } else {
          // Model not found, mark as initialized anyway
          isInitializingFromUrlRef.current = false;
          setIsInitializedFromUrl(true);
        }
      } else {
        // No model param, mark as initialized
        isInitializingFromUrlRef.current = false;
        setIsInitializedFromUrl(true);
      }
    }
  }, [selectedMake, carsByMake, searchParams]);

  useEffect(() => {
    if (makeStats) {
      const makes = Object.keys(makeStats).sort();
      setAvailableMakes(makes);
    }
  }, [makeStats]);

  // Track if we're initializing from URL to prevent resetting
  const isInitializingFromUrlRef = useRef(false);

  // Sync filter state to URL parameters
  const syncFiltersToUrl = useCallback(() => {
    if (isInitializedFromUrl) {
      // Only sync to URL after initial load from URL is complete
      const newParams = new URLSearchParams();

      // Filter mode
      if (filterMode !== 'category_car') {
        newParams.set('mode', filterMode);
      }

      // Car model filters
      if (filterMode === 'car_model') {
        if (showUniversalParts) {
          newParams.set('universal', 'true');
        } else if (selectedGeneration) {
          newParams.set('car_id', selectedGeneration.id.toString());
        } else if (selectedModel) {
          newParams.set('model', selectedModel);
          if (selectedMake) {
            newParams.set('make', selectedMake);
          }
        } else if (selectedMake) {
          newParams.set('make', selectedMake);
        }
      }

      // Brand filter
      if (filterMode === 'brand' && selectedBrand) {
        newParams.set('brand_id', selectedBrand.id.toString());
      }

      // Category & Car filter
      if (filterMode === 'category_car') {
        if (selectedCategory) {
          newParams.set('category_id', selectedCategory.toString());
        }
        if (selectedGeneration) {
          newParams.set('car_id', selectedGeneration.id.toString());
        } else if (selectedModel) {
          newParams.set('model', selectedModel);
          if (selectedMake) {
            newParams.set('make', selectedMake);
          }
        } else if (selectedMake) {
          newParams.set('make', selectedMake);
        }
      }

      // Category (for other modes)
      if (filterMode !== 'category_car' && selectedCategory) {
        newParams.set('category_id', selectedCategory.toString());
      }

      // Search term
      if (searchTerm) {
        newParams.set('search', searchTerm);
      }

      // Page (only if > 1)
      if (currentPage > 1) {
        newParams.set('page', currentPage.toString());
      }

      setSearchParams(newParams, { replace: true });
    }
  }, [
    filterMode,
    selectedMake,
    selectedModel,
    selectedGeneration,
    selectedBrand,
    showUniversalParts,
    selectedCategory,
    searchTerm,
    currentPage,
    isInitializedFromUrl,
    setSearchParams,
  ]);

  // Initialize filters from URL parameters
  const initializeFromUrl = useCallback(() => {
    if (
      isInitializedFromUrl ||
      !makeStats ||
      !categories.length ||
      !availableBrands.length
    ) {
      return;
    }

    // Check if there are any URL params to initialize from
    const hasUrlParams = Array.from(searchParams.keys()).length > 0;
    if (!hasUrlParams) {
      setIsInitializedFromUrl(true);
      return;
    }

    const mode = searchParams.get('mode') as FilterMode | null;
    if (mode === 'car_model' || mode === 'brand' || mode === 'category_car') {
      setFilterMode(mode);
    }

    let handledCarId = false;
    let handledMake = false;

    if (mode === 'category_car') {
      // Handle category first
      const categoryIdParam = searchParams.get('category_id');
      if (categoryIdParam) {
        const categoryId = Number.parseInt(categoryIdParam, 10);
        if (!Number.isNaN(categoryId)) {
          const category = categories.find((c) => c.id === categoryId);
          if (category) {
            setSelectedCategory(category.id);
            setSelectedCategoryData(category);
          }
        }
      }

      // Handle car_id (backward compatibility and direct car selection)
      const carIdParam = searchParams.get('car_id');
      if (carIdParam) {
        const carId = Number.parseInt(carIdParam, 10);
        if (!Number.isNaN(carId)) {
          isInitializingFromUrlRef.current = true;
          handledCarId = true;
          void fetchCarById(carId);
          // Don't set isInitializedFromUrl here - let the carFromUrl effect handle it
          return; // Let the car_id effect handle the rest
        }
      }

      // Handle make/model selection
      const makeParam = searchParams.get('make');
      const modelParam = searchParams.get('model');

      if (makeParam && availableMakes.includes(makeParam)) {
        handledMake = true;
        setSelectedMake(makeParam);
        if (modelParam) {
          // Wait for cars to load before setting model
          isInitializingFromUrlRef.current = true;
          void fetchCarsByMake(makeParam);
        } else {
          setIsInitializedFromUrl(true);
        }
      } else {
        setIsInitializedFromUrl(true);
      }
      return;
    }

    if (mode === 'car_model' || !mode) {
      // Handle car_id (backward compatibility and direct car selection)
      const carIdParam = searchParams.get('car_id');
      if (carIdParam) {
        const carId = Number.parseInt(carIdParam, 10);
        if (!Number.isNaN(carId)) {
          isInitializingFromUrlRef.current = true;
          handledCarId = true;
          void fetchCarById(carId);
          setIsInitializedFromUrl(true);
          return; // Let the car_id effect handle the rest
        }
      }

      // Handle universal parts
      const universalParam = searchParams.get('universal');
      if (universalParam === 'true') {
        setShowUniversalParts(true);
        setIsInitializedFromUrl(true);
        return;
      }

      // Handle make/model selection
      const makeParam = searchParams.get('make');
      const modelParam = searchParams.get('model');

      if (makeParam && availableMakes.includes(makeParam)) {
        handledMake = true;
        setSelectedMake(makeParam);
        if (modelParam) {
          // Wait for cars to load before setting model
          isInitializingFromUrlRef.current = true;
          void fetchCarsByMake(makeParam);
        } else {
          setIsInitializedFromUrl(true);
        }
      }
    } else if (mode === 'brand') {
      // Handle brand selection
      const brandIdParam = searchParams.get('brand_id');
      if (brandIdParam) {
        const brandId = Number.parseInt(brandIdParam, 10);
        if (!Number.isNaN(brandId)) {
          const brand = availableBrands.find((b) => b.id === brandId);
          if (brand) {
            setSelectedBrand(brand);
            setIsInitializedFromUrl(true);
            return;
          }
        }
      }
      // No brand_id or brand not found, mark as initialized anyway
      setIsInitializedFromUrl(true);
      return;
    }

    // Handle category (for car_model and brand modes only, category_car is handled above)
    // At this point, mode can only be 'car_model', 'brand', or null (category_car returns early)
    if (mode === 'car_model' || mode === 'brand' || mode === null) {
      const categoryIdParam = searchParams.get('category_id');
      if (categoryIdParam) {
        const categoryId = Number.parseInt(categoryIdParam, 10);
        if (!Number.isNaN(categoryId)) {
          const category = categories.find((c) => c.id === categoryId);
          if (category) {
            setSelectedCategory(category.id);
            setSelectedCategoryData(category);
          }
        }
      }
    }

    // Handle search term
    const searchParam = searchParams.get('search');
    if (searchParam) {
      setSearchTerm(searchParam);
    }

    // Handle page
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const page = Number.parseInt(pageParam, 10);
      if (!Number.isNaN(page) && page > 0) {
        setCurrentPage(page);
      }
    }

    // Mark as initialized if we didn't handle car_id or make (which need async loading)
    if (!handledCarId && !handledMake) {
      setIsInitializedFromUrl(true);
    }
  }, [
    searchParams,
    makeStats,
    categories,
    availableBrands,
    availableMakes,
    isInitializedFromUrl,
    fetchCarById,
    fetchCarsByMake,
  ]);

  // Initialize from URL when data is ready
  useEffect(() => {
    void initializeFromUrl();
  }, [initializeFromUrl]);

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
    if (carFromUrl && !isInitializedFromUrl) {
      // Set ref first so other effects can check it synchronously
      isInitializingFromUrlRef.current = true;
      // Set all filters at once to avoid intermediate resets
      setSelectedMake(carFromUrl.make);
      setSelectedModel(carFromUrl.model);
      setSelectedGeneration(carFromUrl); // Set immediately from URL data
      setShowUniversalParts(false);
      // Fetch cars for the make so the dropdowns are populated
      void fetchCarsByMake(carFromUrl.make);
    }
  }, [carFromUrl, fetchCarsByMake, isInitializedFromUrl]);

  // Update generation with matching car from loaded list (if available)
  useEffect(() => {
    if (
      isInitializingFromUrlRef.current &&
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
      setIsInitializedFromUrl(true);
    }
  }, [carFromUrl, carsByMake]);

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
  }, [
    searchTerm,
    selectedCategory,
    selectedGeneration,
    showUniversalParts,
    selectedBrand,
  ]);

  // Sync filters to URL when they change (debounced for search term)
  useEffect(() => {
    if (isInitializedFromUrl) {
      syncFiltersToUrl();
    }
  }, [
    filterMode,
    selectedMake,
    selectedModel,
    selectedGeneration,
    selectedBrand,
    showUniversalParts,
    selectedCategory,
    currentPage,
    syncFiltersToUrl,
    isInitializedFromUrl,
  ]);

  // Debounced sync for search term
  useEffect(() => {
    if (!isInitializedFromUrl) return;

    const timeoutId = setTimeout(() => {
      syncFiltersToUrl();
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [searchTerm, syncFiltersToUrl, isInitializedFromUrl]);

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
    setSelectedBrand(null);
    setShowUniversalParts(false);
    setSelectedCategory(null);
    setSelectedCategoryData(null);
    setCurrentPage(1);
  };

  const handleFilterModeChange = (mode: FilterMode) => {
    setFilterMode(mode);
    // Clear all filters when switching modes
    clearFilters();
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
      // Category filter (for car_model and brand modes, or when category is selected in category_car mode)
      ...(selectedCategory &&
        (filterMode !== 'category_car' || selectedGeneration) && {
          category_id: selectedCategory,
        }),
      // Only include car_id if a specific generation is selected (not for universal parts) and in car_model or category_car mode
      ...(selectedGeneration &&
        !showUniversalParts &&
        (filterMode === 'car_model' || filterMode === 'category_car') && {
          car_id: selectedGeneration.id,
        }),
      // Include brand_id if a brand is selected and in brand mode
      ...(selectedBrand !== null &&
        filterMode === 'brand' && { brand_id: selectedBrand.id }),
      ...(searchTerm && { search: searchTerm }),
    }),
    [
      currentPage,
      itemsPerPage,
      selectedCategory,
      selectedGeneration,
      showUniversalParts,
      selectedBrand,
      filterMode,
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

  // Fetch available categories based on current filters
  const fetchAvailableCategories = useCallback(async () => {
    // Build filter params (without category_id)
    const filterParams: {
      skip?: number;
      limit?: number;
      car_id?: number;
      brand_id?: number;
      search?: string;
    } = {
      skip: 0,
      limit: 1000, // Fetch enough parts to get a good sample of categories
    };

    if (filterMode === 'car_model') {
      if (selectedGeneration && !showUniversalParts) {
        filterParams.car_id = selectedGeneration.id;
      }
    } else if (filterMode === 'brand') {
      if (selectedBrand !== null) {
        filterParams.brand_id = selectedBrand.id;
      }
    }

    // Only fetch if we have active filters
    const hasActiveFilter =
      (filterMode === 'car_model' &&
        (selectedGeneration || showUniversalParts)) ||
      (filterMode === 'brand' && selectedBrand !== null);

    if (!hasActiveFilter) {
      // If no filters, show all active categories
      setAvailableCategoryIds(new Set<number>());
      setHasCheckedForParts(false);
      setHasNoParts(false);
      return;
    }

    setHasCheckedForParts(true);
    try {
      const response =
        await globalPartsApi.getGlobalPartsWithVotes(filterParams);
      const parts = response.data.data || [];
      // Extract unique category IDs from the parts
      const categoryIds = new Set<number>(
        parts
          .map((part: GlobalPartReadWithVotes) => part.category_id)
          .filter((id): id is number => typeof id === 'number')
      );
      setAvailableCategoryIds(categoryIds);
      setHasNoParts(categoryIds.size === 0);
    } catch {
      // On error, assume no parts found
      setAvailableCategoryIds(new Set<number>());
      setHasNoParts(true);
    }
  }, [filterMode, selectedGeneration, showUniversalParts, selectedBrand]);

  // Fetch available categories when filters change
  useEffect(() => {
    void fetchAvailableCategories();
  }, [fetchAvailableCategories]);

  // Filter active categories and sort by sort_order
  // Only show categories that have parts matching current filters
  const activeCategories = useMemo(() => {
    let filtered = categories.filter((category) => category.is_active);

    // If we have available category IDs (from filtered parts), only show those
    // Only filter if we've checked and found categories (not if we haven't checked yet)
    if (hasCheckedForParts && availableCategoryIds.size > 0) {
      filtered = filtered.filter((category) =>
        availableCategoryIds.has(category.id)
      );
    } else if (hasCheckedForParts && availableCategoryIds.size === 0) {
      // If we've checked and found no categories, return empty array
      return [];
    }
    // If we haven't checked yet (no filters), show all categories

    return filtered.sort((a, b) => a.sort_order - b.sort_order);
  }, [categories, availableCategoryIds, hasCheckedForParts]);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header with My Parts button */}
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="Parts Catalog" />
        {isAuthenticated && (
          <LinkButton to="/my-global-parts" variant="outline" size="md">
            My Parts
          </LinkButton>
        )}
      </div>

      {/* Filter Mode Toggle */}
      <Card className="mb-6">
        <div className="p-3">
          <h3 className="text-lg font-semibold text-gray-200 mb-2">
            Choose Filter Method
          </h3>
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => handleFilterModeChange('category_car')}
              className={`flex-1 px-6 py-3 rounded-lg border-2 transition-all duration-200 ${
                filterMode === 'category_car'
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-indigo-500/50'
              }`}
            >
              <div className="text-2xl mb-1">📦</div>
              <div className="font-semibold">Filter by Part Category</div>
              <div className="text-sm mt-0.5 opacity-90">
                Select a category first, then choose a vehicle
              </div>
            </button>
            <button
              type="button"
              onClick={() => handleFilterModeChange('car_model')}
              className={`flex-1 px-6 py-3 rounded-lg border-2 transition-all duration-200 ${
                filterMode === 'car_model'
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-indigo-500/50'
              }`}
            >
              <div className="text-2xl mb-1">🚗</div>
              <div className="font-semibold">Filter by Car Model</div>
              <div className="text-sm mt-0.5 opacity-90">
                Browse parts by vehicle manufacturer, model, and generation
              </div>
            </button>
            <button
              type="button"
              onClick={() => handleFilterModeChange('brand')}
              className={`flex-1 px-6 py-3 rounded-lg border-2 transition-all duration-200 ${
                filterMode === 'brand'
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-indigo-500/50'
              }`}
            >
              <div className="text-2xl mb-1">🏷️</div>
              <div className="font-semibold">Filter by Part Brand</div>
              <div className="text-sm mt-0.5 opacity-90">
                Browse parts by manufacturer brand (e.g., AEM, Borla, etc.)
              </div>
            </button>
          </div>
        </div>
      </Card>

      {/* Information Panel */}
      <Card className="mb-6">
        <div className="p-3">
          <h3 className="text-lg font-semibold text-gray-200 mb-2">
            Explore Parts Catalog
          </h3>
          <div className="text-sm text-gray-400">
            {filterMode === 'car_model' ? (
              <>
                <p className="mb-1">
                  Select a manufacturer, car model, and generation to browse
                  parts for that specific vehicle, or choose "Universal Parts"
                  for parts not tied to a specific car.
                </p>
                <p>
                  After selecting a car or universal parts, you can browse parts
                  by category or search for specific parts.
                </p>
              </>
            ) : filterMode === 'brand' ? (
              <>
                <p className="mb-1">
                  Select a part brand to browse all parts from that
                  manufacturer.
                </p>
                <p>
                  After selecting a brand, you can browse parts by category or
                  search for specific parts.
                </p>
              </>
            ) : (
              <>
                <p className="mb-1">
                  First select a category to narrow down the part type, then
                  choose a vehicle manufacturer, model, and generation.
                </p>
                <p>
                  This helps you find specific parts for your vehicle in a
                  particular category.
                </p>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* Car Selection Tiles - 3 Layer Selection */}
      {filterMode === 'car_model' && (
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
                  {selectedModel
                    ? '← Back to Car Models'
                    : '← Back to Selection'}
                </button>
              ) : (
                'Select Car Manufacturer or Universal Parts'
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
                      Selected Car Manufacturer
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
      )}

      {/* Brand Selection */}
      {filterMode === 'brand' && (
        <div className="space-y-6 mb-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-200 mb-4">
              {selectedBrand ? (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedBrand(null);
                    setSelectedCategory(null);
                    setSelectedCategoryData(null);
                    setSearchTerm('');
                  }}
                  className="text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  ← Back to Brand Selection
                </button>
              ) : (
                'Select Part Brand'
              )}
            </h3>
            {!selectedBrand && (
              <>
                {loading ? (
                  <Card>
                    <div className="flex items-center justify-center py-8">
                      <LoadingSpinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                    {availableBrands.map((brand) => (
                      <Card
                        key={brand.id}
                        onClick={() => setSelectedBrand(brand)}
                        interactive
                        className="text-center p-4 cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                      >
                        <h4 className="text-lg font-semibold text-gray-200">
                          {brand.name}
                        </h4>
                        {brand.description && (
                          <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                            {brand.description}
                          </p>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* Selected Brand Info */}
            {selectedBrand && (
              <Card className="mb-4">
                <div className="flex items-center gap-6">
                  <div className="flex-1 flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-200">
                        Selected Brand: {selectedBrand.name}
                      </h3>
                      {selectedBrand.description && (
                        <p className="text-sm text-gray-400 mt-1">
                          {selectedBrand.description}
                        </p>
                      )}
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
      )}

      {/* Category & Car Selection */}
      {filterMode === 'category_car' && (
        <div className="space-y-6 mb-6">
          {/* Step 1: Category Selection */}
          {!selectedCategory && (
            <div>
              <h3 className="text-lg font-semibold text-gray-200 mb-4">
                Select Category
              </h3>
              {loading ? (
                <Card>
                  <div className="flex items-center justify-center py-8">
                    <LoadingSpinner />
                  </div>
                </Card>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {categories
                    .filter((category) => category.is_active)
                    .sort((a, b) => a.sort_order - b.sort_order)
                    .map((category: CategoryResponse) => (
                      <Card
                        key={category.id}
                        className="cursor-pointer hover:bg-gray-800 transition-colors border-2 border-gray-700 hover:border-blue-500"
                        onClick={() => handleCategorySelect(category)}
                      >
                        <div className="p-6 text-center">
                          <div className="text-4xl mb-3">
                            {category.icon || '📦'}
                          </div>
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
            </div>
          )}

          {/* Step 2: Car Selection (after category is selected) */}
          {selectedCategory && selectedCategoryData && (
            <>
              {/* Selected Category Info */}
              <Card className="mb-4 bg-indigo-900/20 border-indigo-500/50">
                <div className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">
                      {selectedCategoryData.icon || '📦'}
                    </span>
                    <div>
                      <p className="text-sm text-gray-400 mb-1">
                        Selected Category
                      </p>
                      <h3 className="text-xl font-semibold text-indigo-400">
                        {selectedCategoryData.display_name ||
                          selectedCategoryData.name}
                      </h3>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedCategory(null);
                      setSelectedCategoryData(null);
                      setSelectedMake('');
                      setSelectedModel('');
                      setSelectedGeneration(null);
                      setSearchTerm('');
                      setCurrentPage(1);
                    }}
                    className="text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    ← Change Category
                  </button>
                </div>
              </Card>

              {/* Layer 1: Make Selection */}
              <div>
                <h3 className="text-lg font-semibold text-gray-200 mb-4">
                  {selectedMake ? (
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedModel) {
                          setSelectedModel('');
                          setSelectedGeneration(null);
                          setSelectedCategory(null);
                          setSelectedCategoryData(null);
                        } else {
                          setSelectedMake('');
                          setSelectedModel('');
                          setSelectedGeneration(null);
                          setSelectedCategory(null);
                          setSelectedCategoryData(null);
                        }
                      }}
                      className="text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      {selectedModel
                        ? '← Back to Car Models'
                        : '← Back to Selection'}
                    </button>
                  ) : (
                    'Select Car Manufacturer'
                  )}
                </h3>
                {!selectedMake && (
                  <>
                    {isLoadingMakes ? (
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
                    ) : (
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
                    )}
                  </>
                )}

                {/* Layer 2: Model Selection */}
                {selectedMake && !selectedModel && (
                  <>
                    <Card className="mb-4 bg-indigo-900/20 border-indigo-500/50">
                      <div className="p-4">
                        <p className="text-sm text-gray-400 mb-1">
                          Selected Car Manufacturer
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
                {selectedMake && selectedModel && !selectedGeneration && (
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
            </>
          )}
        </div>
      )}

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

      {/* Category View - Only show after car, universal parts, or brand is selected (not for category_car mode) */}
      {((filterMode === 'car_model' &&
        (selectedGeneration || showUniversalParts)) ||
        (filterMode === 'brand' && selectedBrand !== null)) &&
        !selectedCategory && (
          <>
            <div className="mb-6">
              <SectionHeader title="Browse by Category" />
              <p className="text-gray-400 text-sm mt-2">
                Select a category to browse parts for this vehicle, or use
                search to find specific parts.
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

            {/* Show callout if no parts found */}
            {hasCheckedForParts && hasNoParts && !searchTerm && (
              <Card className="mb-6 bg-yellow-900/20 border-yellow-500/50">
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">⚠️</span>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-yellow-400 mb-2">
                        No Parts Found
                      </h3>
                      <p className="text-sm text-gray-300">
                        {filterMode === 'brand' && selectedBrand ? (
                          <>
                            There are currently no parts available for{' '}
                            <span className="font-semibold text-yellow-300">
                              {selectedBrand.name}
                            </span>
                            . Try selecting a different brand or use the search
                            to find parts.
                          </>
                        ) : filterMode === 'car_model' && selectedGeneration ? (
                          <>
                            There are currently no parts available for{' '}
                            <span className="font-semibold text-yellow-300">
                              {selectedGeneration.make}{' '}
                              {selectedGeneration.model}{' '}
                              {selectedGeneration.generation_name}
                            </span>
                            . Try selecting a different vehicle or use the
                            search to find parts.
                          </>
                        ) : (
                          <>
                            There are currently no parts available for the
                            selected filters. Try adjusting your selection or
                            use the search to find parts.
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              </Card>
            )}

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
            ) : hasNoParts ? null : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {activeCategories.map((category: CategoryResponse) => (
                  <Card
                    key={category.id}
                    className="cursor-pointer hover:bg-gray-800 transition-colors border-2 border-gray-700 hover:border-blue-500"
                    onClick={() => handleCategorySelect(category)}
                  >
                    <div className="p-6 text-center">
                      <div className="text-4xl mb-3">
                        {category.icon || '📦'}
                      </div>
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

      {/* Category & Car Parts View (for category_car mode) */}
      {filterMode === 'category_car' &&
        selectedCategory &&
        selectedCategoryData &&
        selectedGeneration && (
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
                <p className="text-gray-400 text-sm">
                  {selectedCategoryData.description}
                </p>
                <p className="text-gray-400 text-sm mt-1">
                  For: {selectedGeneration.make} {selectedGeneration.model}{' '}
                  {selectedGeneration.generation_name}
                </p>
              </div>
              <SecondaryButton onClick={clearFilters}>
                Change Selection
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
              emptyMessage="No parts found in this category for this vehicle. Try adjusting your search."
              showVoteButtons={true}
              onVoteUpdate={handleVoteUpdate}
              showAddToBuildListButton={true}
              onAddToBuildList={handleAddToBuildList}
              onPaginationChange={handlePaginationChange}
            />
          </>
        )}

      {/* Category Parts View */}
      {selectedCategory &&
        selectedCategoryData &&
        filterMode !== 'category_car' && (
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
        (((selectedGeneration || showUniversalParts) &&
          filterMode === 'car_model') ||
          (selectedBrand !== null && filterMode === 'brand') ||
          (selectedCategory &&
            selectedGeneration &&
            filterMode === 'category_car')) &&
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
