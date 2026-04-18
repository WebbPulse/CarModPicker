import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import {
  brandsApi,
  buildListPartsApi,
  buildListsApi,
  carsApi,
  categoriesApi,
  partsApi,
} from '../../services/Api';
import type {
  BrandCreate,
  BrandResponse,
  BuildListPartCreate,
  BuildListPhaseRead,
  CarRead,
  CategoryResponse,
  PartCreate,
} from '../../types/Api';

import { LARGE_FETCH_LIMIT } from '../../constants';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import CarModelMultiSelect from '../common/CarModelMultiSelect';
import ImageUpload from '../common/ImageUpload';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../common/SearchableSelect';

interface CreateBuildListPartFormProps {
  buildListId: string;
  onPartAdded: () => void;
  onCancel: () => void;
}

const fetchPartsRequestFn = () => partsApi.getParts();
const fetchCarsRequestFn = () => carsApi.listCars({ limit: LARGE_FETCH_LIMIT });
const fetchPhasesRequestFn = (buildListId: string) =>
  buildListsApi.getPhases(buildListId);

function CreateBuildListPartForm({
  buildListId,
  onPartAdded,
  onCancel,
}: CreateBuildListPartFormProps) {
  const [mode, setMode] = useState<'create' | 'select'>('select');
  const [selectedPartId, setSelectedPartId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand_id: null as string | null,
    description: '',
    product_url: '',
    category_id: null as string | null,
    car_ids: [] as string[],
    is_universal: false,
    notes: '',
    quantity: 1,
  });
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [duplicatePartId, setDuplicatePartId] = useState<string | null>(null);
  const [isCheckingUrl, setIsCheckingUrl] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddingExisting, setIsAddingExisting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [addExistingError, setAddExistingError] = useState<string | null>(null);
  const [cars, setCars] = useState<CarRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [isLoadingBrands, setIsLoadingBrands] = useState(true);
  const [pendingBrandName, setPendingBrandName] = useState<string | null>(null);
  const urlCheckTimeoutRef = useRef<number | null>(null);

  const {
    data: parts,
    isLoading: isLoadingParts,
    error: partsError,
    executeRequest: fetchParts,
  } = useApiRequest(fetchPartsRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);
  const fetchCategoriesRequestFn = () => categoriesApi.getCategories();
  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);
  const fetchBrandsRequestFn = () => brandsApi.getBrands(true);
  const { data: brandsData, executeRequest: fetchBrands } =
    useApiRequest(fetchBrandsRequestFn);
  const { data: phasesData, executeRequest: fetchPhases } =
    useApiRequest(fetchPhasesRequestFn);

  useEffect(() => {
    void fetchParts();
    void fetchCars();
    void fetchCategories();
    void fetchBrands();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch once on mount - request functions are stable

  useEffect(() => {
    if (buildListId) void fetchPhases(buildListId);
  }, [buildListId, fetchPhases]);

  useEffect(() => {
    if (carsData && Array.isArray(carsData)) {
      setCars(carsData);
      setIsLoadingCars(false);
    }
  }, [carsData]);

  useEffect(() => {
    if (categoriesData && Array.isArray(categoriesData)) {
      setCategories(categoriesData);
      setIsLoadingCategories(false);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (brandsData && Array.isArray(brandsData)) {
      setBrands(brandsData);
      setIsLoadingBrands(false);
    }
  }, [brandsData]);

  // Debounced URL checking effect (only when in create mode)
  useEffect(() => {
    // Only check URL when in create mode
    if (mode !== 'create') {
      setDuplicatePartId(null);
      setIsCheckingUrl(false);
      return;
    }

    // Clear any existing timeout
    if (urlCheckTimeoutRef.current) {
      clearTimeout(urlCheckTimeoutRef.current);
    }

    const url = formData.product_url.trim();

    // Don't check if URL is empty
    if (!url) {
      setDuplicatePartId(null);
      setIsCheckingUrl(false);
      return;
    }

    // Basic URL validation - only check if it looks like a URL
    const urlPattern = /^https?:\/\/.+/;
    if (!urlPattern.test(url)) {
      setDuplicatePartId(null);
      setIsCheckingUrl(false);
      return;
    }

    // Set checking state
    setIsCheckingUrl(true);
    setDuplicatePartId(null);

    // Debounce the check - wait 500ms after user stops typing
    urlCheckTimeoutRef.current = window.setTimeout(async () => {
      try {
        const response = await partsApi.checkProductUrl(url);
        if (response.data.existing_part_id) {
          setDuplicatePartId(response.data.existing_part_id);
        } else {
          setDuplicatePartId(null);
        }
      } catch {
        // Silently fail - don't show error for URL checks
        setDuplicatePartId(null);
      } finally {
        setIsCheckingUrl(false);
      }
    }, 500);

    // Cleanup function
    return () => {
      if (urlCheckTimeoutRef.current) {
        clearTimeout(urlCheckTimeoutRef.current);
      }
    };
  }, [formData.product_url, mode]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
    // Don't clear duplicatePartId here - let the useEffect handle it
  };

  const handleCarIdsChange = useCallback(
    (carIds: string[]) => {
      setFormData((prev) => ({ ...prev, car_ids: carIds }));
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  const handleUniversalChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const checked = e.target.checked;
      setFormData((prev) => ({ ...prev, is_universal: checked }));
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  // Convert global parts to SearchableSelectOption format
  const partOptions: SearchableSelectOption[] = useMemo(() => {
    if (!parts) return [];
    return parts
      .sort((a, b) => {
        // Sort by name first
        return a.name.localeCompare(b.name);
      })
      .map((part) => {
        const brandName = part.brand_id
          ? brands.find((b) => b.id === part.brand_id)?.name
          : null;
        return {
          id: part.id,
          value: part.id,
          label: `${part.name}${brandName ? ` - ${brandName}` : ''}${part.best_price_cents != null ? ` - $${(part.best_price_cents / 100).toFixed(2)}` : ''}`,
        };
      });
  }, [parts, brands]);

  // Filter function for global parts
  const filterParts = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((option) => {
        const part = parts?.find((p) => p.id === option.value);
        if (!part) return false;
        const brandName = part.brand_id
          ? brands.find((b) => b.id === part.brand_id)?.name
          : null;
        return (
          part.name.toLowerCase().includes(lowerText) ||
          (brandName && brandName.toLowerCase().includes(lowerText)) ||
          (part.description &&
            part.description.toLowerCase().includes(lowerText)) ||
          (part.part_number &&
            part.part_number.toLowerCase().includes(lowerText)) ||
          option.label.toLowerCase().includes(lowerText)
        );
      });
    },
    [parts, brands]
  );

  // Convert categories to SearchableSelect options (only active categories)
  const categoryOptions: SearchableSelectOption[] = useMemo(() => {
    return categories
      .filter((category) => category.is_active)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((category) => ({
        id: category.id,
        label: category.display_name || category.name,
        value: category.id,
      }));
  }, [categories]);

  // Filter function for categories
  const filterCategories = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((opt) => {
        const category = categories.find((c) => c.id === opt.value);
        if (!category) return false;
        return (
          opt.label.toLowerCase().includes(lowerText) ||
          category.name.toLowerCase().includes(lowerText) ||
          (category.description &&
            category.description.toLowerCase().includes(lowerText))
        );
      });
    },
    [categories]
  );

  // Convert brands to SearchableSelect options
  const brandOptions: SearchableSelectOption[] = useMemo(() => {
    return brands
      .filter((brand) => brand.is_active)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((brand) => ({
        id: brand.id,
        label: brand.name,
        value: brand.id,
      }));
  }, [brands]);

  // Filter function for brands
  const filterBrands = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((opt) => {
        const brand = brands.find((b) => b.id === opt.value);
        if (!brand) return false;
        return (
          opt.label.toLowerCase().includes(lowerText) ||
          (brand.description &&
            brand.description.toLowerCase().includes(lowerText))
        );
      });
    },
    [brands]
  );

  const handleBrandChange = useCallback(
    (value: number | string | null) => {
      const brandId = value !== null && value !== '' ? String(value) : null;
      setFormData((prev) => ({ ...prev, brand_id: brandId }));
      // Clear pending brand if an existing brand is selected or value is cleared
      if (brandId !== null || value === null) {
        setPendingBrandName(null);
      }
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  const createBrandRequestFn = (data: BrandCreate) =>
    brandsApi.createBrand(data);
  const { executeRequest: createBrand } = useApiRequest(createBrandRequestFn);

  const handleCreateNewBrand = (brandName: string) => {
    // Store the brand name to be created later, don't create it yet
    setPendingBrandName(brandName.trim());
    // Clear the brand_id since we're creating a new brand
    setFormData((prev) => ({ ...prev, brand_id: null }));
    if (validationError) setValidationError(null);
  };

  const handleBrandInputChange = useCallback(
    (text: string) => {
      // Clear pending brand if user types something different
      if (pendingBrandName && text.trim() !== pendingBrandName) {
        setPendingBrandName(null);
      }
    },
    [pendingBrandName]
  );

  const handleCategoryChange = useCallback(
    (categoryId: number | string | null) => {
      const nextCategoryId =
        categoryId !== null && categoryId !== '' ? String(categoryId) : null;
      setFormData((prev) => ({ ...prev, category_id: nextCategoryId }));
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  const handlePartSelect = useCallback(
    (partId: number | string | null) => {
      const nextPartId = partId ? String(partId) : null;
      setSelectedPartId(nextPartId);
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === 'create') {
      if (!formData.name.trim()) {
        setValidationError('Part name is required');
        return;
      }

      if (!formData.category_id) {
        setValidationError('Category is required');
        return;
      }

      if (!formData.brand_id && !pendingBrandName) {
        setValidationError('Brand is required');
        return;
      }

      setIsCreating(true);
      setCreateError(null);

      try {
        // Create brand first if there's a pending brand name
        let brandId = formData.brand_id;
        if (pendingBrandName) {
          try {
            const brandResult = await createBrand({
              name: pendingBrandName,
              description: null,
            });
            if (brandResult !== null && brandResult.id) {
              brandId = brandResult.id;
              // Refresh brands list
              await fetchBrands();
            } else {
              setCreateError('Failed to create brand. Please try again.');
              setIsCreating(false);
              return;
            }
          } catch (error) {
            setCreateError(
              error instanceof Error
                ? error.message
                : 'Failed to create brand. Please try again.'
            );
            setIsCreating(false);
            return;
          }
        }

        const partData: PartCreate = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          image_urls: imageFileKey ? [imageFileKey] : null,
          product_url: formData.product_url.trim() || null,
          category_id: formData.category_id,
          is_universal: formData.is_universal,
          car_ids: formData.is_universal ? [] : formData.car_ids,
          brand_id: brandId!, // brandId is guaranteed to be set at this point due to validation
          part_number: formData.part_number.trim() || null,
        };

        const buildListPartData: BuildListPartCreate = {
          quantity: Math.max(1, formData.quantity),
          notes: formData.notes.trim() || null,
          build_list_phase_id: selectedPhaseId,
        };

        await buildListPartsApi.createPartAndAddToBuildList(
          buildListId,
          partData,
          buildListPartData
        );

        // Clear pending brand after successful creation
        setPendingBrandName(null);
        onPartAdded();
      } catch (error) {
        setCreateError(
          error instanceof Error
            ? error.message
            : 'Failed to create and add part'
        );
      } finally {
        setIsCreating(false);
      }
    } else {
      if (!selectedPartId) {
        setValidationError('Please select a global part');
        return;
      }

      setIsAddingExisting(true);
      setAddExistingError(null);

      try {
        const buildListPartData: BuildListPartCreate = {
          quantity: Math.max(1, formData.quantity),
          notes: formData.notes.trim() || null,
          build_list_phase_id: selectedPhaseId,
        };

        await buildListPartsApi.addPartToBuildList(
          buildListId,
          selectedPartId,
          buildListPartData
        );

        onPartAdded();
      } catch (error) {
        setAddExistingError(
          error instanceof Error
            ? error.message
            : 'Failed to add part to build list'
        );
      } finally {
        setIsAddingExisting(false);
      }
    }
  };

  const isLoading = isCreating || isAddingExisting;

  // Reset form when mode changes
  const handleModeChange = (newMode: 'create' | 'select') => {
    setMode(newMode);
    setValidationError(null);
    setCreateError(null);
    setAddExistingError(null);
    if (newMode === 'select') {
      // Clear create form data when switching to select mode
      setFormData({
        name: '',
        part_number: '',
        brand_id: null,
        description: '',
        product_url: '',
        category_id: null,
        car_ids: [],
        is_universal: false,
        notes: '',
        quantity: 1,
      });
      setImageFileKey(null);
      setPendingBrandName(null);
    } else {
      // Clear selection when switching to create mode
      setSelectedPartId(null);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
      className="space-y-6"
    >
      {(createError || addExistingError || validationError) && (
        <ErrorAlert
          message={createError || addExistingError || validationError || ''}
        />
      )}

      {/* Mode Selection - Either-Or Toggle */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-300 mb-3">
          Choose an option:
        </label>
        <div
          className="inline-flex rounded-lg border border-gray-600 bg-gray-800 p-1"
          role="group"
          aria-label="Part selection mode"
        >
          <button
            type="button"
            onClick={() => handleModeChange('select')}
            className={`px-6 py-2.5 rounded-md font-medium transition-all ${
              mode === 'select'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
            aria-pressed={mode === 'select'}
          >
            Select Existing Part
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('create')}
            className={`px-6 py-2.5 rounded-md font-medium transition-all ${
              mode === 'create'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
            aria-pressed={mode === 'create'}
          >
            Create New Part
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Select one option above. You can switch between them at any time.
        </p>
      </div>

      {mode === 'create' ? (
        /* Create New Part Form */
        <div className="space-y-4">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-200">
              Create New Part
            </h3>
            <p className="text-sm text-gray-400 mt-1">
              Create a new part and add it to this build list
            </p>
          </div>

          <Input
            label="Part Name *"
            id="global-part-name"
            name="name"
            type="text"
            value={formData.name}
            onChange={handleInputChange}
            placeholder="Enter part name"
            required
          />

          <Input
            label="Part Number"
            id="global-part-number"
            name="part_number"
            type="text"
            value={formData.part_number}
            onChange={handleInputChange}
            placeholder="Enter part number"
          />

          <div>
            <SearchableSelect
              id="global-part-brand"
              name="brand_id"
              label="Brand *"
              placeholder="Type to search for a brand or create new..."
              value={formData.brand_id}
              onChange={handleBrandChange}
              options={brandOptions}
              disabled={isLoadingBrands}
              isLoading={isLoadingBrands}
              emptyMessage="No brands found. Type a name to create a new brand."
              filterOptions={filterBrands}
              onCreateNew={handleCreateNewBrand}
              createNewLabel="Create brand"
              displayValue={pendingBrandName}
              onInputChange={handleBrandInputChange}
            />
            {pendingBrandName && (
              <div className="mt-2 px-3 py-2 bg-blue-500/20 border border-blue-500/50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-blue-300">
                  <svg
                    className="w-4 h-4 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span>
                    New brand <strong>&quot;{pendingBrandName}&quot;</strong>{' '}
                    will be created when you submit this form.
                  </span>
                </div>
              </div>
            )}
          </div>

          <Input
            label="Description"
            id="global-part-description"
            name="description"
            type="text"
            value={formData.description}
            onChange={handleInputChange}
            placeholder="Enter part description"
          />

          <div>
            <Input
              label="Product URL"
              id="global-part-product-url"
              name="product_url"
              type="url"
              value={formData.product_url}
              onChange={handleInputChange}
              placeholder="https://example.com/product"
            />
            {isCheckingUrl && formData.product_url.trim() && (
              <p className="mt-1 text-xs text-gray-400 flex items-center gap-1">
                <LoadingSpinner />
                <span>Checking if URL already exists...</span>
              </p>
            )}
            {duplicatePartId && (
              <div className="mt-2 p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
                <div className="flex items-start gap-2">
                  <svg
                    className="w-4 h-4 flex-shrink-0 text-yellow-400 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <div className="flex-grow min-w-0">
                    <p className="text-sm font-medium text-yellow-300 mb-1">
                      A part with this URL already exists
                    </p>
                    <p className="text-xs text-yellow-200/80 mb-2">
                      This product URL is already associated with an existing
                      part in the catalog.
                    </p>
                    <Link
                      to={`/parts/${duplicatePartId}`}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-yellow-300 hover:text-yellow-200 underline"
                    >
                      <span>View existing part</span>
                      <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                        />
                      </svg>
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </div>

          <SearchableSelect
            id="global-part-category"
            name="category_id"
            label="Category *"
            placeholder="Type to search for a category..."
            value={formData.category_id}
            onChange={handleCategoryChange}
            options={categoryOptions}
            disabled={isLoadingCategories}
            isLoading={isLoadingCategories}
            emptyMessage="No categories found. Try a different search term."
            filterOptions={filterCategories}
          />

          <ImageUpload
            currentImageUrl={imageFileKey}
            entityType="part"
            onImageUploaded={(fileKey) => {
              setImageFileKey(fileKey);
            }}
            onImageRemoved={() => {
              setImageFileKey(null);
            }}
            label="Part Image (Optional)"
            maxSizeMB={10}
          />

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="create-part-universal"
              checked={formData.is_universal}
              onChange={handleUniversalChange}
              className="rounded border-gray-500 bg-gray-700 text-indigo-500 focus:ring-indigo-500"
            />
            <label
              htmlFor="create-part-universal"
              className="text-sm text-gray-300"
            >
              Universal part (fits all vehicles)
            </label>
          </div>
          {!formData.is_universal && (
            <CarModelMultiSelect
              cars={cars}
              value={formData.car_ids}
              onChange={handleCarIdsChange}
              label="Car models (optional)"
              placeholder="Type to search for a car model..."
              isLoading={isLoadingCars}
              emptyMessage="No cars found or all selected."
            />
          )}
        </div>
      ) : (
        /* Select Existing Part */
        <div className="space-y-4">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-200">
              Select Existing Part
            </h3>
            <p className="text-sm text-gray-400 mt-1">
              Search for an existing part from the catalog to add to this build
              list. This helps prevent duplicates and keeps the catalog
              organized.
            </p>
          </div>

          {isLoadingParts ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : partsError ? (
            <ErrorAlert message="Failed to load parts" />
          ) : parts && parts.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <p>No parts found in the catalog.</p>
              <p className="text-sm mt-2">
                Switch to "Create New Part" to add a new part.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <SearchableSelect
                id="select-global-part"
                name="part_id"
                label="Search for Part"
                placeholder="Type to search for a part (name, brand, part number, description)..."
                value={selectedPartId}
                onChange={handlePartSelect}
                options={partOptions}
                disabled={isLoadingParts}
                isLoading={isLoadingParts}
                emptyMessage="No parts found. Try a different search term or create a new part."
                filterOptions={filterParts}
              />

              {/* Show selected part details */}
              {selectedPartId && (
                <div className="mt-4 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
                  {(() => {
                    const selectedPart = parts?.find(
                      (p) => p.id === selectedPartId
                    );
                    if (!selectedPart) return null;
                    return (
                      <div className="space-y-4">
                        <div className="flex items-start gap-4">
                          {/* Part Image */}
                          <div className="flex-shrink-0">
                            <div className="w-32 h-32">
                              <ImageWithPlaceholder
                                srcUrl={selectedPart.image_urls?.[0] ?? null}
                                altText={selectedPart.name}
                                imageClassName="w-full h-full object-cover rounded-lg"
                                containerClassName="w-full h-full flex justify-center items-center bg-gray-700 rounded-lg"
                                fallbackText="No image"
                              />
                            </div>
                          </div>

                          {/* Part Details */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-semibold text-white text-lg truncate">
                                    {selectedPart.name}
                                  </h4>
                                  <a
                                    href={`/parts/${selectedPart.id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex-shrink-0 text-blue-400 hover:text-blue-300 transition-colors"
                                    title="Open part in new tab"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <svg
                                      className="w-5 h-5"
                                      fill="none"
                                      stroke="currentColor"
                                      viewBox="0 0 24 24"
                                    >
                                      <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                                      />
                                    </svg>
                                  </a>
                                </div>
                                {selectedPart.brand_id && (
                                  <p className="text-sm text-gray-400 mt-1">
                                    <span className="font-medium">Brand:</span>{' '}
                                    {brands.find(
                                      (b) => b.id === selectedPart.brand_id
                                    )?.name || 'Unknown'}
                                  </p>
                                )}
                                {selectedPart.part_number && (
                                  <p className="text-sm text-gray-400">
                                    <span className="font-medium">Part #:</span>{' '}
                                    {selectedPart.part_number}
                                  </p>
                                )}
                                {selectedPart.description && (
                                  <p className="text-sm text-gray-300 mt-2 line-clamp-3">
                                    {selectedPart.description}
                                  </p>
                                )}
                              </div>
                              {selectedPart.best_price_cents != null && (
                                <div className="ml-4 text-right flex-shrink-0">
                                  <span className="text-lg font-semibold text-green-400">
                                    $
                                    {(
                                      selectedPart.best_price_cents / 100
                                    ).toFixed(2)}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Quantity & Notes (Common to both modes) */}
      <div className="space-y-4 pt-4 border-t border-gray-700">
        <div>
          <h3 className="text-lg font-semibold text-gray-200 mb-1">
            Build List Options
          </h3>
          <p className="text-sm text-gray-400 mb-3">
            Set quantity and optional notes for this part in your build list
          </p>
        </div>
        <div>
          <label
            htmlFor="build-list-part-quantity"
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Quantity
          </label>
          <input
            id="build-list-part-quantity"
            type="number"
            min={1}
            max={999}
            value={formData.quantity}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!Number.isNaN(v) && v >= 1)
                setFormData((prev) => ({ ...prev, quantity: v }));
            }}
            className="mt-1 block w-24 px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
        </div>
        {(phasesData?.length ?? 0) > 0 && (
          <div>
            <label
              htmlFor="build-list-part-phase"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Phase
            </label>
            <select
              id="build-list-part-phase"
              value={selectedPhaseId ?? ''}
              onChange={(e) => {
                const v = e.target.value;
                setSelectedPhaseId(v === '' ? null : v);
              }}
              className="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="">None</option>
              {(phasesData ?? [])
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((phase: BuildListPhaseRead) => (
                  <option key={phase.id} value={phase.id}>
                    {phase.name}
                  </option>
                ))}
            </select>
          </div>
        )}
        <Input
          label="Notes (Optional)"
          id="build-list-part-notes"
          name="notes"
          type="text"
          value={formData.notes}
          onChange={handleInputChange}
          placeholder="Add notes about this part in your build list"
        />
      </div>

      <div className="flex justify-end space-x-3 pt-4">
        <SecondaryButton type="button" onClick={onCancel} disabled={isLoading}>
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? (
            <LoadingSpinner />
          ) : mode === 'create' ? (
            'Create & Add to Build List'
          ) : (
            'Add to Build List'
          )}
        </ActionButton>
      </div>
    </form>
  );
}

export default CreateBuildListPartForm;
