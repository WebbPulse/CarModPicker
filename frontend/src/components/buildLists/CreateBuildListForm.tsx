import React, { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { carsApi } from '../../services/Api';
import type { BuildListCreate, BuildListRead, CarRead } from '../../types/Api';
import ButtonStretch from '../buttons/StretchButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';

interface CreateBuildListFormProps {
  onBuildListCreated: (newBuildList: BuildListRead) => void;
}

const createBuildListRequestFn = (payload: BuildListCreate) =>
  apiClient.post<BuildListRead>('/build-lists/', payload);

const CreateBuildListForm: React.FC<CreateBuildListFormProps> = ({
  onBuildListCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(
    null
  );
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeCreateBuildList,
    setError: setApiError,
  } = useApiRequest(createBuildListRequestFn);

  // Memoize request functions to prevent infinite re-renders
  const fetchMakeStatsFn = useCallback(() => carsApi.getCarMakeStats(), []);

  // Fetch available manufacturers
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  // Memoize cars by make request function
  const fetchCarsByMakeFn = useCallback(
    (make: string) => carsApi.getCarsByMake(make, { limit: 1000 }),
    []
  );

  // Fetch cars by make when make is selected
  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  useEffect(() => {
    void fetchMakes();
  }, [fetchMakes]);

  useEffect(() => {
    if (makeStats) {
      const makes = Object.keys(makeStats).sort();
      setAvailableMakes(makes);
    }
  }, [makeStats]);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      setSelectedModel(''); // Reset model when make changes
      setSelectedGeneration(null); // Reset generation when make changes
    } else {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, fetchCarsByMake]);

  useEffect(() => {
    if (carsByMake) {
      setAvailableCars(carsByMake);
    }
  }, [carsByMake]);

  useEffect(() => {
    // Reset generation when model changes
    if (selectedModel) {
      setSelectedGeneration(null);
    }
  }, [selectedModel]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (!name.trim()) {
      setFormMessage({
        type: 'error',
        text: 'Build list name is required.',
      });
      return;
    }

    if (!selectedGeneration) {
      setFormMessage({
        type: 'error',
        text: 'Please select a car generation.',
      });
      return;
    }

    const payload: BuildListCreate = {
      name: name.trim(),
      description: description.trim() || null,
      car_id: selectedGeneration.id,
      image_url: imageFileKey || null,
    };

    const result = await executeCreateBuildList(payload);

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Build list created successfully!',
      });
      onBuildListCreated(result);
      // Reset form
      setName('');
      setDescription('');
      setImageFileKey(null);
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
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

  return (
    <div className="p-2">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        {/* Car Selection Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200">Select Car</h3>

          {/* Layer 1: Make Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              {selectedMake ? (
                <button
                  type="button"
                  onClick={() => {
                    if (selectedModel) {
                      // On generation page, go back to models
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    } else {
                      // On model page, go back to manufacturers
                      setSelectedMake('');
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    }
                  }}
                  className="text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  {selectedModel
                    ? '← Back to Car Models'
                    : '← Back to Manufacturers'}
                </button>
              ) : (
                'Manufacturer'
              )}
            </label>
            {!selectedMake && (
              <>
                {isLoadingMakes ? (
                  <Card>
                    <div className="flex items-center justify-center py-4">
                      <LoadingSpinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {availableMakes.map((make) => (
                      <Card
                        key={make}
                        onClick={() => setSelectedMake(make)}
                        interactive
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                      >
                        <h4 className="text-base font-semibold text-gray-200 break-words px-3 w-full">
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
                <label className="block text-sm font-medium text-gray-300 mb-2 mt-4">
                  Model
                </label>
                {isLoadingCars ? (
                  <Card>
                    <div className="flex items-center justify-center py-4">
                      <LoadingSpinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {uniqueModels.map((model) => (
                      <Card
                        key={model}
                        onClick={() => setSelectedModel(model)}
                        interactive
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors"
                      >
                        <h4 className="text-base font-semibold text-gray-200 break-words px-3 w-full">
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
                <label className="block text-sm font-medium text-gray-300 mb-2 mt-4">
                  Generation
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {generations.map((car) => (
                    <Card
                      key={car.id}
                      onClick={() => setSelectedGeneration(car)}
                      interactive
                      className="cursor-pointer hover:border-indigo-500 border-2 border-transparent transition-colors p-5"
                    >
                      {car.image_url && (
                        <img
                          src={car.image_url}
                          alt={`${car.make} ${car.model} ${car.generation_name}`}
                          className="w-full h-24 object-cover rounded-md mb-3"
                        />
                      )}
                      <h4 className="text-base font-semibold text-indigo-400 mb-1 break-words px-1">
                        {car.generation_name}
                      </h4>
                      <p className="text-xs text-gray-400">
                        {car.start_year} - {car.end_year}
                      </p>
                    </Card>
                  ))}
                </div>
              </>
            )}

            {/* Selected Generation Display */}
            {selectedGeneration && (
              <Card className="mt-4 bg-gray-800">
                <div className="flex items-center justify-between p-3">
                  <div>
                    <h4 className="text-base font-semibold text-gray-200">
                      Selected: {selectedGeneration.make}{' '}
                      {selectedGeneration.model}{' '}
                      {selectedGeneration.generation_name}
                    </h4>
                    <p className="text-sm text-gray-400">
                      {selectedGeneration.start_year} -{' '}
                      {selectedGeneration.end_year}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedMake('');
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    }}
                    className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-sm"
                  >
                    Change
                  </button>
                </div>
              </Card>
            )}
          </div>
        </div>

        {/* Build List Details Section - Only show after car is selected */}
        {selectedGeneration && (
          <div className="space-y-4 border-t border-gray-700 pt-4">
            <h3 className="text-lg font-semibold text-gray-200">
              Build List Details
            </h3>
            <Input
              label="Build List Name"
              id="buildlist-name"
              name="buildlist-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={isLoading}
            />
            <Input
              label="Description (Optional)"
              id="buildlist-description"
              name="buildlist-description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isLoading}
            />
            <ImageUpload
              currentImageUrl={imageFileKey}
              entityType="build_list"
              onImageUploaded={(fileKey) => {
                setImageFileKey(fileKey);
              }}
              onImageRemoved={() => {
                setImageFileKey(null);
              }}
              label="Build List Image (Optional)"
              maxSizeMB={10}
            />
          </div>
        )}

        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        {selectedGeneration && (
          <ButtonStretch type="submit" disabled={isLoading}>
            {isLoading ? 'Creating Build List...' : 'Create Build List'}
          </ButtonStretch>
        )}
      </form>
    </div>
  );
};

export default CreateBuildListForm;
