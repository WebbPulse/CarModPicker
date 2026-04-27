import React from 'react';
import {
  carGenerationDisplayName,
  formatCarYearRange,
} from '../../utils/carUtils';
import type { CarGenerationRead } from '../../types/Api';
import Spinner from '../ui/spinner';

export interface VehicleFilterSectionProps {
  showUniversalParts: boolean;
  setShowUniversalParts: (v: boolean) => void;
  selectedMake: string;
  selectedModel: string;
  selectedGeneration: CarGenerationRead | null;
  setSelectedMake: (make: string) => void;
  setSelectedModel: (model: string) => void;
  setSelectedGeneration: (car: CarGenerationRead | null) => void;
  availableMakes: string[];
  uniqueModels: string[];
  generations: CarGenerationRead[];
  isLoadingMakes: boolean;
  isLoadingCars: boolean;
  /** When true, hide the "Universal Parts" option (e.g. for build lists catalog). */
  hideUniversalOption?: boolean;
}

const sectionTitleClass =
  'text-xs font-medium text-gray-500 uppercase tracking-wider pb-2 mb-3 border-b border-gray-700/60';
const optionButtonClass = (active: boolean) =>
  `block w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
    active
      ? 'bg-info/30 text-info font-medium'
      : 'text-gray-300 hover:bg-gray-700/50 hover:text-gray-100'
  }`;
const inputClass =
  'w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:ring-2 focus:ring-info focus:border-info/50 transition-colors';

const VehicleFilterSection: React.FC<VehicleFilterSectionProps> = (props) => {
  const {
    showUniversalParts,
    setShowUniversalParts,
    selectedMake,
    selectedModel,
    selectedGeneration,
    setSelectedMake,
    setSelectedModel,
    setSelectedGeneration,
    availableMakes,
    uniqueModels,
    generations,
    isLoadingMakes,
    isLoadingCars,
    hideUniversalOption = false,
  } = props;

  return (
    <div>
      <h3 className={sectionTitleClass}>Car / Vehicle</h3>
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => {
            setShowUniversalParts(false);
            setSelectedMake('');
            setSelectedModel('');
            setSelectedGeneration(null);
          }}
          className={optionButtonClass(
            !showUniversalParts && !selectedGeneration
          )}
        >
          All Vehicles
        </button>

        {!showUniversalParts && (
          <>
            {isLoadingMakes ? (
              <div className="flex justify-center py-3">
                <Spinner />
              </div>
            ) : (
              <select
                value={selectedMake}
                onChange={(e) => {
                  setSelectedMake(e.target.value);
                  setSelectedModel('');
                  setSelectedGeneration(null);
                }}
                className={inputClass}
              >
                <option value="">Select Make</option>
                {availableMakes.map((make) => (
                  <option key={make} value={make}>
                    {make}
                  </option>
                ))}
              </select>
            )}

            {selectedMake && (
              <>
                <select
                  value={selectedModel}
                  onChange={(e) => {
                    setSelectedModel(e.target.value);
                    setSelectedGeneration(null);
                  }}
                  className={inputClass}
                >
                  <option value="">Select Model</option>
                  {uniqueModels.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>

                {selectedModel && (
                  <div className="space-y-2">
                    {isLoadingCars ? (
                      <div className="flex justify-center py-3">
                        <Spinner />
                      </div>
                    ) : (
                      generations.map((car) => (
                        <button
                          key={car.id}
                          type="button"
                          onClick={() => setSelectedGeneration(car)}
                          className={optionButtonClass(
                            selectedGeneration?.id === car.id
                          )}
                        >
                          {carGenerationDisplayName(car)} (
                          {formatCarYearRange(car.start_year, car.end_year)})
                        </button>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {!hideUniversalOption && (
          <button
            type="button"
            onClick={() => {
              setShowUniversalParts(true);
              setSelectedMake('');
              setSelectedModel('');
              setSelectedGeneration(null);
            }}
            className={optionButtonClass(showUniversalParts)}
          >
            Universal Parts
          </button>
        )}
      </div>
    </div>
  );
};

export default VehicleFilterSection;
