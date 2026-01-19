import React, { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { carsApi } from '../../services/Api';
import type { CarRead, CarUpdate } from '../../types/Api';
import SecondaryButton from '../buttons/SecondaryButton';
import ButtonStretch from '../buttons/StretchButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';

interface EditCarFormProps {
  car: CarRead;
  onCarUpdated: (updatedCar: CarRead) => void;
  onCancel: () => void;
}

const updateCarRequestFn = (payload: { carId: number; data: CarUpdate }) =>
  carsApi.updateCar(payload.carId, payload.data);

const EditCarForm: React.FC<EditCarFormProps> = ({
  car,
  onCarUpdated,
  onCancel,
}) => {
  const [make, setMake] = useState(car.make);
  const [model, setModel] = useState(car.model);
  const [generationName, setGenerationName] = useState(car.generation_name);
  const [startYear, setStartYear] = useState<number | ''>(car.start_year);
  const [endYear, setEndYear] = useState<number | ''>(car.end_year);
  const [description, setDescription] = useState(car.description || '');
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeUpdateCar,
    setError: setApiError,
  } = useApiRequest(updateCarRequestFn);

  useEffect(() => {
    setMake(car.make);
    setModel(car.model);
    setGenerationName(car.generation_name);
    setStartYear(car.start_year);
    setEndYear(car.end_year);
    setDescription(car.description || '');
    // Note: car.image_url is now a presigned URL from the API
    // We'll use it for display, but track file key separately
    setImageFileKey(null);
    setImageChanged(false);
    setApiError(null);
    setFormMessage(null);
  }, [car, setApiError]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (
      !make.trim() ||
      !model.trim() ||
      !generationName.trim() ||
      startYear === '' ||
      endYear === ''
    ) {
      setFormMessage({
        type: 'error',
        text: 'Make, Model, Generation Name, Start Year, and End Year are required.',
      });
      return;
    }
    if (
      isNaN(Number(startYear)) ||
      Number(startYear) < 1886 ||
      Number(startYear) > new Date().getFullYear() + 1
    ) {
      setFormMessage({
        type: 'error',
        text: 'Please enter a valid start year.',
      });
      return;
    }
    if (
      isNaN(Number(endYear)) ||
      Number(endYear) < 1886 ||
      Number(endYear) > new Date().getFullYear() + 1
    ) {
      setFormMessage({ type: 'error', text: 'Please enter a valid end year.' });
      return;
    }
    if (Number(startYear) > Number(endYear)) {
      setFormMessage({
        type: 'error',
        text: 'Start year must be less than or equal to end year.',
      });
      return;
    }

    const payload: CarUpdate = {
      make: make.trim(),
      model: model.trim(),
      generation_name: generationName.trim(),
      start_year: Number(startYear),
      end_year: Number(endYear),
      description: description.trim() || null,
    };

    // Only include image_url if it was changed (new file key uploaded)
    if (imageChanged) {
      payload.image_url = imageFileKey || null;
    }

    // Always submit the data, even if no changes detected
    // This provides better UX and allows users to "save" without making changes

    const result = await executeUpdateCar({ carId: car.id, data: payload });

    if (result) {
      setFormMessage({ type: 'success', text: 'Car updated successfully!' });
      onCarUpdated(result);
    }
  };

  return (
    <div className="p-4">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        <div>
          <label
            htmlFor="edit-make"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Make
          </label>
          <Input
            type="text"
            value={make}
            onChange={(e) => setMake(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label
            htmlFor="edit-model"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Model
          </label>
          <Input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label
            htmlFor="edit-generation-name"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Generation Name
          </label>
          <Input
            type="text"
            value={generationName}
            onChange={(e) => setGenerationName(e.target.value)}
            required
            disabled={isLoading}
            placeholder="e.g., 5th Gen, MK7, F30"
          />
        </div>
        <div>
          <label
            htmlFor="edit-start-year"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Start Year
          </label>
          <Input
            type="number"
            value={startYear.toString()}
            onChange={(e) =>
              setStartYear(
                e.target.value === '' ? '' : parseInt(e.target.value, 10)
              )
            }
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label
            htmlFor="edit-end-year"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            End Year
          </label>
          <Input
            type="number"
            value={endYear.toString()}
            onChange={(e) =>
              setEndYear(
                e.target.value === '' ? '' : parseInt(e.target.value, 10)
              )
            }
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label
            htmlFor="edit-description"
            className="block text-sm font-medium text-neutral-300 mb-2"
          >
            Description (Optional)
          </label>
          <Input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isLoading}
            placeholder="Optional description of this car generation"
          />
        </div>
        <ImageUpload
          currentImageUrl={car.image_url ?? null}
          entityType="car"
          entityId={car.id}
          onImageUploaded={(fileKey) => {
            setImageFileKey(fileKey);
            setImageChanged(true);
          }}
          onImageRemoved={() => {
            setImageFileKey(null);
            setImageChanged(true);
          }}
          label="Car Image (Optional)"
          maxSizeMB={10}
        />
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <div className="flex space-x-3 pt-4">
          <ButtonStretch type="submit" disabled={isLoading} className="flex-1">
            {isLoading ? 'Saving...' : 'Save Changes'}
          </ButtonStretch>
          <SecondaryButton
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1"
          >
            Cancel
          </SecondaryButton>
        </div>
      </form>
    </div>
  );
};

export default EditCarForm;
