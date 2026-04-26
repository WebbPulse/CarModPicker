import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CAR_VIEW_BUILD_LISTS_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { carGenerationsApi, categoriesApi } from '../../services/Api';
import type { CategoryResponse } from '../../types/Api';

import BuildListList from '../../components/buildLists/BuildListList';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  carModelDisplayName,
  formatCarYearRange,
} from '../../utils/carUtils';
import PartList from '../../components/parts/PartList';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Card } from '../../components/ui/card';
import CardInfoItem from '../../components/ui/card-info-item';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import Spinner from '../../components/ui/spinner';

const fetchCarRequestFn = (carId: string) => carGenerationsApi.getCar(carId);

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

  const carTitle = car ? carFullDisplayName(car) : null;
  useDocumentMeta({
    title: carTitle ?? 'Car Generation',
    description: carTitle
      ? `Builds, parts, and modification ideas for the ${carTitle} on CarModPicker.`
      : 'Explore builds and parts for a car generation on CarModPicker.',
    canonicalPath: carId ? `/car-generations/${carId}` : undefined,
  });

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

  if (isLoadingCar) {
    return (
      <>
        <PageHeader title="Car Details" />
        <Spinner />
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
        title={`${carFullDisplayName(car)} (${formatCarYearRange(car.start_year, car.end_year)})`}
      />
      <Card>
        <div className="mb-4">
          <SectionHeader title="Car Information" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-foreground mb-6">
          <CardInfoItem label="Make:">
            <p>{car.car_make_name ?? ''}</p>
          </CardInfoItem>
          <CardInfoItem label="Model:">
            <p>{carModelDisplayName(car)}</p>
          </CardInfoItem>
          <CardInfoItem label="Generation:">
            <p>{carGenerationDisplayName(car)}</p>
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
        open={isCreateBuildListFormOpen}
        onOpenChange={setIsCreateBuildListFormOpen}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{`Create Build List for ${car.car_make_name ?? ''} ${carModelDisplayName(car)}`}</DialogTitle>
          </DialogHeader>
          <CreateBuildListForm onBuildListCreated={handleBuildListCreated} />
        </DialogContent>
      </Dialog>

      {/* Build Lists Section */}
      {currentUser && (
        <>
          <div className="mb-4">
            <SectionHeader
              title={`Build Lists for ${carFullDisplayName(car)}`}
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
        <SectionHeader title={`Parts for ${carFullDisplayName(car)}`} />
        <div className="mt-4">
          <Input
            id="search-parts"
            type="text"
            placeholder="Search parts by name, description, part manufacturer, or part number..."
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
                  ? 'bg-info text-white'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
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
                      ? 'bg-info text-white'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
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
              className="text-info hover:text-info/90 underline font-medium"
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
