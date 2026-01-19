import { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { carsApi, categoriesApi } from '../../services/Api';
import type {
  CarRead,
  CategoryResponse,
  GlobalPartRead,
  GlobalPartUpdate,
} from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
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
const fetchCarsRequestFn = () => carsApi.listCars({ limit: 1000 });

function EditGlobalPartForm({
  globalPart,
  onGlobalPartUpdated,
  onCancel,
}: EditGlobalPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    product_url: '',
    category_id: 1,
    car_id: null as number | null,
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [cars, setCars] = useState<CarRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);

  const {
    isLoading,
    error,
    executeRequest: updateGlobalPart,
  } = useApiRequest(updateGlobalPartRequestFn);

  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  useEffect(() => {
    void fetchCategories();
    void fetchCars();
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
    try {
      setFormData({
        name: globalPart.name ?? '',
        part_number: globalPart.part_number ?? '',
        brand: globalPart.brand ?? '',
        description: globalPart.description ?? '',
        price:
          globalPart.price !== null && globalPart.price !== undefined
            ? (globalPart.price / 100).toFixed(2)
            : '',
        product_url: globalPart.product_url ?? '',
        category_id: globalPart.category_id ?? 1,
        car_id: globalPart.car_id ?? null,
      });
      // Note: globalPart.image_url is now a presigned URL from the API
      setImageFileKey(null);
      setImageChanged(false);
    } catch (error) {
      console.error('Error setting form data:', error);
      setValidationError('Failed to load part data. Please refresh the page.');
    }
  }, [globalPart]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handlePriceBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const value = e.target.value.trim();
    if (value === '') {
      setFormData((prev) => ({ ...prev, price: '' }));
      return;
    }
    const numValue = parseFloat(value);
    if (!isNaN(numValue) && numValue >= 0) {
      const formatted = numValue.toFixed(2);
      setFormData((prev) => ({ ...prev, price: formatted }));
    }
  };

  const handlePriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;

    // Allow empty value
    if (value === '') {
      setFormData((prev) => ({ ...prev, price: '' }));
      if (validationError) setValidationError(null);
      return;
    }

    // Allow only numbers and one decimal point
    if (/^\d*\.?\d*$/.test(value)) {
      // Store the raw value while typing - don't format until blur
      setFormData((prev) => ({ ...prev, price: value }));
      if (validationError) setValidationError(null);
    }
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const categoryId = e.target.value ? Number(e.target.value) : null;
    setFormData((prev) => ({
      ...prev,
      category_id: categoryId ?? 1,
    }));
    if (validationError) setValidationError(null);
  };

  const handleCarChange = (carId: number | string | null) => {
    const numericCarId = carId ? Number(carId) : null;
    setFormData((prev) => ({ ...prev, car_id: numericCarId }));
    if (validationError) setValidationError(null);
  };

  // Convert cars to SearchableSelectOption format
  const carOptions: SearchableSelectOption[] = cars
    .sort((a, b) => {
      // Sort by make, then model, then generation
      if (a.make !== b.make) {
        return a.make.localeCompare(b.make);
      }
      if (a.model !== b.model) {
        return a.model.localeCompare(b.model);
      }
      return a.generation_name.localeCompare(b.generation_name);
    })
    .map((car) => ({
      id: car.id,
      value: car.id,
      label: `${car.make} ${car.model} - ${car.generation_name} (${car.start_year}${car.end_year ? `-${car.end_year}` : ''})`,
    }));

  // Custom filter function that searches across make, model, generation, and years
  const filterCars = (
    options: SearchableSelectOption[],
    searchText: string
  ): SearchableSelectOption[] => {
    if (!searchText.trim()) return options;
    const lowerText = searchText.toLowerCase();
    return options.filter((option) => {
      const car = cars.find((c) => c.id === option.value);
      if (!car) return false;
      return (
        car.make.toLowerCase().includes(lowerText) ||
        car.model.toLowerCase().includes(lowerText) ||
        car.generation_name.toLowerCase().includes(lowerText) ||
        car.start_year.toString().includes(lowerText) ||
        (car.end_year !== null &&
          car.end_year.toString().includes(lowerText)) ||
        option.label.toLowerCase().includes(lowerText)
      );
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Part name is required');
      return;
    }

    const globalPartData: GlobalPartUpdate = {
      name: formData.name.trim(),
      part_number: formData.part_number.trim() || null,
      brand: formData.brand.trim() || null,
      description: formData.description.trim() || null,
      price: formData.price
        ? Math.round(parseFloat(formData.price) * 100)
        : null,
      product_url: formData.product_url.trim() || null,
      category_id: formData.category_id,
      car_id: formData.car_id,
    };

    // Only include image_url if it was changed (new file key uploaded)
    if (imageChanged) {
      globalPartData.image_url = imageFileKey || null;
    }

    const result = await updateGlobalPart({
      globalPartId: globalPart.id,
      globalPartData,
    });
    if (result !== null) {
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

      <Input
        label="Brand"
        id="global-part-brand"
        name="brand"
        type="text"
        value={formData.brand}
        onChange={handleInputChange}
        placeholder="Enter brand name"
      />

      <Input
        label="Description"
        id="global-part-description"
        name="description"
        type="text"
        value={formData.description}
        onChange={handleInputChange}
        placeholder="Enter part description"
      />

      <Input
        label="Price"
        id="global-part-price"
        name="price"
        type="text"
        value={formData.price}
        onChange={handlePriceChange}
        onBlur={handlePriceBlur}
        placeholder="0.00"
        leftIcon={<span className="text-white/80 font-medium">$</span>}
      />

      <Input
        label="Product URL"
        id="global-part-product-url"
        name="product_url"
        type="url"
        value={formData.product_url}
        onChange={handleInputChange}
        placeholder="https://example.com/product"
      />

      <SearchableSelect
        id="global-part-car"
        name="car_id"
        label="Car Model (Optional)"
        placeholder="Type to search for a car model..."
        value={formData.car_id}
        onChange={handleCarChange}
        options={carOptions}
        disabled={isLoadingCars}
        isLoading={isLoadingCars}
        emptyMessage="No cars found. Try a different search term."
        filterOptions={filterCars}
      />

      <ImageUpload
        currentImageUrl={globalPart.image_url ?? null}
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
