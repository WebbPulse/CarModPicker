import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi, globalPartsApi } from '../../services/Api';
import type { GlobalPartRead } from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import SecondaryButton from '../../components/buttons/SecondaryButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

function UserGlobalParts() {
  const location = useLocation();
  const { user } = useAuth();
  const [deletingPartId, setDeletingPartId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);

  // Note: Backend doesn't have a dedicated endpoint for user's global parts
  // We can use the main endpoint with search or filter by user_id on the frontend
  const fetchUserGlobalPartsRequestFn = useCallback(
    () => globalPartsApi.getGlobalParts({ limit: 1000 }),
    []
  );

  const {
    data: globalParts,
    isLoading,
    error,
    executeRequest: fetchUserGlobalParts,
  } = useApiRequest(fetchUserGlobalPartsRequestFn);

  useEffect(() => {
    if (user) {
      void fetchUserGlobalParts();
    }
  }, [user, fetchUserGlobalParts]);

  const handleDelete = async (partId: number) => {
    setIsDeleting(true);
    try {
      await globalPartsApi.deleteGlobalPart(partId);
      // Refresh the list
      if (user) {
        await fetchUserGlobalParts();
      }
    } catch (error) {
      console.error('Failed to delete global part:', error);
    } finally {
      setIsDeleting(false);
      setDeletingPartId(null);
    }
  };

  const canDeleteGlobalPart = (globalPart: GlobalPartRead) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  const canEditGlobalPart = (globalPart: GlobalPartRead) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="My Parts" />
        <Card>
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader title="My Parts" />
        <ErrorAlert message="Failed to load your parts. Please try again." />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="My Parts" />

      {/* Tab Navigation */}
      <div className="mb-6">
        <div className="flex space-x-1 bg-gray-800 p-1 rounded-lg border border-gray-700">
          <Link
            to="/global-parts"
            className={`flex-1 text-center px-4 py-2 rounded-md font-medium transition-all duration-200 ${
              location.pathname === '/global-parts'
                ? 'bg-primary-600 text-white shadow-lg'
                : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            Parts Catalog
          </Link>
          <Link
            to="/my-global-parts"
            className={`flex-1 text-center px-4 py-2 rounded-md font-medium transition-all duration-200 ${
              location.pathname === '/my-global-parts'
                ? 'bg-primary-600 text-white shadow-lg'
                : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            My Parts
          </Link>
        </div>
      </div>

      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Parts I Created" />
          <Link to="/global-parts">
            <ActionButton>Browse All Parts</ActionButton>
          </Link>
        </div>

        {!globalParts ||
        globalParts.filter((part) => user && part.user_id === user.id)
          .length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>You haven't created any parts yet.</p>
            <p className="text-sm mt-2">
              Parts you create will appear here and can be added to build lists
              by other users.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {globalParts
              .filter((part) => user && part.user_id === user.id)
              .map((globalPart) => (
                <div
                  key={globalPart.id}
                  className="bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500 transition-colors"
                >
                  <div className="flex flex-row items-center gap-4 p-3">
                    {/* Image */}
                    <Link
                      to={`/global-parts/${globalPart.id}`}
                      className="flex-shrink-0"
                    >
                      <div className="w-20 h-20">
                        <ImageWithPlaceholder
                          srcUrl={globalPart.image_url ?? null}
                          altText={globalPart.name}
                          imageClassName="w-full h-full object-cover rounded"
                          containerClassName="w-full h-full flex justify-center items-center"
                          fallbackText="No image"
                        />
                      </div>
                    </Link>

                    {/* Main Content */}
                    <div className="flex-grow min-w-0">
                      <Link
                        to={`/global-parts/${globalPart.id}`}
                        className="block hover:no-underline"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-grow min-w-0">
                            <h3 className="text-base font-semibold text-gray-200 mb-1 truncate">
                              {globalPart.name}
                            </h3>
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                              {globalPart.brand && (
                                <span className="text-gray-400">
                                  <span className="text-gray-500">Brand:</span>{' '}
                                  {globalPart.brand}
                                </span>
                              )}
                              {globalPart.part_number && (
                                <span className="text-gray-400">
                                  <span className="text-gray-500">P/N:</span>{' '}
                                  {globalPart.part_number}
                                </span>
                              )}
                            </div>
                            {globalPart.description && (
                              <p className="text-sm text-gray-400 mt-1 line-clamp-1">
                                {globalPart.description}
                              </p>
                            )}
                          </div>
                          {globalPart.price !== null &&
                            globalPart.price !== undefined && (
                              <div className="flex-shrink-0 text-right">
                                <p className="text-base font-semibold text-green-400">
                                  ${globalPart.price.toFixed(2)}
                                </p>
                              </div>
                            )}
                        </div>
                      </Link>

                      {/* Action Buttons */}
                      <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-gray-700">
                        {canEditGlobalPart(globalPart) && (
                          <Link to={`/global-parts/${globalPart.id}/edit`}>
                            <SecondaryButton className="text-xs px-3 py-1">
                              Edit
                            </SecondaryButton>
                          </Link>
                        )}
                        {canDeleteGlobalPart(globalPart) && (
                          <ActionButton
                            onClick={() => {
                              setDeletingPartId(globalPart.id);
                              // Fetch build list count when opening the dialog
                              void (async () => {
                                try {
                                  const response =
                                    await buildListPartsApi.countBuildListsContainingGlobalPart(
                                      globalPart.id
                                    );
                                  setBuildListCount(response.data.count);
                                } catch (error) {
                                  console.error(
                                    'Failed to fetch build list count:',
                                    error
                                  );
                                  setBuildListCount(null);
                                }
                              })();
                            }}
                            className="text-xs px-3 py-1 bg-red-600 hover:bg-red-700"
                            disabled={isDeleting}
                          >
                            Delete
                          </ActionButton>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        )}
      </Card>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={deletingPartId !== null}
        onClose={() => {
          setDeletingPartId(null);
          setBuildListCount(null);
        }}
        onConfirm={() => {
          if (deletingPartId) {
            void handleDelete(deletingPartId);
          }
        }}
        itemName={globalParts?.find((p) => p.id === deletingPartId)?.name || ''}
        itemType="part"
        isProcessing={isDeleting}
        error={null}
        buildListCount={buildListCount !== null ? buildListCount : undefined}
      />
    </div>
  );
}

export default UserGlobalParts;
