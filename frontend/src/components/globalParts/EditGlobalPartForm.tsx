import { useCallback, useEffect, useMemo, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, {
  brandsApi,
  carsApi,
  categoriesApi,
} from '../../services/Api';
import type {
  BrandCreate,
  BrandResponse,
  CarRead,
  CategoryResponse,
  GlobalPartRead,
  GlobalPartUpdate,
} from '../../types/Api';

import { LARGE_FETCH_LIMIT } from '../../constants';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import CarModelMultiSelect from '../common/CarModelMultiSelect';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../common/SearchableSelect';

interface EditGlobalPartFormProps {
  globalPart: GlobalPartRead;
  onGlobalPartUpdated: () => Promise<void>;
  onCancel: () => void;
}

const updateGlobalPartRequestFn = (payload: {
  globalPartId: number;
  globalPartData: GlobalPartUpdate;
}) =>
  apiClient.put<GlobalPartUpdate>(
    `/global-parts/${payload.globalPartId}`,
    payload.globalPartData
  );

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();
const fetchCarsRequestFn = () => carsApi.listCars({ limit: LARGE_FETCH_LIMIT });
const fetchBrandsRequestFn = () => brandsApi.getBrands(true);

function EditGlobalPartForm({
  globalPart,
  onGlobalPartUpdated,
  onCancel,
}: EditGlobalPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand_id: null as number | null,
    description: '',
    category_id: 1,
    car_ids: [] as number[],
    is_universal: false,
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [cars, setCars] = useState<CarRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [isLoadingBrands, setIsLoadingBrands] = useState(true);
  const [pendingBrandName, setPendingBrandName] = useState<string | null>(null);

  const {
    isLoading,
    error,
    executeRequest: updateGlobalPart,
  } = useApiRequest(updateGlobalPartRequestFn);

  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);
  const { data: brandsData, executeRequest: fetchBrands } =
    useApiRequest(fetchBrandsRequestFn);

  useEffect(() => {
    void fetchCategories();
    void fetchCars();
    void fetchBrands();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch once on mount - request functions are stable

  useEffect(() => {
    if (categoriesData && Array.isArray(categoriesData)) {
      setCategories(categoriesData);
      setIsLoadingCategories(false);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (carsData && Array.isArray(carsData)) {
      setCars(carsData);
      setIsLoadingCars(false);
    }
  }, [carsData]);

  useEffect(() => {
    if (brandsData && Array.isArray(brandsData)) {
      setBrands(brandsData);
      setIsLoadingBrands(false);
    }
  }, [brandsData]);

  useEffect(() => {
    try {
      const carIds = globalPart.car_ids ?? [];
      setFormData({
        name: globalPart.name ?? '',
        part_number: globalPart.part_number ?? '',
        brand_id: globalPart.brand_id ?? null,
        description: globalPart.description ?? '',
        category_id: globalPart.category_id ?? 1,
        car_ids: [...carIds],
        is_universal: globalPart.is_universal ?? false,
      });
      // Note: globalPart.image_urls[0] is a presigned URL from the API
      setImageFileKey(null);
      setImageChanged(false);
    } catch {
      setValidationError('Failed to load part data. Please refresh the page.');
    }
  }, [globalPart]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const categoryId = e.target.value ? Number(e.target.value) : null;
    setFormData((prev) => ({
      ...prev,
      category_id: categoryId ?? 1,
    }));
    if (validationError) setValidationError(null);
  };

  const handleCarIdsChange = (carIds: number[]) => {
    setFormData((prev) => ({ ...prev, car_ids: carIds }));
    if (validationError) setValidationError(null);
  };

  const handleUniversalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setFormData((prev) => ({ ...prev, is_universal: checked }));
    if (validationError) setValidationError(null);
  };

  const handleBrandChange = (value: number | string | null) => {
    const brandId = value !== null && value !== '' ? Number(value) : null;
    setFormData((prev) => ({ ...prev, brand_id: brandId }));
    // Clear pending brand if an existing brand is selected or value is cleared
    if (brandId !== null || value === null) {
      setPendingBrandName(null);
    }
    if (validationError) setValidationError(null);
  };

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

  const handleBrandInputChange = (text: string) => {
    // Clear pending brand if user types something different
    if (pendingBrandName && text.trim() !== pendingBrandName) {
      setPendingBrandName(null);
    }
  };

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Part name is required');
      return;
    }

    if (!formData.brand_id && !pendingBrandName) {
      setValidationError('Brand is required');
      return;
    }

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
          setValidationError('Failed to create brand. Please try again.');
          return;
        }
      } catch (error) {
        setValidationError(
          error instanceof Error
            ? error.message
            : 'Failed to create brand. Please try again.'
        );
        return;
      }
    }

    const globalPartData: GlobalPartUpdate = {
      name: formData.name.trim(),
      part_number: formData.part_number.trim() || null,
      brand_id: brandId!, // brandId is guaranteed to be set at this point due to validation
      description: formData.description.trim() || null,
      category_id: formData.category_id,
      is_universal: formData.is_universal,
      car_ids: formData.is_universal ? [] : formData.car_ids,
    };

    // Only include image_urls if it was changed (new file key uploaded)
    if (imageChanged) {
      globalPartData.image_urls = imageFileKey ? [imageFileKey] : null;
    }

    const result = await updateGlobalPart({
      globalPartId: globalPart.id,
      globalPartData,
    });
    if (result !== null) {
      // Clear pending brand after successful update
      setPendingBrandName(null);
      await onGlobalPartUpdated();
    }
  };

  return (
    <form
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
      className="space-y-4"
    >
      {(error || validationError) && (
        <ErrorAlert message={error || validationError || ''} />
      )}

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

      <div className="relative">
        <label
          htmlFor="global-part-category"
          className="block text-sm font-medium text-neutral-300 mb-2"
        >
          Category *
        </label>
        <select
          id="global-part-category"
          name="category_id"
          value={formData.category_id}
          onChange={handleCategoryChange}
          disabled={isLoadingCategories}
          required
          className="w-full px-5 py-3 bg-gray-800 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all duration-300 ease-out input-modern min-h-[44px] [&>option]:bg-gray-800 [&>option]:text-white"
        >
          {isLoadingCategories ? (
            <option>Loading categories...</option>
          ) : (
            categories
              .filter((category) => category.is_active)
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((category) => (
                <option key={category.id} value={category.id}>
                  {category.display_name}
                </option>
              ))
          )}
        </select>
      </div>

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
                New brand <strong>&quot;{pendingBrandName}&quot;</strong> will
                be created when you submit this form.
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

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="global-part-universal-edit"
          checked={formData.is_universal}
          onChange={handleUniversalChange}
          className="rounded border-gray-500 bg-gray-700 text-indigo-500 focus:ring-indigo-500"
        />
        <label
          htmlFor="global-part-universal-edit"
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

      <ImageUpload
        currentImageUrl={globalPart.image_urls?.[0] ?? null}
        entityType="global_part"
        entityId={globalPart.id}
        onImageUploaded={(fileKey) => {
          setImageFileKey(fileKey);
          setImageChanged(true);
        }}
        onImageRemoved={() => {
          setImageFileKey(null);
          setImageChanged(true);
        }}
        label="Part Image (Optional)"
        maxSizeMB={10}
      />

      <div className="flex justify-end space-x-3 pt-4">
        <SecondaryButton
          type="button"
          onClick={() => void onCancel()}
          disabled={isLoading}
        >
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? <LoadingSpinner /> : 'Update Part'}
        </ActionButton>
      </div>
    </form>
  );
}

export default EditGlobalPartForm;
