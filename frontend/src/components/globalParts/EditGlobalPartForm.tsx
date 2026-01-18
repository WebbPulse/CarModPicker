import { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { categoriesApi } from '../../services/Api';
import type {
  CategoryResponse,
  GlobalPartRead,
  GlobalPartUpdate,
} from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';

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
    image_url: '',
    category_id: 1,
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);

  const {
    isLoading,
    error,
    executeRequest: updateGlobalPart,
  } = useApiRequest(updateGlobalPartRequestFn);

  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);

  useEffect(() => {
    void fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    if (categoriesData && Array.isArray(categoriesData)) {
      setCategories(categoriesData);
      setIsLoadingCategories(false);
    }
  }, [categoriesData]);

  useEffect(() => {
    setFormData({
      name: globalPart.name ?? '',
      part_number: globalPart.part_number ?? '',
      brand: globalPart.brand ?? '',
      description: globalPart.description ?? '',
      price:
        globalPart.price !== null && globalPart.price !== undefined
          ? globalPart.price.toString()
          : '',
      image_url: globalPart.image_url ?? '',
      category_id: globalPart.category_id ?? 1,
    });
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
      price: formData.price ? parseFloat(formData.price) : null,
      image_url: formData.image_url.trim() || null,
      category_id: formData.category_id,
    };

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
        type="number"
        value={formData.price}
        onChange={handleInputChange}
        placeholder="0.00"
        step="0.01"
        min="0"
      />

      <Input
        label="Image URL"
        id="global-part-image-url"
        name="image_url"
        type="url"
        value={formData.image_url}
        onChange={handleInputChange}
        placeholder="https://example.com/image.jpg"
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
