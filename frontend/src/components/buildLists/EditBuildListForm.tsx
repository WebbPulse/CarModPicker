import React, { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import apiClient, { carsApi } from '../../services/Api';
import type { BuildListRead, BuildListUpdate, CarRead } from '../../types/Api';
import SecondaryButton from '../buttons/SecondaryButton';
import ButtonStretch from '../buttons/StretchButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';

interface EditBuildListFormProps {
  buildList: BuildListRead;
  onBuildListUpdated: (updatedBuildList: BuildListRead) => void;
  onCancel: () => void;
}

const updateBuildListRequestFn = (payload: {
  buildListId: number;
  data: BuildListUpdate;
}) =>
  apiClient.put<BuildListRead>(
    `/build-lists/${payload.buildListId}`,
    payload.data
  );

const EditBuildListForm: React.FC<EditBuildListFormProps> = ({
  buildList,
  onBuildListUpdated,
  onCancel,
}) => {
  const [name, setName] = useState(buildList.name);
  const [description, setDescription] = useState(buildList.description || '');
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] = useState<CarRead | null>(null);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarRead[]>([]);
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeUpdateBuildList,
    setError: setApiError,
  } = useApiRequest(updateBuildListRequestFn);

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

  // Fetch current car if buildList has car_id
  const fetchCurrentCarFn = useCallback(
    (carId: number) => carsApi.getCar(carId),
    []
  );

  const {
    data: currentCarData,
    executeRequest: fetchCurrentCar,
  } = useApiRequest(fetchCurrentCarFn);

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

  // Fetch current car when buildList changes
  useEffect(() => {
    if (buildList.car_id) {
      void fetchCurrentCar(buildList.car_id);
    } else {
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [buildList.car_id, fetchCurrentCar]);

  useEffect(() => {
    if (currentCarData) {
      setSelectedMake(currentCarData.make);
      setSelectedModel(currentCarData.model);
      setSelectedGeneration(currentCarData);
    }
  }, [currentCarData]);

  useEffect(() => {
    setName(buildList.name);
    setDescription(buildList.description || '');
    // Note: buildList.image_url is now a presigned URL from the API
    setImageFileKey(null);
    setImageChanged(false);
    setApiError(null);
    setFormMessage(null);
  }, [buildList, setApiError]);

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

    const payload: BuildListUpdate = {
      name: name.trim(),
      description: description.trim() || null,
      car_id: selectedGeneration?.id || null,
    };

    // Only include image_url if it was changed (new file key uploaded)
    if (imageChanged) {
      payload.image_url = imageFileKey || null;
    }

    // Always submit the data, even if no changes detected
    // This provides better UX and allows users to "save" without making changes

    const result = await executeUpdateBuildList({
      buildListId: buildList.id,
      data: payload,
    });

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Build list updated successfully!',
      });
      onBuildListUpdated(result);
    }
  };

  // Get unique models for selected make
  const uniqueModels = Array.from(
    new Set(availableCars.map((car) => car.model))
  ).sort();

  // Get generations (cars) for selected make and model
  const generations = availableCars.filter(
    (car) => car.make === selectedMake && car.model === selectedModel
  ).sort((a, b) => {
    // Sort by start_year, then generation_name
    if (a.start_year !== b.start_year) {
      return a.start_year - b.start_year;
    }
    return a.generation_name.localeCompare(b.generation_name);
  });

  return (
    <div className="p-4">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        {/* Car Selection Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200">
            Select Car (Optional)
          </h3>

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
                  {selectedModel ? '← Back to Car Models' : '← Back to Manufacturers'}
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
                      Selected: {selectedGeneration.make} {selectedGeneration.model}{' '}
                      {selectedGeneration.generation_name}
                    </h4>
                    <p className="text-sm text-gray-400">
                      {selectedGeneration.start_year} - {selectedGeneration.end_year}
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

            {/* Option to remove car assignment */}
            {selectedGeneration && (
              <button
                type="button"
                onClick={() => {
                  setSelectedMake('');
                  setSelectedModel('');
                  setSelectedGeneration(null);
                }}
                className="mt-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors text-sm"
              >
                Remove Car Assignment
              </button>
            )}
          </div>
        </div>

        <div>
          <label
            htmlFor="edit-buildlist-name"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Build List Name
          </label>
          <Input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label
            htmlFor="edit-buildlist-description"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Description (Optional)
          </label>
          <Input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isLoading}
          />
        </div>
        <ImageUpload
          currentImageUrl={buildList.image_url ?? null}
          entityType="build_list"
          entityId={buildList.id}
          onImageUploaded={(fileKey) => {
            setImageFileKey(fileKey);
            setImageChanged(true);
          }}
          onImageRemoved={() => {
            setImageFileKey(null);
            setImageChanged(true);
          }}
          label="Build List Image (Optional)"
          maxSizeMB={10}
        />
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <div className="flex space-x-2 pt-2">
          <ButtonStretch type="submit" disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Changes'}
          </ButtonStretch>
          <SecondaryButton
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="w-full"
          >
            Cancel
          </SecondaryButton>
        </div>
      </form>
    </div>
  );
};

export default EditBuildListForm;
