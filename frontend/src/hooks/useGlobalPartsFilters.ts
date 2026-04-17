import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LARGE_FETCH_LIMIT } from '../constants';
import {
  brandsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
} from '../services/Api';
import type {
  BrandResponse,
  CarRead,
  CategoryResponse,
  PaginationInfo,
} from '../types/Api';
import { normalizeCarRead, normalizeCarReadList } from '../utils/carUtils';
import useApiRequest from './UseApiRequest';

const PARTS_PER_PAGE = 100;

export interface UseGlobalPartsFiltersOptions {
  /** When set, list and filter-options are scoped to this user (e.g. My Parts). */
  user_id?: string;
  /** When true, filter state is synced to URL and initialized from URL. */
  syncToUrl?: boolean;
}

export interface UseGlobalPartsFiltersReturn {
  // List API params (include sort so server sorts full result set; pagination then returns correct page)
  params: {
    skip: number;
    limit: number;
    category_ids?: string[];
    car_id?: string;
    brand_ids?: string[];
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    user_id?: string;
    universal?: boolean;
  };
  currentPage: number;
  setCurrentPage: (page: number) => void;
  paginationInfo: PaginationInfo | null;
  setPaginationInfo: (info: PaginationInfo | null) => void;

  // Filter state
  selectedCategoryIds: string[];
  setSelectedCategoryIds: (ids: string[]) => void;
  selectedBrandIds: string[];
  setSelectedBrandIds: (ids: string[]) => void;
  selectedMake: string;
  selectedModel: string;
  selectedGeneration: CarRead | null;
  setSelectedGeneration: (car: CarRead | null) => void;
  showUniversalParts: boolean;
  setShowUniversalParts: (v: boolean) => void;
  setSelectedMake: (make: string) => void;
  setSelectedModel: (model: string) => void;
  searchTerm: string;
  setSearchTerm: (s: string) => void;
  priceMin: string;
  priceMax: string;
  setPriceMin: (s: string) => void;
  setPriceMax: (s: string) => void;

  // Sort (server-side; included in params and URL so page 2+ respects sort)
  sortParam: string;
  setSortParam: (s?: string) => void;

  // Data
  categories: CategoryResponse[];
  availableMakes: string[];
  availableCars: CarRead[];
  availableBrands: BrandResponse[];
  activeCategories: CategoryResponse[];
  uniqueModels: string[];
  generations: CarRead[];
  filterOptions: {
    category_ids: string[];
    brand_ids: string[];
    car_ids?: string[];
    make_names?: string[];
  } | null;

  // Derived
  availableCategoryIds: string[];
  availableBrandIds: string[];
  hasPriceRange: boolean;
  hasActiveFilters: boolean;
  clearAllFilters: () => void;
  clearVehicleFilter: () => void;
  clearPriceRange: () => void;
  toggleCategory: (id: string) => void;
  toggleBrand: (id: string) => void;

  // Loading
  isLoadingMakes: boolean;
  isLoadingCars: boolean;

  // URL (only meaningful when syncToUrl is true)
  isInitializedFromUrl: boolean;
}

