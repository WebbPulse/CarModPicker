import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import {
  brandsApi,
  buildListPartsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
  globalPartVotesApi,
  usersApi,
} from '../../services/Api';
import type {
  BrandResponse,
  CarRead,
  CategoryResponse,
  GlobalPartReadWithVotes,
  PartListingReadWithRetailer,
} from '../../types/Api';

import ReportDialog from '../../components/admin/ReportDialog';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import CardInfoItem from '../../components/common/CardInfoItem';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import AddToBuildListDialog from '../../components/globalParts/AddToBuildListDialog';
import EditGlobalPartForm from '../../components/globalParts/EditGlobalPartForm';
import ImageGallery from '../../components/globalParts/ImageGallery';
import PriceHistoryLineChart from '../../components/globalParts/PriceHistoryLineChart';
import VoteButtons from '../../components/globalParts/VoteButtons';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchPartRequestFn = (partId: string) =>
  globalPartsApi.getGlobalPart(Number(partId));

const fetchPartWithVotesRequestFn = (partId: string) =>
  globalPartVotesApi.getVoteSummary(Number(partId));

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchUserRequestFn = (userId: number) => usersApi.getUser(userId);

const fetchCarRequestFn = (carId: number) => carsApi.getCar(carId);

const fetchBrandRequestFn = (brandId: number) => brandsApi.getBrand(brandId);

const deletePartRequestFn = (partId: string) =>
  globalPartsApi.deleteGlobalPart(Number(partId));

const fetchListingsRequestFn = (partId: string) =>
  globalPartsApi.getGlobalPartListings(Number(partId));

const fetchPriceHistoryRequestFn = (partId: string) =>
  globalPartsApi.getGlobalPartPriceHistory(Number(partId));

function ViewGlobalPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditGlobalPartFormOpen, setIsEditGlobalPartFormOpen] =
    useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [partWithVotes, setPartWithVotes] =
    useState<GlobalPartReadWithVotes | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);
  const [car, setCar] = useState<CarRead | null>(null);
  const [brand, setBrand] = useState<BrandResponse | null>(null);

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  const {
    data: voteSummary,
    isLoading: isLoadingVotes,
    error: voteApiError,
    executeRequest: fetchVoteSummary,
  } = useApiRequest(fetchPartWithVotesRequestFn);

  const {
    data: categoriesData,
    isLoading: isLoadingCategories,
    error: categoriesApiError,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  const {
    data: itemOwner,
    isLoading: isLoadingOwner,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    data: carData,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const {
    data: brandData,
    isLoading: isLoadingBrand,
    error: brandApiError,
    executeRequest: fetchBrand,
  } = useApiRequest(fetchBrandRequestFn);

  const {
    isLoading: isDeletingPart,
    error: deletePartError,
    executeRequest: executeDeletePart,
    setError: setDeletePartError,
  } = useApiRequest(deletePartRequestFn);

  const {
    data: listingsData,
    isLoading: isLoadingListings,
    error: listingsApiError,
    executeRequest: fetchListings,
  } = useApiRequest(fetchListingsRequestFn);

  const {
    data: priceHistoryData,
    isLoading: isLoadingPriceHistory,
    error: priceHistoryApiError,
    executeRequest: fetchPriceHistory,
  } = useApiRequest(fetchPriceHistoryRequestFn);

  const memoizedFetchPart = useCallback(() => {
    if (partId) {
      void fetchPart(partId);
    }
  }, [fetchPart, partId]);

  const memoizedFetchVoteSummary = useCallback(() => {
    if (partId) {
      void fetchVoteSummary(partId);
    }
  }, [fetchVoteSummary, partId]);

  const memoizedFetchCategories = useCallback(() => {
    void fetchCategories(undefined);
  }, [fetchCategories]);

  const memoizedFetchUser = useCallback(() => {
    if (part?.user_id) {
      void fetchUser(part.user_id);
    }
  }, [fetchUser, part?.user_id]);

  const memoizedFetchCar = useCallback(() => {
    if (part?.car_id) {
      void fetchCar(part.car_id);
    } else {
      setCar(null);
    }
  }, [fetchCar, part?.car_id]);

  const memoizedFetchBrand = useCallback(() => {
    if (part?.brand_id) {
      void fetchBrand(part.brand_id);
    } else {
      setBrand(null);
    }
  }, [fetchBrand, part?.brand_id]);

  useEffect(() => {
    memoizedFetchPart();
    memoizedFetchVoteSummary();
    memoizedFetchCategories();
  }, [memoizedFetchPart, memoizedFetchVoteSummary, memoizedFetchCategories]);

  useEffect(() => {
    if (partId) {
      void fetchListings(partId);
    }
  }, [partId, fetchListings]);

  useEffect(() => {
    if (partId) {
      void fetchPriceHistory(partId);
    }
  }, [partId, fetchPriceHistory]);

  useEffect(() => {
    if (categoriesData) {
      setCategories(categoriesData);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (part && voteSummary) {
      setPartWithVotes({
        ...part,
        upvotes: voteSummary.upvotes,
        downvotes: voteSummary.downvotes,
        total_votes: voteSummary.total_votes,
        user_vote: voteSummary.user_vote ?? null,
      });
    }
  }, [part, voteSummary]);

  useEffect(() => {
    memoizedFetchUser();
  }, [memoizedFetchUser]);

  useEffect(() => {
    memoizedFetchCar();
  }, [memoizedFetchCar]);

  useEffect(() => {
    memoizedFetchBrand();
  }, [memoizedFetchBrand]);

  useEffect(() => {
    if (carData) {
      setCar(carData);
    }
  }, [carData]);

  useEffect(() => {
    if (brandData) {
      setBrand(brandData);
    }
  }, [brandData]);

  const handleGlobalPartUpdated = async () => {
    if (partId) {
      await fetchPart(partId); // Refresh part data
      await fetchVoteSummary(partId); // Refresh vote data
    }
    setIsEditGlobalPartFormOpen(false);
  };

  const handleVoteUpdate = (
    _partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    if (partWithVotes) {
      const currentVote = partWithVotes.user_vote;
      let upvotes = partWithVotes.upvotes;
      let downvotes = partWithVotes.downvotes;

      // Remove previous vote
      if (currentVote === 'upvote') upvotes--;
      if (currentVote === 'downvote') downvotes--;

      // Add new vote
      if (newVote === 'upvote') upvotes++;
      if (newVote === 'downvote') downvotes++;

      setPartWithVotes({
        ...partWithVotes,
        upvotes,
        downvotes,
        total_votes: upvotes + downvotes,
        user_vote: newVote,
      });
    }
  };

  const openEditGlobalPartDialog = () => setIsEditGlobalPartFormOpen(true);
  const closeEditGlobalPartDialog = () => setIsEditGlobalPartFormOpen(false);

  const openDeleteConfirmDialog = async () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);

    // Fetch build list count when opening the dialog
    if (part?.id) {
      try {
        const response =
          await buildListPartsApi.countBuildListsContainingGlobalPart(part.id);
        setBuildListCount(response.data.count);
      } catch {
        setBuildListCount(null);
      }
    }
  };
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const openReportDialog = () => setIsReportDialogOpen(true);
  const closeReportDialog = () => setIsReportDialogOpen(false);

  const openAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(true);
  const closeAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(false);

  const handlePartAddedToBuildList = () => {
    // Part added to build list
  };

  const handleConfirmDelete = async (): Promise<void> => {
    if (!part || !partId) return;

    const result = await executeDeletePart(partId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      void navigate('/global-parts'); // Navigate to global parts catalog
    }
  };

  const isLoading =
    isLoadingPart ||
    isLoadingVotes ||
    isLoadingCategories ||
    isLoadingOwner ||
    isLoadingCar ||
    isLoadingBrand;

  if (isLoading && !part) {
    return (
      <>
        <PageHeader title="Part Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (partApiError) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load part with ID "${partId}". ${partApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert message={`Part with ID "${partId}" not found.`} />
        </Card>
      </div>
    );
  }

  const canEdit =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);

  const canDelete =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);
  const category = categories.find((c) => c.id === part.category_id);

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={part.name} />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Part Information" />
          <div className="flex space-x-2">
            {currentUser && (
              <ActionButton
                onClick={openAddToBuildListDialog}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                📋 Add to Build List
              </ActionButton>
            )}
            {currentUser && (
              <ActionButton
                onClick={openReportDialog}
                className="bg-orange-600 hover:bg-orange-700 text-white"
              >
                Report
              </ActionButton>
            )}
            {canEdit && (
              <ActionButton onClick={openEditGlobalPartDialog}>
                Edit Part
              </ActionButton>
            )}
            {canDelete && (
              <ActionButton
                onClick={() => {
                  void openDeleteConfirmDialog();
                }}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Delete Part
              </ActionButton>
            )}
          </div>
        </div>

        {/* Car Association / Universal Parts Badge */}
        <div className="mb-6">
          {part.car_id && car ? (
            <div className="p-4 bg-indigo-900/20 border-2 border-indigo-500/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🚗</span>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-indigo-400 mb-1">
                    Car-Specific Part
                  </h3>
                  <p className="text-sm text-gray-300">
                    This part is designed for:{' '}
                    <Link
                      to={`/cars/${car.id}`}
                      className="font-semibold text-indigo-300 hover:text-indigo-200 underline transition-colors"
                    >
                      {car.make} {car.model} {car.generation_name} (
                      {car.start_year}
                      {car.end_year ? `-${car.end_year}` : '+'})
                    </Link>
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-indigo-900/20 border-2 border-indigo-500/50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🌐</span>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-indigo-400 mb-1">
                    Universal Part
                  </h3>
                  <p className="text-sm text-gray-300">
                    This part is not tied to a specific car and can be used with
                    any vehicle (wheels, tools, accessories, etc.)
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Voting Section */}
        {partWithVotes && (
          <div className="mb-6 p-4 bg-gray-800 rounded-lg">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">
                Community Rating
              </h3>
              <VoteButtons
                entityId={part.id}
                upvotes={partWithVotes.upvotes}
                downvotes={partWithVotes.downvotes}
                userVote={partWithVotes.user_vote ?? null}
                onVoteUpdate={handleVoteUpdate}
                voteApi={{
                  voteOnEntity: (id, data) =>
                    globalPartVotesApi.voteOnGlobalPart(id, data),
                  removeVote: (id) => globalPartVotesApi.removeVote(id),
                }}
                size="lg"
              />
            </div>
          </div>
        )}

        {/* Part Images - full width */}
        <div className="mb-6">
          <CardInfoItem label="Part Images">
            <ImageGallery
              imageUrl={part.image_url ?? null}
              imageUrls={part.image_urls ?? null}
              altText={part.name}
            />
          </CardInfoItem>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          {part.description && (
            <CardInfoItem label="Description:">
              <p className="whitespace-pre-wrap">{part.description}</p>
            </CardInfoItem>
          )}
          {category && (
            <CardInfoItem label="Category:">
              <Link
                to={
                  part.car_id
                    ? `/global-parts?mode=category_car&category_id=${category.id}&car_id=${part.car_id}`
                    : `/global-parts?mode=category_car&category_id=${category.id}`
                }
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {category.display_name}
              </Link>
            </CardInfoItem>
          )}
          {brand && (
            <CardInfoItem label="Brand:">
              <Link
                to={`/global-parts?mode=brand&brand_id=${brand.id}`}
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {brand.name}
              </Link>
            </CardInfoItem>
          )}
          {part.part_number && (
            <CardInfoItem label="Part Number:">
              <p>{part.part_number}</p>
            </CardInfoItem>
          )}
          {part.price !== null && part.price !== undefined && (
            <CardInfoItem label="Price:">
              <p>
                $
                {(part.price / 100).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </p>
            </CardInfoItem>
          )}
          {part.specifications &&
            Object.keys(part.specifications).length > 0 && (
              <CardInfoItem label="Specifications:">
                <div className="space-y-1">
                  {Object.entries(part.specifications).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="font-medium">{key}:</span>
                      <span>{String(value)}</span>
                    </div>
                  ))}
                </div>
              </CardInfoItem>
            )}
          <CardInfoItem label="Status:">
            <div className="flex items-center space-x-2">
              {part.is_verified && (
                <span className="text-green-400 text-sm">✓ Verified</span>
              )}
              <span className="text-gray-400 text-sm">
                Source: {part.source}
              </span>
            </div>
          </CardInfoItem>
          <CardInfoItem label="Edit History:">
            <p>{part.edit_count} edits</p>
          </CardInfoItem>
          {itemOwner && (
            <CardInfoItem label="Created by:">
              <ParentNavigationLink
                linkTo={`/user/${itemOwner.id}`}
                linkText={itemOwner.username}
              />
            </CardInfoItem>
          )}
          <CardInfoItem label="Created:">
            <p>{new Date(part.created_at).toLocaleDateString()}</p>
          </CardInfoItem>
          <CardInfoItem label="Last Updated:">
            <p>{new Date(part.updated_at).toLocaleDateString()}</p>
          </CardInfoItem>
        </div>

        {/* Price by retailer */}
        <div className="mb-6">
          <SectionHeader title="Price by retailer" />
          {isLoadingListings && (
            <p className="text-gray-400 text-sm">Loading retailer prices…</p>
          )}
          {listingsApiError && (
            <ErrorAlert
              message={`Could not load retailer prices: ${listingsApiError}`}
            />
          )}
          {!isLoadingListings && !listingsApiError && listingsData && (
            <>
              {listingsData.length === 0 ? (
                <p className="text-gray-400 text-sm">
                  No retailer listings with price for this part yet.
                </p>
              ) : (
                <ul className="space-y-3">
                  {listingsData
                    .filter(
                      (l: PartListingReadWithRetailer) =>
                        l.last_known_price_cents != null
                    )
                    .sort(
                      (
                        a: PartListingReadWithRetailer,
                        b: PartListingReadWithRetailer
                      ) =>
                        (a.last_known_price_cents ?? 0) -
                        (b.last_known_price_cents ?? 0)
                    )
                    .map((listing: PartListingReadWithRetailer) => (
                      <li
                        key={listing.id}
                        className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-800/60 rounded-lg border border-gray-700/50"
                      >
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-white">
                            {listing.retailer.name}
                          </span>
                          {listing.last_price_updated_at && (
                            <span className="text-gray-400 text-sm ml-2">
                              (updated{' '}
                              {new Date(
                                listing.last_price_updated_at
                              ).toLocaleDateString()}
                              )
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-emerald-400 font-semibold">
                            $
                            {(
                              (listing.last_known_price_cents ?? 0) / 100
                            ).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </span>
                          {listing.product_url && (
                            <a
                              href={listing.product_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-400 hover:text-primary-300 text-sm underline"
                            >
                              View at retailer →
                            </a>
                          )}
                        </div>
                      </li>
                    ))}
                </ul>
              )}
            </>
          )}
        </div>

        {/* Price history */}
        <div className="mb-6">
          <SectionHeader title="Price history" />
          {isLoadingPriceHistory && (
            <p className="text-gray-400 text-sm">Loading price history…</p>
          )}
          {priceHistoryApiError && (
            <ErrorAlert
              message={`Could not load price history: ${priceHistoryApiError}`}
            />
          )}
          {!isLoadingPriceHistory &&
            !priceHistoryApiError &&
            priceHistoryData && (
              <>
                {priceHistoryData.length === 0 ? (
                  <p className="text-gray-400 text-sm">
                    No price history recorded for this part yet.
                  </p>
                ) : (
                  <div className="rounded-lg border border-gray-700/50 bg-gray-800/30 p-4">
                    <PriceHistoryLineChart data={priceHistoryData} />
                  </div>
                )}
              </>
            )}
        </div>

        {voteApiError && (
          <ErrorAlert message={`Error loading vote data: ${voteApiError}`} />
        )}
        {categoriesApiError && (
          <ErrorAlert
            message={`Error loading category data: ${categoriesApiError}`}
          />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading creator information: ${ownerApiError}`}
          />
        )}
        {carApiError && (
          <ErrorAlert
            message={`Error loading car information: ${carApiError}`}
          />
        )}
        {brandApiError && (
          <ErrorAlert
            message={`Error loading brand information: ${brandApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canEdit && (
        <Dialog
          isOpen={isEditGlobalPartFormOpen}
          onClose={closeEditGlobalPartDialog}
          title={`Edit ${part.name}`}
        >
          <EditGlobalPartForm
            globalPart={part}
            onGlobalPartUpdated={handleGlobalPartUpdated}
            onCancel={closeEditGlobalPartDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Part Confirmation */}
      {part && canDelete && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={() => void handleConfirmDelete()}
          itemName={part.name}
          itemType="part"
          isProcessing={isDeletingPart}
          error={deletePartError}
          buildListCount={buildListCount !== null ? buildListCount : undefined}
        />
      )}

      {/* Dialog for Reporting Part */}
      {part && (
        <ReportDialog
          isOpen={isReportDialogOpen}
          onClose={closeReportDialog}
          partId={part.id}
          partName={part.name}
        />
      )}

      {/* Dialog for Adding to Build List */}
      {partWithVotes && (
        <AddToBuildListDialog
          isOpen={isAddToBuildListDialogOpen}
          onClose={closeAddToBuildListDialog}
          globalPart={partWithVotes}
          onPartAdded={handlePartAddedToBuildList}
        />
      )}
    </div>
  );
}

export default ViewGlobalPart;
