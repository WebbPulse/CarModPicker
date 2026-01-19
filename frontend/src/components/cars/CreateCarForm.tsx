import React, { useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { carsApi } from '../../services/Api';
import type { CarCreate, CarRead } from '../../types/Api';
import ButtonStretch from '../buttons/StretchButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Card from '../common/Card';
import ImageUpload from '../common/ImageUpload';
import Input from '../common/Input';

interface CreateCarFormProps {
  onCarCreated: (newCar: CarRead) => void;
}

const createCarRequestFn = (payload: CarCreate) => carsApi.createCar(payload);

const CreateCarForm: React.FC<CreateCarFormProps> = ({ onCarCreated }) => {
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [generationName, setGenerationName] = useState('');
  const [startYear, setStartYear] = useState<number | ''>('');
  const [endYear, setEndYear] = useState<number | ''>('');
  const [description, setDescription] = useState('');
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeCreateCar,
    setError: setApiError,
  } = useApiRequest(createCarRequestFn);

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

    const payload: CarCreate = {
      make: make.trim(),
      model: model.trim(),
      generation_name: generationName.trim(),
      start_year: Number(startYear),
      end_year: Number(endYear),
      description: description.trim() || null,
      image_url: imageFileKey || null,
    };

    const result = await executeCreateCar(payload);

    if (result) {
      setFormMessage({ type: 'success', text: 'Car created successfully!' });
      onCarCreated(result);

      setMake('');
      setModel('');
      setGenerationName('');
      setStartYear('');
      setEndYear('');
      setDescription('');
      setImageFileKey(null);
    } else {
      // apiError will be set by the hook
      // setFormMessage({ type: 'error', text: apiError || 'Failed to create car.' });
    }
  };

  return (
    <Card className="p-4">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        <Input
          label="Make"
          id="make"
          name="make"
          type="text"
          value={make}
          onChange={(e) => setMake(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Model"
          id="model"
          name="model"
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Generation Name"
          id="generation_name"
          name="generation_name"
          type="text"
          value={generationName}
          onChange={(e) => setGenerationName(e.target.value)}
          required
          disabled={isLoading}
          placeholder="e.g., 5th Gen, MK7, F30"
        />
        <Input
          label="Start Year"
          id="start_year"
          name="start_year"
          type="number"
          value={startYear}
          onChange={(e) =>
            setStartYear(e.target.value === '' ? '' : Number(e.target.value))
          }
          required
          disabled={isLoading}
        />
        <Input
          label="End Year"
          id="end_year"
          name="end_year"
          type="number"
          value={endYear}
          onChange={(e) =>
            setEndYear(e.target.value === '' ? '' : Number(e.target.value))
          }
          required
          disabled={isLoading}
        />
        <Input
          label="Description (Optional)"
          id="description"
          name="description"
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isLoading}
          placeholder="Optional description of this car generation"
        />
        <ImageUpload
          currentImageUrl={imageFileKey}
          entityType="car"
          onImageUploaded={(fileKey) => {
            setImageFileKey(fileKey);
          }}
          onImageRemoved={() => {
            setImageFileKey(null);
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
        <ButtonStretch type="submit" disabled={isLoading}>
          {isLoading ? 'Adding Car...' : 'Add Car'}
        </ButtonStretch>
      </form>
    </Card>
  );
};

export default CreateCarForm;