export function useGlobalPartsFilters(
  options: UseGlobalPartsFiltersOptions = {}
): UseGlobalPartsFiltersReturn {
  const { user_id: userId, syncToUrl = false } = options;
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [showUniversalParts, setShowUniversalParts] = useState(false);
  const [selectedBrandIds, setSelectedBrandIds] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [priceMin, setPriceMin] = useState<string>('');
  const [priceMax, setPriceMax] = useState<string>('');
  const [sortParam, setSortParamState] = useState<string>('votes_desc');
  const [filterOptions, setFilterOptions] = useState<{
    category_ids: string[];
    brand_ids: string[];
    car_ids?: string[];
    make_names?: string[];
  } | null>(null);

  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [availableBrands, setAvailableBrands] = useState<BrandResponse[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo | null>(
    null
  );
  const [isInitializedFromUrl, setIsInitializedFromUrl] = useState(false);
  const isInitializingFromUrlRef = useRef(false);

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
    (carId: string) => carsApi.getCar(carId),
    []
  );
  const { data: carFromUrl, executeRequest: fetchCarById } =
    useApiRequest(fetchCarByIdFn);

  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch {
      // ignore
    }
  }, []);

  const loadBrands = useCallback(async () => {
    try {
      const response = await brandsApi.getBrands(true);
      setAvailableBrands(response.data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    void fetchMakes();
    void loadCategories();
    void loadBrands();
  }, [fetchMakes, loadCategories, loadBrands]);

  // When brand/category/search filters are applied, filter-options returns make_names;
  // otherwise use all makes from makeStats.
  useEffect(() => {
    if (filterOptions?.make_names?.length) {
      setAvailableMakes([...filterOptions.make_names].sort());
    } else if (makeStats) {
      setAvailableMakes(Object.keys(makeStats).sort());
    }
  }, [makeStats, filterOptions?.make_names]);

  // When vehicle options are scoped by filters, clear vehicle selection if selected make is no longer valid
  useEffect(() => {
    if (
      filterOptions?.make_names?.length &&
      selectedMake &&
      !filterOptions.make_names.includes(selectedMake)
    ) {
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [filterOptions?.make_names, selectedMake]);

  // Restrict to car_ids from filter-options when brand/category/search filters are applied
  useEffect(() => {
    const list = normalizeCarReadList(carsByMake ?? undefined);
    if (filterOptions?.car_ids?.length) {
      const allowed = new Set(filterOptions.car_ids);
      setAvailableCars(list.filter((c) => c.id != null && allowed.has(c.id)));
    } else {
      setAvailableCars(list);
    }
  }, [carsByMake, filterOptions?.car_ids]);

  const generations = useMemo(
    () =>
      availableCars
        .filter(
          (c) =>
            (c.make ?? '') === selectedMake && (c.model ?? '') === selectedModel
        )
        .sort((a, b) => {
          if (a.start_year !== b.start_year) return a.start_year - b.start_year;
          return (a.generation_name ?? '').localeCompare(
            b.generation_name ?? ''
          );
        }),
    [availableCars, selectedMake, selectedModel]
  );

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

  // Stable key so we only fetch filter-options when the logical request changes (avoids duplicate fetches from re-renders)
  const filterOptionsRequestKey = `${selectedCategoryIds.join(',')}-${selectedBrandIds.join(',')}-${showUniversalParts}-${effectiveCarIds.join(',')}-${searchTerm}-${userId ?? ''}`;

  useEffect(() => {
    let cancelled = false;
    const filterOptionsParams: Parameters<
      typeof globalPartsApi.getFilterOptions
    >[0] = {};
    if (selectedCategoryIds.length > 0)
      filterOptionsParams.category_ids = selectedCategoryIds;
    if (selectedBrandIds.length > 0)
      filterOptionsParams.brand_ids = selectedBrandIds;
    if (effectiveCarIds.length && !showUniversalParts)
      filterOptionsParams.car_ids = effectiveCarIds;
    if (showUniversalParts) filterOptionsParams.universal = true;
    if (searchTerm.trim()) filterOptionsParams.search = searchTerm;
    if (userId !== undefined) filterOptionsParams.user_id = userId;
    void globalPartsApi
      .getFilterOptions(filterOptionsParams)
      .then((res) => {
        if (!cancelled) setFilterOptions(res.data);
      })
      .catch(() => {
        if (!cancelled) setFilterOptions(null);
      });
    return () => {
      cancelled = true;
    };
  }, [filterOptionsRequestKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only refetch when request key changes

  const initializeFromUrl = useCallback(() => {
    if (
      !syncToUrl ||
      isInitializedFromUrl ||
      !makeStats ||
      !categories.length ||
      !availableBrands.length
    ) {
      return;
    }
    const hasUrlParams = Array.from(searchParams.keys()).length > 0;
    if (!hasUrlParams) {
      setIsInitializedFromUrl(true);
      return;
    }
    const categoryIdParams = searchParams.getAll('category_ids');
    const categoryIdsRaw =
      categoryIdParams.length > 0
        ? categoryIdParams
        : searchParams.get('category_id')
          ? [searchParams.get('category_id') as string]
          : [];
    if (categoryIdsRaw.length > 0) {
      const valid = categoryIdsRaw.filter((id) =>
        categories.some((c) => c.id === id)
      );
      if (valid.length > 0) setSelectedCategoryIds(valid);
    }
    const brandIdParams = searchParams.getAll('brand_ids');
    const brandIdsRaw =
      brandIdParams.length > 0
        ? brandIdParams
        : searchParams.get('brand_id')
          ? [searchParams.get('brand_id') as string]
          : [];
    if (brandIdsRaw.length > 0) {
      const valid = brandIdsRaw.filter((id) =>
        availableBrands.some((b) => b.id === id)
      );
      if (valid.length > 0) setSelectedBrandIds(valid);
    }
    const carIdParam = searchParams.get('car_id');
    if (carIdParam) {
      isInitializingFromUrlRef.current = true;
      void fetchCarById(carIdParam);
      return;
    }
    if (searchParams.get('universal') === 'true') setShowUniversalParts(true);
    const makeParam = searchParams.get('make');
    const modelParam = searchParams.get('model');
    if (makeParam && availableMakes.includes(makeParam)) {
      setSelectedMake(makeParam);
      if (modelParam) {
        isInitializingFromUrlRef.current = true;
        void fetchCarsByMake(makeParam);
      }
    }
    const searchParam = searchParams.get('search');
    if (searchParam) setSearchTerm(searchParam);
    const minPriceParam = searchParams.get('min_price');
    if (minPriceParam !== null && minPriceParam !== '') {
      const n = Number.parseFloat(minPriceParam);
      if (!Number.isNaN(n) && n >= 0) setPriceMin(minPriceParam);
    }
    const maxPriceParam = searchParams.get('max_price');
    if (maxPriceParam !== null && maxPriceParam !== '') {
      const n = Number.parseFloat(maxPriceParam);
      if (!Number.isNaN(n) && n >= 0) setPriceMax(maxPriceParam);
    }
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const page = Number.parseInt(pageParam, 10);
      if (!Number.isNaN(page) && page > 0) setCurrentPage(page);
    }
    const sortParamFromUrl = searchParams.get('sort');
    if (sortParamFromUrl) setSortParamState(sortParamFromUrl);
    setIsInitializedFromUrl(true);
  }, [
    syncToUrl,
    searchParams,
    makeStats,
    categories,
    availableBrands,
    availableMakes,
    isInitializedFromUrl,
    fetchCarById,
    fetchCarsByMake,
  ]);

  useEffect(() => {
    if (syncToUrl) void initializeFromUrl();
  }, [syncToUrl, initializeFromUrl]);

  useEffect(() => {
    if (carFromUrl && isInitializingFromUrlRef.current) {
      const car = normalizeCarRead(carFromUrl);
      if (car) {
        setSelectedMake(car.make);
        setSelectedModel(car.model);
        setSelectedGeneration(car);
        setShowUniversalParts(false);
        void fetchCarsByMake(car.make);
      }
      isInitializingFromUrlRef.current = false;
      setIsInitializedFromUrl(true);
    }
  }, [carFromUrl, fetchCarsByMake]);

  useEffect(() => {
    if (
      syncToUrl &&
      selectedMake &&
      carsByMake?.length &&
      searchParams.get('model') &&
      !selectedGeneration
    ) {
      const carIdParam = searchParams.get('car_id');
      if (carIdParam) {
        const car = normalizeCarRead(
          carsByMake.find((c) => c.id === carIdParam) ?? null
        );
        if (car) setSelectedGeneration(car);
      } else {
        setSelectedModel(searchParams.get('model') ?? '');
      }
      setIsInitializedFromUrl(true);
    }
  }, [syncToUrl, selectedMake, carsByMake, searchParams, selectedGeneration]);

  useEffect(() => {
    if (selectedMake && !isInitializingFromUrlRef.current) {
      void fetchCarsByMake(selectedMake);
      // Only clear model/generation when user changed make; preserve when restoring from URL (car_id)
      if (
        !selectedGeneration ||
        (selectedGeneration.make ?? '') !== selectedMake
      ) {
        setSelectedModel('');
        setSelectedGeneration(null);
      }
    } else if (!showUniversalParts && !selectedMake) {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, selectedGeneration, fetchCarsByMake, showUniversalParts]);

  const syncFiltersToUrl = useCallback(() => {
    if (!syncToUrl || !isInitializedFromUrl) return;
    const newParams = new URLSearchParams();
    selectedCategoryIds.forEach((id) =>
      newParams.append('category_ids', id.toString())
    );
    selectedBrandIds.forEach((id) =>
      newParams.append('brand_ids', id.toString())
    );
    if (showUniversalParts) newParams.set('universal', 'true');
    else if (selectedGeneration)
      newParams.set('car_id', selectedGeneration.id.toString());
    else if (selectedMake) {
      newParams.set('make', selectedMake);
      if (selectedModel) newParams.set('model', selectedModel);
    }
    if (searchTerm) newParams.set('search', searchTerm);
    if (priceMin.trim() !== '') {
      const n = Number.parseFloat(priceMin.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('min_price', priceMin.trim());
    }
    if (priceMax.trim() !== '') {
      const n = Number.parseFloat(priceMax.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('max_price', priceMax.trim());
    }
    if (currentPage > 1) newParams.set('page', currentPage.toString());
    if (sortParam && sortParam !== 'votes_desc')
      newParams.set('sort', sortParam);
    const next = newParams.toString();
    if (searchParams.toString() === next) return;
    setSearchParams(newParams, { replace: true });
  }, [
    syncToUrl,
    isInitializedFromUrl,
    selectedCategoryIds,
    selectedBrandIds,
    showUniversalParts,
    selectedGeneration,
    selectedMake,
    selectedModel,
    searchTerm,
    priceMin,
    priceMax,
    currentPage,
    sortParam,
    searchParams,
    setSearchParams,
  ]);

  useEffect(() => {
    if (syncToUrl && isInitializedFromUrl) syncFiltersToUrl();
  }, [
    syncToUrl,
    isInitializedFromUrl,
    selectedCategoryIds,
    selectedBrandIds,
    showUniversalParts,
    selectedGeneration,
    selectedMake,
    selectedModel,
    searchTerm,
    priceMin,
    priceMax,
    currentPage,
    sortParam,
    syncFiltersToUrl,
  ]);

  useEffect(() => {
    if (!syncToUrl || !isInitializedFromUrl) return;
    const t = setTimeout(syncFiltersToUrl, 500);
    return () => clearTimeout(t);
  }, [syncToUrl, searchTerm, syncFiltersToUrl, isInitializedFromUrl]);

  useEffect(() => {
    setCurrentPage(1);
  }, [
    selectedCategoryIds,
    effectiveCarIds,
    showUniversalParts,
    selectedBrandIds,
    searchTerm,
    priceMin,
    priceMax,
    sortParam,
  ]);

  const uniqueModels = useMemo(
    () =>
      Array.from(
        new Set(availableCars.map((c) => c.model ?? '').filter(Boolean))
      ).sort(),
    [availableCars]
  );

  const activeCategories = useMemo(
    () =>
      categories
        .filter((c) => c.is_active)
        .sort((a, b) => a.sort_order - b.sort_order),
    [categories]
  );

  const availableCategoryIds = useMemo(
    () => filterOptions?.category_ids ?? activeCategories.map((c) => c.id),
    [filterOptions?.category_ids, activeCategories]
  );

  const availableBrandIds = useMemo(
    () => filterOptions?.brand_ids ?? availableBrands.map((b) => b.id),
    [filterOptions?.brand_ids, availableBrands]
  );

  const hasPriceRange =
    (priceMin.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(priceMin.trim())) &&
      Number.parseFloat(priceMin.trim()) >= 0) ||
    (priceMax.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(priceMax.trim())) &&
      Number.parseFloat(priceMax.trim()) >= 0);

  const hasActiveFilters =
    selectedCategoryIds.length > 0 ||
    selectedBrandIds.length > 0 ||
    effectiveCarIds.length > 0 ||
    showUniversalParts ||
    hasPriceRange;

  const toggleCategory = useCallback((categoryId: string) => {
    setSelectedCategoryIds((prev) =>
      prev.includes(categoryId)
        ? prev.filter((id) => id !== categoryId)
        : [...prev, categoryId]
    );
  }, []);

  const toggleBrand = useCallback((brandId: string) => {
    setSelectedBrandIds((prev) =>
      prev.includes(brandId)
        ? prev.filter((id) => id !== brandId)
        : [...prev, brandId]
    );
  }, []);

  const clearAllFilters = useCallback(() => {
    setSelectedCategoryIds([]);
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
    setShowUniversalParts(false);
    setSelectedBrandIds([]);
    setSearchTerm('');
    setPriceMin('');
    setPriceMax('');
    setCurrentPage(1);
  }, []);

  const clearVehicleFilter = useCallback(() => {
    setShowUniversalParts(false);
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  }, []);

  const clearPriceRange = useCallback(() => {
    setPriceMin('');
    setPriceMax('');
  }, []);

  const setSortParam = useCallback((s?: string) => {
    if (s !== undefined) {
      setSortParamState(s);
      setCurrentPage(1);
    }
  }, []);

  const params = useMemo(() => {
    const minCents =
      priceMin.trim() !== ''
        ? Math.round(Number.parseFloat(priceMin.trim()) * 100)
        : undefined;
    const maxCents =
      priceMax.trim() !== ''
        ? Math.round(Number.parseFloat(priceMax.trim()) * 100)
        : undefined;
    const min_price_cents =
      minCents !== undefined && !Number.isNaN(minCents) && minCents >= 0
        ? minCents
        : undefined;
    const max_price_cents =
      maxCents !== undefined && !Number.isNaN(maxCents) && maxCents >= 0
        ? maxCents
        : undefined;
    return {
      skip: (currentPage - 1) * PARTS_PER_PAGE,
      limit: PARTS_PER_PAGE,
      ...(userId !== undefined && { user_id: userId }),
      ...(selectedCategoryIds.length > 0 && {
        category_ids: selectedCategoryIds,
      }),
      ...(effectiveCarIds.length &&
        !showUniversalParts && { car_ids: effectiveCarIds }),
      ...(showUniversalParts && { universal: true }),
      ...(selectedBrandIds.length > 0 && { brand_ids: selectedBrandIds }),
      ...(searchTerm && { search: searchTerm }),
      ...(sortParam && { sort: sortParam }),
      ...(min_price_cents !== undefined && { min_price_cents }),
      ...(max_price_cents !== undefined && { max_price_cents }),
    };
  }, [
    currentPage,
    userId,
    selectedCategoryIds,
    effectiveCarIds,
    showUniversalParts,
    selectedBrandIds,
    searchTerm,
    sortParam,
    priceMin,
    priceMax,
  ]);

  return {
    params,
    currentPage,
    setCurrentPage,
    paginationInfo,
    setPaginationInfo,
    selectedCategoryIds,
    setSelectedCategoryIds,
    selectedBrandIds,
    setSelectedBrandIds,
    selectedMake,
    selectedModel,
    selectedGeneration,
    setSelectedGeneration,
    showUniversalParts,
    setShowUniversalParts,
    setSelectedMake,
    setSelectedModel,
    searchTerm,
    setSearchTerm,
    priceMin,
    priceMax,
    setPriceMin,
    setPriceMax,
    sortParam,
    setSortParam,
    categories,
    availableMakes,
    availableCars,
    availableBrands,
    activeCategories,
    uniqueModels,
    generations,
    filterOptions,
    availableCategoryIds,
    availableBrandIds,
    hasPriceRange,
    hasActiveFilters,
    clearAllFilters,
    clearVehicleFilter,
    clearPriceRange,
    toggleCategory,
    toggleBrand,
    isLoadingMakes,
    isLoadingCars,
    isInitializedFromUrl,
  };
}

export const GLOBAL_PARTS_PARTS_PER_PAGE = PARTS_PER_PAGE;
