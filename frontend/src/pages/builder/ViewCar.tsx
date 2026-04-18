import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CAR_VIEW_BUILD_LISTS_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { carsApi, categoriesApi } from '../../services/Api';
import type { CategoryResponse } from '../../types/Api';

import BuildListList from '../../components/buildLists/BuildListList';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import { ErrorAlert } from '../../components/common/Alerts';
import { formatCarYearRange } from '../../utils/carUtils';
import Card from '../../components/common/Card';
import CardInfoItem from '../../components/common/CardInfoItem';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PartList from '../../components/parts/PartList';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchCarRequestFn = (carId: string) => carsApi.getCar(carId);

function ViewCar(): React.JSX.Element {
  const { carId } = useParams<{ carId: string }>();
  const { user: currentUser } = useAuth();
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [buildListRefreshTrigger, setBuildListRefreshTrigger] = useState(0);
  const [partsRefreshTrigger, setPartsRefreshTrigger] = useState(0);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [buildListSearchTerm, setBuildListSearchTerm] = useState('');
  const [partsSearchTerm, setPartsSearchTerm] = useState('');

  const {
    data: car,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch {
      // Failed to load categories
    }
  }, []);

  useEffect(() => {
    if (carId) {
      void fetchCar(carId);
    }
    void loadCategories();
  }, [carId, fetchCar, loadCategories]);

  const handleBuildListCreated = () => {
    setBuildListRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false); // Close dialog
  };

  const handleVoteUpdate = (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _partId: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _newVote: 'upvote' | 'downvote' | null
  ) => {
    // Refresh parts list after voting
    setPartsRefreshTrigger((prev) => prev + 1);
  };

  const handleCategoryChange = (categoryId: string | null) => {
    setSelectedCategory(categoryId);
    // Refresh parts list when category changes
    setPartsRefreshTrigger((prev) => prev + 1);
  };

  const handleBuildListSearchChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setBuildListSearchTerm(e.target.value);
    // Reset to page 1 when search changes (handled by BuildListList component)
  };

  const handlePartsSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPartsSearchTerm(e.target.value);
    // Refresh parts list when search changes
    setPartsRefreshTrigger((prev) => prev + 1);
  };

  const openCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(true);
  };

  const closeCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(false);
  };

  if (isLoadingCar) {
    return (
      <>
        <PageHeader title="Car Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (carApiError) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load car with ID "${carId}". ${carApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!car) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert message={`Car with ID "${carId}" not found.`} />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={`${car.make ?? ''} ${car.model ?? ''} ${car.generation_name ?? ''} (${formatCarYearRange(car.start_year, car.end_year)})`}
      />
      <Card>
        <div className="mb-4">
          <SectionHeader title="Car Information" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <div className="hidden md:block"></div> {/* Spacer */}
          <CardInfoItem label="Make:">
            <p>{car.make ?? ''}</p>
          </CardInfoItem>
          <CardInfoItem label="Model:">
            <p>{car.model ?? ''}</p>
          </CardInfoItem>
          <CardInfoItem label="Generation:">
            <p>{car.generation_name ?? ''}</p>
          </CardInfoItem>
          <CardInfoItem label="Year Range:">
            <p>{formatCarYearRange(car.start_year, car.end_year)}</p>
          </CardInfoItem>
          {car.description && (
            <CardInfoItem label="Description:">
              <p>{car.description}</p>
            </CardInfoItem>
          )}
        </div>
      </Card>

      <Divider />

      {/* Dialog for Creating Build List */}
      <Dialog
        isOpen={isCreateBuildListFormOpen}
        onClose={closeCreateBuildListDialog}
        title={`Create Build List for ${car.make ?? ''} ${car.model ?? ''}`}
      >
        <CreateBuildListForm onBuildListCreated={handleBuildListCreated} />
      </Dialog>

      {/* Build Lists Section */}
      {currentUser && (
        <>
          <div className="mb-4">
            <SectionHeader
              title={`Build Lists for ${car.make ?? ''} ${car.model ?? ''} ${car.generation_name ?? ''}`}
            />
            <div className="mt-4">
              <Input
                id="search-build-lists"
                type="text"
                placeholder="Search build lists by name or description..."
                value={buildListSearchTerm}
                onChange={handleBuildListSearchChange}
                className="w-full"
              />
            </div>
          </div>
          <BuildListList
            carId={car.id}
            refreshKey={buildListRefreshTrigger}
            title=""
            emptyMessage="This car doesn't have any build lists yet."
            onAddBuildListClick={openCreateBuildListDialog}
            search={buildListSearchTerm.trim() || undefined}
          />
          <Divider />
        </>
      )}

      {/* Related Parts Section */}
      <div className="mb-4">
        <SectionHeader
          title={`Parts for ${car.make ?? ''} ${car.model ?? ''} ${car.generation_name ?? ''}`}
        />
        <div className="mt-4">
          <Input
            id="search-parts"
            type="text"
            placeholder="Search parts by name, description, brand, or part number..."
            value={partsSearchTerm}
            onChange={handlePartsSearchChange}
            className="w-full"
          />
        </div>
      </div>

      {/* Category Switcher */}
      {categories.length > 0 && (
        <div className="mb-4 overflow-x-auto">
          <div className="flex gap-2 pb-2">
            <button
              type="button"
              onClick={() => handleCategoryChange(null)}
              className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
                selectedCategory === null
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              All
            </button>
            {categories
              .filter((category) => category.is_active)
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => handleCategoryChange(category.id)}
                  className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors flex items-center gap-2 ${
                    selectedCategory === category.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {category.icon && <span>{category.icon}</span>}
                  <span>{category.display_name || category.name}</span>
                </button>
              ))}
          </div>
        </div>
      )}

      <PartList
        params={{
          car_id: car.id,
          limit: CAR_VIEW_BUILD_LISTS_LIMIT,
          ...(selectedCategory && { category_id: selectedCategory }),
          ...(partsSearchTerm && { search: partsSearchTerm }),
        }}
        refreshKey={partsRefreshTrigger}
        title=""
        emptyMessage="No parts found for this car."
        showVoteButtons={true}
        onVoteUpdate={handleVoteUpdate}
      />
      <div className="mt-4 flex justify-center">
        <Card className="inline-block">
          <div className="text-center">
            <Link
              to={`/parts?car_id=${car.id}`}
              className="text-blue-400 hover:text-blue-300 underline font-medium"
            >
              See more parts →
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default ViewCar;
