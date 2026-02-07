import React, { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { carsApi } from '../../services/Api';
import { normalizeCarReadList } from '../../utils/carUtils';
import type { CarRead } from '../../types/Api';
import AddItemTile from '../common/AddItemTile';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';
import SectionHeader from '../layout/SectionHeader';
import CarListItem from './CarListItem';

interface CarListProps {
  searchQuery?: string;
  make?: string;
  year?: number;
  generationId?: number;
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddCarClick?: () => void;
  showAddCarTile?: boolean;
  limit?: number;
  skip?: number;
}

const CarList: React.FC<CarListProps> = ({
  searchQuery,
  make,
  year,
  generationId,
  refreshKey,
  title = 'Cars',
  emptyMessage = 'No cars found.',
  onAddCarClick,
  showAddCarTile = false,
  limit = 100,
  skip = 0,
}) => {
  const [internalCars, setInternalCars] = useState<CarRead[] | null>(null);

  const fetchCarsRequestFn = useCallback(() => {
    if (searchQuery) {
      return carsApi.searchCars(searchQuery, { skip, limit });
    }
    if (generationId) {
      // In the new backend, a Car is a generation; get single car by id
      return carsApi.getCar(generationId);
    }
    if (make && year) {
      return carsApi.searchCars(`${make} ${year}`, { skip, limit });
    }
    if (make) {
      return carsApi.getCarsByMake(make, { skip, limit });
    }
    if (year) {
      return carsApi.searchCars(String(year), { skip, limit });
    }
    return carsApi.listCars({ skip, limit });
  }, [searchQuery, make, year, generationId, skip, limit]);

  const {
    data: fetchedApiCars,
    isLoading,
    error,
    executeRequest: fetchCars,
  } = useApiRequest(fetchCarsRequestFn);

  useEffect(() => {
    void fetchCars();
  }, [fetchCars, refreshKey]);

  useEffect(() => {
    if (fetchedApiCars != null) {
      const list = Array.isArray(fetchedApiCars)
        ? fetchedApiCars
        : [fetchedApiCars];
      setInternalCars(normalizeCarReadList(list));
    } else if (!isLoading && !error) {
      setInternalCars([]);
    }
  }, [fetchedApiCars, isLoading, error]);

  if (isLoading) {
    return (
      <>
        <SectionHeader title={title} />
        <LoadingSpinner />
      </>
    );
  }

  if (error) {
    return (
      <>
        <SectionHeader title={title} />
        <ErrorAlert message={error} />
      </>
    );
  }

  const noCarsToShow = !internalCars || internalCars.length === 0;

  return (
    <div>
      <SectionHeader title={title} />
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 mt-4">
        {showAddCarTile && onAddCarClick && (
          <AddItemTile
            title="Add a New Car"
            description="Click here to add a vehicle (Admin only)."
            onClick={onAddCarClick}
          />
        )}
        {internalCars &&
          internalCars.map((car) => <CarListItem key={car.id} car={car} />)}
      </div>
      {noCarsToShow && !showAddCarTile && (
        <p className="text-gray-400 mt-4">{emptyMessage}</p>
      )}
      {noCarsToShow && showAddCarTile && (
        <p className="text-gray-400 mt-4">
          No cars found. Click the tile above to add one (Admin only)!
        </p>
      )}
    </div>
  );
};

export default CarList;
