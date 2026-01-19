import { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { carsApi } from '../../services/Api';
import type { CarRead, GlobalPartCreate } from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../common/SearchableSelect';

interface CreateGlobalPartFormProps {
  onGlobalPartCreated: () => void;
}

const createGlobalPartRequestFn = (globalPartData: GlobalPartCreate) =>
  apiClient.post<GlobalPartCreate>('/global-parts/', globalPartData);
const fetchCarsRequestFn = () => carsApi.listCars({ limit: 1000 });

function CreateGlobalPartForm({
  onGlobalPartCreated,
}: CreateGlobalPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    category_id: 1, // Default category
    car_id: null as number | null,
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [cars, setCars] = useState<CarRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);

  // Convert cars to SearchableSelect options
  const carOptions: SearchableSelectOption[] = cars.map((car) => ({
    id: car.id,
    label: `${car.make} ${car.model} ${car.generation_name} (${car.start_year}${
      car.end_year ? `-${car.end_year}` : ''
    })`,
    value: car.id,
  }));

  // Filter function for cars
  const filterCars = (
    options: SearchableSelectOption[],
    searchText: string
  ): SearchableSelectOption[] => {
    if (!searchText.trim()) return options;
    const lowerText = searchText.toLowerCase();
    return options.filter((opt) => opt.label.toLowerCase().includes(lowerText));
  };

  const {
    isLoading,
    error,
    executeRequest: createGlobalPart,
  } = useApiRequest(createGlobalPartRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  useEffect(() => {
    void fetchCars();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch once on mount - request function is stable

  useEffect(() => {
    if (carsData && Array.isArray(carsData)) {
      setCars(carsData);
      setIsLoadingCars(false);
    }
  }, [carsData]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handleCarChange = (value: number | string | null) => {
    const carId = value !== null && value !== '' ? Number(value) : null;
    setFormData((prev) => ({ ...prev, car_id: carId }));
    if (validationError) setValidationError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Part name is required');
      return;
    }

    const globalPartData: GlobalPartCreate = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      price: formData.price ? parseFloat(formData.price) : null,
      image_url: imageFileKey || null,
      category_id: formData.category_id,
      car_id: formData.car_id,
      brand: formData.brand.trim() || null,
      part_number: formData.part_number.trim() || null,
    };

    const result = await createGlobalPart(globalPartData);
    if (result !== null) {
      onGlobalPartCreated();
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
        currentImageUrl={imageFileKey}
        entityType="global_part"
        onImageUploaded={(fileKey) => {
          setImageFileKey(fileKey);
        }}
        onImageRemoved={() => {
          setImageFileKey(null);
        }}
        label="Part Image (Optional)"
        maxSizeMB={10}
      />

      <div className="flex justify-end space-x-3 pt-4">
        <SecondaryButton
          type="button"
          onClick={() => void onGlobalPartCreated()}
          disabled={isLoading}
        >
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? <LoadingSpinner /> : 'Create Part'}
        </ActionButton>
      </div>
    </form>
  );
}

export default CreateGlobalPartForm;
