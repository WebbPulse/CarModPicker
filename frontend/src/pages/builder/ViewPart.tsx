import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import {
  partManufacturersApi,
  buildListPartsApi,
  carGenerationsApi,
  categoriesApi,
  partsApi,
  partVotesApi,
  usersApi,
} from '../../services/Api';
import { formatCarYearRange, normalizeCarReadList } from '../../utils/carUtils';
import type {
  CarGenerationRead,
  PartReadWithVotes,
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
import AddToBuildListDialog from '../../components/parts/AddToBuildListDialog';
import EditPartForm from '../../components/parts/EditPartForm';
import ImageGallery from '../../components/parts/ImageGallery';
import ImageGalleryManage from '../../components/parts/ImageGalleryManage';
import PriceHistoryLineChart from '../../components/parts/PriceHistoryLineChart';
import VoteButtons from '../../components/parts/VoteButtons';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchPartRequestFn = (partId: string) => partsApi.getPart(partId);

const fetchPartWithVotesRequestFn = (partId: string) =>
  partVotesApi.getVoteSummary(partId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchUserRequestFn = (userId: string) => usersApi.getUser(userId);

const fetchPartManufacturerRequestFn = (part_manufacturerId: string) =>
  partManufacturersApi.getPartManufacturer(part_manufacturerId);

const deletePartRequestFn = (partId: string) => partsApi.deletePart(partId);

const fetchListingsRequestFn = (partId: string) =>
  partsApi.getPartListings(partId);

const fetchPriceHistoryRequestFn = (partId: string) =>
  partsApi.getPartPriceHistory(partId);

function ViewPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditPartFormOpen, setIsEditPartFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);
  const [compatibleCars, setCompatibleCars] = useState<CarGenerationRead[]>([]);
  const [isLoadingCompatibleCars, setIsLoadingCompatibleCars] = useState(false);
  const [voteOverride, setVoteOverride] = useState<{
    upvotes: number;
    downvotes: number;
    user_vote: 'upvote' | 'downvote' | null;
  } | null>(null);

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
    data: part_manufacturerData,
    isLoading: isLoadingPartManufacturer,
    error: part_manufacturerApiError,
    executeRequest: fetchPartManufacturer,
  } = useApiRequest(fetchPartManufacturerRequestFn);

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

  // Fetch all primary data when partId changes
  useEffect(() => {
    if (!partId) return;
    void fetchPart(partId);
    void fetchVoteSummary(partId);
    void fetchCategories(undefined);
    void fetchListings(partId);
    void fetchPriceHistory(partId);
  }, [
    partId,
    fetchPart,
    fetchVoteSummary,
    fetchCategories,
    fetchListings,
    fetchPriceHistory,
  ]);

  // Fetch dependent data when part loads
  useEffect(() => {
    if (part?.user_id) {
      void fetchUser(part.user_id);
    }
    if (part?.part_manufacturer_id) {
      void fetchPartManufacturer(part.part_manufacturer_id);
    }
  }, [
    part?.user_id,
    part?.part_manufacturer_id,
    fetchUser,
    fetchPartManufacturer,
  ]);

  // Fetch compatible cars when part has car_ids
  useEffect(() => {
    const carIds = part?.car_ids ?? [];
    if (carIds.length === 0) {
      setCompatibleCars([]);
      setIsLoadingCompatibleCars(false);
      return;
    }
    let cancelled = false;
    setIsLoadingCompatibleCars(true);
    Promise.all(carIds.map((id) => carGenerationsApi.getCar(id)))
      .then((responses) => {
        if (!cancelled) {
          setCompatibleCars(
            normalizeCarReadList(responses.map((r) => r.data).filter(Boolean))
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCompatibleCars([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingCompatibleCars(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [part?.car_ids]);

  const partWithVotes = useMemo<PartReadWithVotes | null>(() => {
    if (!part || !voteSummary) return null;
    const votes = voteOverride ?? voteSummary;
    return {
      ...part,
      upvotes: votes.upvotes,
      downvotes: votes.downvotes,
      total_votes: votes.upvotes + votes.downvotes,
      user_vote: votes.user_vote ?? null,
    };
  }, [part, voteSummary, voteOverride]);

  const categories = categoriesData ?? [];
  const part_manufacturer = part_manufacturerData ?? null;

  const handlePartUpdated = async () => {
    if (partId) {
      await fetchPart(partId); // Refresh part data
      await fetchVoteSummary(partId); // Refresh vote data
    }
    setIsEditPartFormOpen(false);
  };

  const handleVoteUpdate = (
    _partId: string,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    if (!partWithVotes) return;
    const currentVote = partWithVotes.user_vote;
    let upvotes = partWithVotes.upvotes;
    let downvotes = partWithVotes.downvotes;

    if (currentVote === 'upvote') upvotes--;
    if (currentVote === 'downvote') downvotes--;
    if (newVote === 'upvote') upvotes++;
    if (newVote === 'downvote') downvotes++;

    setVoteOverride({ upvotes, downvotes, user_vote: newVote });
  };

  const openEditPartDialog = () => setIsEditPartFormOpen(true);
  const closeEditPartDialog = () => setIsEditPartFormOpen(false);

  const openDeleteConfirmDialog = async () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);

    // Fetch build list count when opening the dialog
    if (part?.id) {
      try {
        const response = await buildListPartsApi.countBuildListsContainingPart(
          part.id
        );
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
      void navigate('/parts'); // Navigate to global parts catalog
    }
  };

  const isLoading =
    isLoadingPart ||
    isLoadingVotes ||
    isLoadingCategories ||
    isLoadingOwner ||
    isLoadingCompatibleCars ||
    isLoadingPartManufacturer;

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
              <ActionButton onClick={openEditPartDialog}>
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
                  voteOnEntity: (id, data) => partVotesApi.voteOnPart(id, data),
                  removeVote: (id) => partVotesApi.removeVote(id),
                }}
                size="lg"
              />
            </div>
          </div>
        )}

        {/* Part images (left half) + description (right half) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 items-start">
          <div className="min-w-0">
            <CardInfoItem label="Part Images">
              {canEdit ? (
                <ImageGalleryManage
                  imageUrls={part.image_urls ?? null}
                  altText={part.name}
                  partId={part.id}
                  onPartUpdated={handlePartUpdated}
                  layout="hero"
                />
              ) : (
                <ImageGallery
                  imageUrls={part.image_urls ?? null}
                  altText={part.name}
                  layout="hero"
                />
              )}
            </CardInfoItem>
          </div>
          <div className="min-w-0">
            {part.description ? (
              <CardInfoItem label="Description">
                <p className="whitespace-pre-wrap text-gray-300">
                  {part.description}
                </p>
              </CardInfoItem>
            ) : (
              <CardInfoItem label="Description">
                <p className="text-gray-500 italic">No description.</p>
              </CardInfoItem>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          {category && (
            <CardInfoItem label="Category:">
              <Link
                to={
                  part.car_ids?.length
                    ? `/parts?mode=category_car&category_id=${category.id}&car_id=${part.car_ids[0]}`
                    : `/parts?mode=category_car&category_id=${category.id}`
                }
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {category.display_name}
              </Link>
            </CardInfoItem>
          )}
          {part_manufacturer && (
            <CardInfoItem label="PartManufacturer:">
              <Link
                to={`/parts?mode=part_manufacturer&part_manufacturer_id=${part_manufacturer.id}`}
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {part_manufacturer.name}
              </Link>
            </CardInfoItem>
          )}
          {part.part_number && (
            <CardInfoItem label="Part Number:">
              <p>{part.part_number}</p>
            </CardInfoItem>
          )}
          {part.best_price_cents != null && (
            <CardInfoItem label="From:">
              <p>
                $
                {(part.best_price_cents / 100).toLocaleString(undefined, {
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
          {itemOwner && !itemOwner.is_service_account && (
            <CardInfoItem label="Created by:">
              <ParentNavigationLink
                linkTo={`/user/${itemOwner.id}`}
                linkText={itemOwner.username}
              />
            </CardInfoItem>
          )}
          <CardInfoItem
            label="Fits:"
            className={
              !part.is_universal && (part.car_ids?.length ?? 0) > 1
                ? 'md:col-span-2'
                : ''
            }
          >
            {part.is_universal ? (
              <p>Universal (all vehicles)</p>
            ) : isLoadingCompatibleCars ? (
              <p className="text-gray-400">Loading…</p>
            ) : compatibleCars.length > 0 ? (
              <ul className="space-y-1">
                {compatibleCars.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/car-generations/${c.id}`}
                      className="text-blue-400 hover:text-blue-300 underline transition-colors"
                    >
                      {c.car_make_name} {c.car_model_name} {c.generation_name} (
                      {formatCarYearRange(c.start_year, c.end_year)})
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500 italic">Not linked to any car yet.</p>
            )}
          </CardInfoItem>
          <CardInfoItem label="Created:">
            <p>{new Date(part.created_at).toLocaleDateString()}</p>
          </CardInfoItem>
          <CardInfoItem label="Last Updated:">
            <p>{new Date(part.updated_at).toLocaleDateString()}</p>
          </CardInfoItem>
        </div>

        {/* Price history (left) + Price by retailer (right) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 items-start">
          {/* Price history - left */}
          <div className="min-w-0">
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

          {/* Price by retailer - right */}
          <div className="min-w-0">
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
        {part_manufacturerApiError && (
          <ErrorAlert
            message={`Error loading part_manufacturer information: ${part_manufacturerApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canEdit && (
        <Dialog
          isOpen={isEditPartFormOpen}
          onClose={closeEditPartDialog}
          title={`Edit ${part.name}`}
        >
          <EditPartForm
            part={part}
            onPartUpdated={handlePartUpdated}
            onCancel={closeEditPartDialog}
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
          part={partWithVotes}
          onPartAdded={handlePartAddedToBuildList}
        />
      )}
    </div>
  );
}

export default ViewPart;
