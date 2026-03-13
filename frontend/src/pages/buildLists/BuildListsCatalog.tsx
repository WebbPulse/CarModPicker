import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import BuildListCard from '../../components/buildLists/BuildListCard';
import BuildListCatalogList from '../../components/buildLists/BuildListCatalogList';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import VehicleFilterChips, {
  filterChipClass,
} from '../../components/common/VehicleFilterChips';
import VehicleFilterSection from '../../components/common/VehicleFilterSection';
import PageHeader from '../../components/layout/PageHeader';
import {
  BUILD_LISTS_ALL_PAGE_SIZE,
  BUILD_LISTS_CATALOG_ITEMS_PER_PAGE,
  LARGE_FETCH_LIMIT,
} from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi, carsApi } from '../../services/Api';
import type {
  BuildListReadWithVotes,
  CarRead,
  PaginatedResponse,
} from '../../types/Api';
import { normalizeCarRead, normalizeCarReadList } from '../../utils/carUtils';

const BuildListsCatalog: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [costMin, setCostMin] = useState('');
  const [costMax, setCostMax] = useState('');
  const [sortBy, setSortBy] = useState<
    'votes' | 'votes_asc' | 'price_asc' | 'price_desc'
  >('votes');
  const [currentPage, setCurrentPage] = useState(1);
  const [isInitializedFromUrl, setIsInitializedFromUrl] = useState(false);
  const isInitializingFromUrlRef = useRef(false);
  const itemsPerPage = BUILD_LISTS_CATALOG_ITEMS_PER_PAGE;

  // Debounce search so API is called only after user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // When no vehicle selected: paginated list of all build lists (search + cost + sort via API)
  const allBuildListsParams = useMemo(() => {
    const params: {
      skip: number;
      limit: number;
      search?: string;
      min_cost_cents?: number;
      max_cost_cents?: number;
      sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
    } = {
      skip: (currentPage - 1) * BUILD_LISTS_ALL_PAGE_SIZE,
      limit: BUILD_LISTS_ALL_PAGE_SIZE,
      sort: sortBy,
    };
    if (debouncedSearchTerm.trim()) params.search = debouncedSearchTerm.trim();
    if (
      costMin.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(costMin.trim())) &&
      Number.parseFloat(costMin.trim()) >= 0
    ) {
      params.min_cost_cents = Math.round(
        Number.parseFloat(costMin.trim()) * 100
      );
    }
    if (
      costMax.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(costMax.trim())) &&
      Number.parseFloat(costMax.trim()) >= 0
    ) {
      params.max_cost_cents = Math.round(
        Number.parseFloat(costMax.trim()) * 100
      );
    }
    return params;
  }, [currentPage, debouncedSearchTerm, costMin, costMax, sortBy]);

  const fetchAllBuildListsFn = useCallback(
    (params: Parameters<typeof buildListsApi.getBuildListsWithVotes>[0]) =>
      buildListsApi.getBuildListsWithVotes(params),
    []
  );

  const {
    data: allBuildListsResponse,
    isLoading: isLoadingAllBuildLists,
    error: allBuildListsError,
    executeRequest: fetchAllBuildLists,
  } = useApiRequest<
    PaginatedResponse<BuildListReadWithVotes>,
    Parameters<typeof buildListsApi.getBuildListsWithVotes>[0]
  >(fetchAllBuildListsFn);

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

  const fetchCarByIdFn = useCallback(
    (carId: number) => carsApi.getCar(carId),
    []
  );
  const { data: carFromUrl, executeRequest: fetchCarById } =
    useApiRequest(fetchCarByIdFn);

  useEffect(() => {
    void fetchMakes();
  }, [fetchMakes]);

  // Initialize filter state from URL (deeplinking), same param names as global-parts where applicable
  const initializeFromUrl = useCallback(() => {
    if (isInitializedFromUrl || !makeStats) return;
    const hasUrlParams = Array.from(searchParams.keys()).length > 0;
    if (!hasUrlParams) {
      setIsInitializedFromUrl(true);
      return;
    }
    isInitializingFromUrlRef.current = true;
    const searchParam = searchParams.get('search');
    if (searchParam) setSearchTerm(searchParam);
    const minPriceParam = searchParams.get('min_price');
    if (minPriceParam != null && minPriceParam !== '') {
      const n = Number.parseFloat(minPriceParam);
      if (!Number.isNaN(n) && n >= 0) setCostMin(minPriceParam);
    }
    const maxPriceParam = searchParams.get('max_price');
    if (maxPriceParam != null && maxPriceParam !== '') {
      const n = Number.parseFloat(maxPriceParam);
      if (!Number.isNaN(n) && n >= 0) setCostMax(maxPriceParam);
    }
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const page = Number.parseInt(pageParam, 10);
      if (!Number.isNaN(page) && page > 0) setCurrentPage(page);
    }
    const sortParam = searchParams.get('sort');
    if (
      sortParam === 'votes' ||
      sortParam === 'votes_asc' ||
      sortParam === 'price_asc' ||
      sortParam === 'price_desc'
    ) {
      setSortBy(sortParam);
    }
    const carIdParam = searchParams.get('car_id');
    if (carIdParam) {
      const id = Number.parseInt(carIdParam, 10);
      if (!Number.isNaN(id)) {
        void fetchCarById(id);
        return;
      }
    }
    // Leave isInitializingFromUrlRef true so reset-page effect skips; cleared in useEffect after tick
    setIsInitializedFromUrl(true);
  }, [searchParams, makeStats, isInitializedFromUrl, fetchCarById]);

  useEffect(() => {
    initializeFromUrl();
  }, [initializeFromUrl]);

  useEffect(() => {
    if (carFromUrl && isInitializingFromUrlRef.current) {
      const car = normalizeCarRead(carFromUrl);
      if (car) {
        setSelectedMake(car.make);
        setSelectedModel(car.model);
        setSelectedGeneration(car);
        void fetchCarsByMake(car.make);
      }
      isInitializingFromUrlRef.current = false;
      setIsInitializedFromUrl(true);
    }
  }, [carFromUrl, fetchCarsByMake]);

  // Sync filter state to URL when filters change (after initial load from URL)
  const syncFiltersToUrl = useCallback(() => {
    if (!isInitializedFromUrl) return;
    const newParams = new URLSearchParams();
    if (searchTerm) newParams.set('search', searchTerm);
    if (costMin.trim() !== '') {
      const n = Number.parseFloat(costMin.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('min_price', costMin.trim());
    }
    if (costMax.trim() !== '') {
      const n = Number.parseFloat(costMax.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('max_price', costMax.trim());
    }
    if (selectedGeneration)
      newParams.set('car_id', selectedGeneration.id.toString());
    if (sortBy !== 'votes') newParams.set('sort', sortBy);
    if (currentPage > 1) newParams.set('page', currentPage.toString());
    setSearchParams(newParams, { replace: true });
  }, [
    isInitializedFromUrl,
    searchTerm,
    costMin,
    costMax,
    selectedGeneration,
    sortBy,
    currentPage,
    setSearchParams,
  ]);

  useEffect(() => {
    if (isInitializedFromUrl) syncFiltersToUrl();
  }, [
    isInitializedFromUrl,
    searchTerm,
    costMin,
    costMax,
    selectedGeneration,
    sortBy,
    currentPage,
    syncFiltersToUrl,
  ]);

  // Debounce search in URL to avoid rapid updates while typing
  useEffect(() => {
    if (!isInitializedFromUrl) return;
    const t = setTimeout(syncFiltersToUrl, 500);
    return () => clearTimeout(t);
  }, [isInitializedFromUrl, searchTerm, syncFiltersToUrl]);

  // Clear "initializing" ref after first sync so page reset on filter change works
  useEffect(() => {
    if (!isInitializedFromUrl) return;
    const id = setTimeout(() => {
      isInitializingFromUrlRef.current = false;
    }, 0);
    return () => clearTimeout(id);
  }, [isInitializedFromUrl]);

  useEffect(() => {
    if (makeStats) {
      setAvailableMakes(Object.keys(makeStats).sort());
    }
  }, [makeStats]);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      // Only clear model/generation when user changed make; skip when restoring from URL
      if (
        !selectedGeneration ||
        (selectedGeneration.make ?? '') !== selectedMake
      ) {
        setSelectedModel('');
        setSelectedGeneration(null);
      }
    } else {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, selectedGeneration, fetchCarsByMake]);

  useEffect(() => {
    setAvailableCars(normalizeCarReadList(carsByMake ?? undefined));
  }, [carsByMake]);

  useEffect(() => {
    if (selectedModel) {
      // Only clear generation when user changed model; skip when restoring from URL
      if (!selectedGeneration || selectedGeneration.model !== selectedModel) {
        setSelectedGeneration(null);
      }
    }
  }, [selectedModel, selectedGeneration]);

  // Reset to page 1 when filters or sort change (skip during URL init so deeplink page is preserved)
  useEffect(() => {
    if (isInitializingFromUrlRef.current) return;
    setCurrentPage(1);
  }, [
    debouncedSearchTerm,
    selectedMake,
    selectedModel,
    costMin,
    costMax,
    sortBy,
  ]);

  const clearAllFilters = () => {
    setSearchTerm('');
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
    setCostMin('');
    setCostMax('');
  };

  const clearCostRange = () => {
    setCostMin('');
    setCostMax('');
  };

  const clearVehicleFilter = () => {
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  };

  const hasCostRange =
    (costMin.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(costMin.trim())) &&
      Number.parseFloat(costMin.trim()) >= 0) ||
    (costMax.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(costMax.trim())) &&
      Number.parseFloat(costMax.trim()) >= 0);

  const hasActiveFilters =
    selectedMake !== '' || searchTerm.trim() !== '' || hasCostRange;

  const uniqueModels = Array.from(
    new Set(availableCars.map((car) => car.model ?? '').filter(Boolean))
  ).sort();

  const generations = availableCars
    .filter(
      (car) =>
        (car.make ?? '') === selectedMake && (car.model ?? '') === selectedModel
    )
    .sort((a, b) => {
      if (a.start_year !== b.start_year) return a.start_year - b.start_year;
      return (a.generation_name ?? '').localeCompare(b.generation_name ?? '');
    });

  /** Car IDs for API filter: single generation, or all for make, or all for make+model */
  const effectiveCarIds = useMemo(
    () =>
      selectedGeneration
        ? [selectedGeneration.id]
        : selectedModel
          ? generations.map((c) => c.id)
          : selectedMake
            ? availableCars.map((c) => c.id)
            : [],
    [
      selectedGeneration,
      selectedModel,
      selectedMake,
      generations,
      availableCars,
    ]
  );

  const hasVehicleFilter = selectedMake !== '';

  /** Memoized params for BuildListCatalogList so the reference is stable and we don't refetch on every render */
  const buildListCatalogListParams = useMemo(
    () => ({
      skip: (currentPage - 1) * itemsPerPage,
      limit: itemsPerPage,
      sort: sortBy,
      ...(debouncedSearchTerm.trim() && {
        search: debouncedSearchTerm.trim(),
      }),
      ...(costMin.trim() !== '' &&
        !Number.isNaN(Number.parseFloat(costMin.trim())) &&
        Number.parseFloat(costMin.trim()) >= 0 && {
          min_cost_cents: Math.round(Number.parseFloat(costMin.trim()) * 100),
        }),
      ...(costMax.trim() !== '' &&
        !Number.isNaN(Number.parseFloat(costMax.trim())) &&
        Number.parseFloat(costMax.trim()) >= 0 && {
          max_cost_cents: Math.round(Number.parseFloat(costMax.trim()) * 100),
        }),
    }),
    [currentPage, itemsPerPage, sortBy, debouncedSearchTerm, costMin, costMax]
  );

  // Fetch all build lists (paginated) when no vehicle filter is selected
  useEffect(() => {
    if (!hasVehicleFilter) {
      void fetchAllBuildLists(allBuildListsParams);
    }
  }, [hasVehicleFilter, fetchAllBuildLists, allBuildListsParams]);

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

              {/* Total cost range filter */}
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider pb-2 mb-3 border-b border-gray-700/60">
                  Total Cost ($)
                </h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor="cost-min"
                      className="text-sm text-gray-500 shrink-0 w-12"
                    >
                      Min ($)
                    </label>
                    <input
                      id="cost-min"
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="No min"
                      value={costMin}
                      onChange={(e) => setCostMin(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500/50 transition-colors"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor="cost-max"
                      className="text-sm text-gray-500 shrink-0 w-12"
                    >
                      Max ($)
                    </label>
                    <input
                      id="cost-max"
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="No max"
                      value={costMax}
                      onChange={(e) => setCostMax(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500/50 transition-colors"
                    />
                  </div>
                </div>
              </div>

              {/* Sort by */}
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider pb-2 mb-3 border-b border-gray-700/60">
                  Sort by
                </h3>
                <select
                  id="build-lists-sort"
                  value={sortBy}
                  onChange={(e) =>
                    setSortBy(
                      e.target.value as
                        | 'votes'
                        | 'votes_asc'
                        | 'price_asc'
                        | 'price_desc'
                    )
                  }
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500/50 transition-colors"
                >
                  <option value="votes">Most votes</option>
                  <option value="votes_asc">Least votes</option>
                  <option value="price_asc">Price: low to high</option>
                  <option value="price_desc">Price: high to low</option>
                </select>
              </div>
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

          <div className="flex flex-wrap gap-2 mb-4">
            <VehicleFilterChips
              selectedGeneration={selectedGeneration}
              selectedMake={selectedMake}
              selectedModel={selectedModel}
              showUniversalParts={false}
              clearVehicleFilter={clearVehicleFilter}
              searchTerm={searchTerm}
              onClearSearch={() => setSearchTerm('')}
              wrapInContainer={false}
            />
            {hasCostRange && (
              <span className={filterChipClass}>
                {costMin.trim() && costMax.trim()
                  ? `$${costMin.trim()} – $${costMax.trim()}`
                  : costMin.trim()
                    ? `Min $${costMin.trim()}`
                    : `Max $${costMax.trim()}`}
                <button
                  type="button"
                  onClick={clearCostRange}
                  className="p-0.5 rounded-full hover:bg-gray-600/80 hover:text-white transition-colors shrink-0"
                  aria-label="Clear cost range"
                >
                  ×
                </button>
              </span>
            )}
          </div>

          {hasVehicleFilter && effectiveCarIds.length > 0 ? (
            <BuildListCatalogList
              carIds={effectiveCarIds}
              params={buildListCatalogListParams}
              title={
                selectedGeneration
                  ? `${selectedGeneration.make} ${selectedGeneration.model} ${selectedGeneration.generation_name} Build Lists`
                  : selectedModel
                    ? `${selectedMake} ${selectedModel} Build Lists`
                    : `${selectedMake} Build Lists`
              }
              emptyMessage="No build lists found for this car. Try adjusting your search or select a different vehicle."
              showVoteButtons={false}
              layout="card"
            />
          ) : (
            <>
              <Card>
                <div className="p-4">
                  <h3 className="text-lg font-semibold text-gray-200 mb-2">
                    All Build Lists
                  </h3>
                  <p className="text-sm text-gray-400 mb-4">
                    Select a vehicle in the sidebar to filter by car, or browse
                    all build lists below. Search and cost filters apply.
                  </p>
                  {isLoadingAllBuildLists ? (
                    <div className="flex justify-center py-12">
                      <LoadingSpinner />
                    </div>
                  ) : allBuildListsError ? (
                    <ErrorAlert
                      message={`Failed to load build lists: ${allBuildListsError}`}
                    />
                  ) : allBuildListsResponse?.data &&
                    allBuildListsResponse.data.length > 0 ? (
                    <div className="tile-grid">
                      {allBuildListsResponse.data.map((buildList) => (
                        <BuildListCard
                          key={buildList.id}
                          buildList={buildList}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-400 text-center py-8">
                      No build lists found. Try adjusting your search or cost
                      filters.
                    </p>
                  )}
                </div>
              </Card>
              {allBuildListsResponse?.pagination &&
                allBuildListsResponse.pagination.total_pages > 1 && (
                  <div className="mt-6">
                    <Pagination
                      currentPage={
                        allBuildListsResponse.pagination.current_page
                      }
                      totalPages={allBuildListsResponse.pagination.total_pages}
                      totalItems={allBuildListsResponse.pagination.total_items}
                      itemsPerPage={
                        allBuildListsResponse.pagination.items_per_page
                      }
                      onPageChange={setCurrentPage}
                    />
                  </div>
                )}
            </>
          )}
        </main>
      </div>
    </div>
  );
};

export default BuildListsCatalog;
