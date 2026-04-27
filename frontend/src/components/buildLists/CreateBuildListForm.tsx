import React, { useCallback, useEffect, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { carGenerationsApi } from '../../services/Api';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  formatCarYearRange,
  normalizeCarReadList,
} from '../../utils/carUtils';
import type {
  BuildListCreate,
  BuildListRead,
  CarGenerationRead,
} from '../../types/Api';
import ImageUpload from '../forms/ImageUpload';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';

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
  const [selectedGeneration, setSelectedGeneration] =
    useState<CarGenerationRead | null>(null);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarGenerationRead[]>([]);
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
  const fetchMakeStatsFn = useCallback(
    () => carGenerationsApi.getCarMakeStats(),
    []
  );

  // Fetch available manufacturers
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  // Memoize cars by make request function
  const fetchCarsByMakeFn = useCallback(
    (make: string) =>
      carGenerationsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
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
    setAvailableCars(normalizeCarReadList(carsByMake ?? undefined));
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
      image_urls: imageFileKey ? [imageFileKey] : null,
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
    new Set(
      availableCars.map((car) => car.car_model_name ?? '').filter(Boolean)
    )
  ).sort();

  // Get generations (cars) for selected make and model
  const generations = availableCars
    .filter(
      (car) =>
        (car.car_make_name ?? '') === selectedMake &&
        (car.car_model_name ?? '') === selectedModel
    )
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
                  className="text-info hover:text-info/90 transition-colors"
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
                      <Spinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {availableMakes.map((make) => (
                      <Card
                        key={make}
                        onClick={() => setSelectedMake(make)}
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors"
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
                      <Spinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {uniqueModels.map((model) => (
                      <Card
                        key={model}
                        onClick={() => setSelectedModel(model)}
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors"
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
                      className="cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors p-5"
                    >
                      <h4 className="text-base font-semibold text-info mb-1 break-words px-1">
                        {carGenerationDisplayName(car)}
                      </h4>
                      <p className="text-xs text-gray-400">
                        {formatCarYearRange(car.start_year, car.end_year)}
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
                      Selected: {carFullDisplayName(selectedGeneration)}
                    </h4>
                    <p className="text-sm text-gray-400">
                      {formatCarYearRange(
                        selectedGeneration.start_year,
                        selectedGeneration.end_year
                      )}
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
            <div>
              <label
                htmlFor="buildlist-name"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Build List Name
              </label>
              <Input
                id="buildlist-name"
                name="buildlist-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            <div>
              <label
                htmlFor="buildlist-description"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Description (Optional)
              </label>
              <Input
                id="buildlist-description"
                name="buildlist-description"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isLoading}
              />
            </div>
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
          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? 'Creating Build List...' : 'Create Build List'}
          </Button>
        )}
      </form>
    </div>
  );
};

export default CreateBuildListForm;
