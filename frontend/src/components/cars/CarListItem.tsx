import React from 'react';
import { Link } from 'react-router-dom';
import { formatCarYearRange } from '../../utils/carUtils';
import type { CarGenerationRead } from '../../types/Api';
import Card from '../common/Card';
import CardInfoItem from '../common/CardInfoItem';

interface CarListItemProps {
  car: CarGenerationRead;
}

const CarListItem: React.FC<CarListItemProps> = ({ car }) => {
  return (
    <Link
      to={`/car-generations/${car.id}`}
      className="block hover:no-underline h-full"
    >
      <Card className="flex flex-col h-full hover:border-indigo-500 border-2 border-transparent transition-colors">
        {/* Add hover effect */}
        <div className="flex-grow flex flex-col">
          <h3 className="text-lg font-semibold text-indigo-400 mb-2">
            {car.car_make_name ?? ''} {car.car_model_name ?? ''}{' '}
            {car.generation_name ?? ''}
          </h3>
          <div className="grid grid-cols-1 gap-1 text-xs flex-grow">
            <CardInfoItem label="Generation">
              <p>{car.generation_name ?? ''}</p>
            </CardInfoItem>
            <CardInfoItem label="Year Range">
              <p>{formatCarYearRange(car.start_year, car.end_year)}</p>
            </CardInfoItem>
          </div>
        </div>
      </Card>
    </Link>
  );
};

export default CarListItem;
