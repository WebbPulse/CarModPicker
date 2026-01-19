import { useCallback, useEffect, useMemo, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListPartsApi, carsApi, globalPartsApi } from '../../services/Api';
import type {
  BuildListPartCreate,
  CarRead,
  GlobalPartCreate,
} from '../../types/Api';

import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import ImageUpload from '../common/ImageUpload';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../common/SearchableSelect';

interface CreateBuildListPartFormProps {
  buildListId: number;
  onPartAdded: () => void;
  onCancel: () => void;
}

const fetchGlobalPartsRequestFn = () => globalPartsApi.getGlobalParts();
const fetchCarsRequestFn = () => carsApi.listCars({ limit: 1000 });

function CreateBuildListPartForm({
  buildListId,
  onPartAdded,
  onCancel,
}: CreateBuildListPartFormProps) {
  const [mode, setMode] = useState<'create' | 'select'>('select');
  const [selectedGlobalPartId, setSelectedGlobalPartId] = useState<
    number | null
  >(null);
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    product_url: '',
    category_id: 1, // Default category
    car_id: null as number | null,
    notes: '',
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddingExisting, setIsAddingExisting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [addExistingError, setAddExistingError] = useState<string | null>(null);
  const [cars, setCars] = useState<CarRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);

  const {
    data: globalParts,
    isLoading: isLoadingGlobalParts,
    error: globalPartsError,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  useEffect(() => {
    void fetchGlobalParts();
    void fetchCars();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch once on mount - request functions are stable

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

  const handleCarChange = useCallback(
    (carId: number | string | null) => {
      const numericCarId = carId ? Number(carId) : null;
      setFormData((prev) => ({ ...prev, car_id: numericCarId }));
      if (validationError) setValidationError(null);
    },
    [validationError]
  );

  // Memoize car options to prevent unnecessary re-renders
  const carOptions: SearchableSelectOption[] = useMemo(() => {
    return cars
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
        label: `${car.make} ${car.model} - ${car.generation_name} (${car.start_year}-${car.end_year})`,
      }));
  }, [cars]);

  // Memoize filter function to prevent SearchableSelect from breaking
  const filterCars = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((option) => {
        // Search in the label directly (which contains all car info)
        return option.label.toLowerCase().includes(lowerText);
      });
    },
    []
  );

  // Convert global parts to SearchableSelectOption format
  const globalPartOptions: SearchableSelectOption[] = useMemo(() => {
    if (!globalParts) return [];
    return globalParts
      .sort((a, b) => {
        // Sort by name first
        return a.name.localeCompare(b.name);
      })
      .map((part) => ({
        id: part.id,
        value: part.id,
        label: `${part.name}${part.brand ? ` - ${part.brand}` : ''}${part.price ? ` - $${(part.price / 100).toFixed(2)}` : ''}`,
      }));
  }, [globalParts]);

  // Filter function for global parts
  const filterGlobalParts = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((option) => {
        const part = globalParts?.find((p) => p.id === option.value);
        if (!part) return false;
        return (
          part.name.toLowerCase().includes(lowerText) ||
          (part.brand && part.brand.toLowerCase().includes(lowerText)) ||
          (part.description &&
            part.description.toLowerCase().includes(lowerText)) ||
          (part.part_number &&
            part.part_number.toLowerCase().includes(lowerText)) ||
          option.label.toLowerCase().includes(lowerText)
        );
      });
    },
    [globalParts]
  );

  const handlePartSelect = useCallback(
    (partId: number | string | null) => {
      const numericPartId = partId ? Number(partId) : null;
      setSelectedGlobalPartId(numericPartId);
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

      setIsCreating(true);
      setCreateError(null);

      try {
        const globalPartData: GlobalPartCreate = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          price: formData.price
            ? Math.round(parseFloat(formData.price) * 100)
            : null,
          image_url: imageFileKey || null,
          product_url: formData.product_url.trim() || null,
          category_id: formData.category_id,
          car_id: formData.car_id,
          brand: formData.brand.trim() || null,
          part_number: formData.part_number.trim() || null,
        };

        const buildListPartData: BuildListPartCreate = {
          notes: formData.notes.trim() || null,
        };

        await buildListPartsApi.createGlobalPartAndAddToBuildList(
          buildListId,
          globalPartData,
          buildListPartData
        );

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
      if (!selectedGlobalPartId) {
        setValidationError('Please select a global part');
        return;
      }

      setIsAddingExisting(true);
      setAddExistingError(null);

      try {
        const buildListPartData: BuildListPartCreate = {
          notes: formData.notes.trim() || null,
        };

        await buildListPartsApi.addGlobalPartToBuildList(
          buildListId,
          selectedGlobalPartId,
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
        brand: '',
        description: '',
        price: '',
        product_url: '',
        category_id: 1,
        car_id: null,
        notes: '',
      });
      setImageFileKey(null);
    } else {
      // Clear selection when switching to create mode
      setSelectedGlobalPartId(null);
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

          {isLoadingGlobalParts ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : globalPartsError ? (
            <ErrorAlert message="Failed to load parts" />
          ) : globalParts && globalParts.length === 0 ? (
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
                name="global_part_id"
                label="Search for Part"
                placeholder="Type to search for a part (name, brand, part number, description)..."
                value={selectedGlobalPartId}
                onChange={handlePartSelect}
                options={globalPartOptions}
                disabled={isLoadingGlobalParts}
                isLoading={isLoadingGlobalParts}
                emptyMessage="No parts found. Try a different search term or create a new part."
                filterOptions={filterGlobalParts}
              />

              {/* Show selected part details */}
              {selectedGlobalPartId && (
                <div className="mt-4 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
                  {(() => {
                    const selectedPart = globalParts?.find(
                      (p) => p.id === selectedGlobalPartId
                    );
                    if (!selectedPart) return null;
                    return (
                      <div className="space-y-4">
                        <div className="flex items-start gap-4">
                          {/* Part Image */}
                          <div className="flex-shrink-0">
                            <div className="w-32 h-32">
                              <ImageWithPlaceholder
                                srcUrl={selectedPart.image_url ?? null}
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
                                    href={`/global-parts/${selectedPart.id}`}
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
                                {selectedPart.brand && (
                                  <p className="text-sm text-gray-400 mt-1">
                                    <span className="font-medium">Brand:</span>{' '}
                                    {selectedPart.brand}
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
                              {selectedPart.price && (
                                <div className="ml-4 text-right flex-shrink-0">
                                  <span className="text-lg font-semibold text-green-400">
                                    ${(selectedPart.price / 100).toFixed(2)}
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

      {/* Notes Field (Common to both modes) */}
      <div className="space-y-4 pt-4 border-t border-gray-700">
        <div>
          <h3 className="text-lg font-semibold text-gray-200 mb-1">
            Build List Notes
          </h3>
          <p className="text-sm text-gray-400 mb-3">
            Add personal notes about this part in your build list (optional)
          </p>
        </div>
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
