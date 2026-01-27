import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi, globalPartsApi } from '../../services/Api';
import type { GlobalPartReadWithVotes } from '../../types/Api';

import LinkButton from '../../components/buttons/LinkButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import GlobalPartList from '../../components/globalParts/GlobalPartList';
import PageHeader from '../../components/layout/PageHeader';
import { CACHE_DURATION_MS, LARGE_FETCH_LIMIT } from '../../constants';

// Cache for user's global parts to improve UX when switching tabs
let cachedUserParts: GlobalPartReadWithVotes[] | null = null;
let cachedUserPartsTimestamp = 0;

function UserGlobalParts() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [deletingPartId, setDeletingPartId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);

  // Fetch global parts with votes
  const fetchUserGlobalPartsRequestFn = useCallback(
    () => globalPartsApi.getGlobalPartsWithVotes({ limit: LARGE_FETCH_LIMIT }),
    []
  );

  const {
    data: globalPartsResponse,
    error,
    executeRequest: fetchUserGlobalParts,
  } = useApiRequest(fetchUserGlobalPartsRequestFn);

  // Initialize with cached data if available
  const [displayData, setDisplayData] = useState<GlobalPartReadWithVotes[]>(
    () => {
      if (
        user &&
        cachedUserParts &&
        Date.now() - cachedUserPartsTimestamp < CACHE_DURATION_MS
      ) {
        return cachedUserParts.filter((part) => part.user_id === user.id);
      }
      return [];
    }
  );

  useEffect(() => {
    if (user) {
      // Check cache first
      if (
        cachedUserParts &&
        Date.now() - cachedUserPartsTimestamp < CACHE_DURATION_MS
      ) {
        setDisplayData(
          cachedUserParts.filter((part) => part.user_id === user.id)
        );
      }
      // Always fetch fresh data in background
      void fetchUserGlobalParts();
    }
  }, [user, fetchUserGlobalParts]);

  // Update display data when fresh data arrives
  useEffect(() => {
    if (globalPartsResponse?.data) {
      // Update cache
      cachedUserParts = globalPartsResponse.data;
      cachedUserPartsTimestamp = Date.now();
      // Update display
      if (user) {
        setDisplayData(
          globalPartsResponse.data.filter((part) => part.user_id === user.id)
        );
      }
    }
  }, [globalPartsResponse?.data, user]);

  // Filter parts by user_id (use displayData which may come from cache)
  const userGlobalParts = useMemo(() => {
    if (!user) return [];
    // If we have fresh response data, use that, otherwise use cached displayData
    if (globalPartsResponse?.data) {
      return globalPartsResponse.data.filter(
        (part) => part.user_id === user.id
      );
    }
    return displayData;
  }, [globalPartsResponse?.data, user, displayData]);

  const handleDelete = async (part: GlobalPartReadWithVotes) => {
    setIsDeleting(true);
    try {
      await globalPartsApi.deleteGlobalPart(part.id);
      // Clear cache and refresh the list
      cachedUserParts = null;
      cachedUserPartsTimestamp = 0;
      if (user) {
        await fetchUserGlobalParts();
      }
      setDeletingPartId(null);
    } catch {
      // Failed to delete global part
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteClick = (part: GlobalPartReadWithVotes) => {
    setDeletingPartId(part.id);
    // Fetch build list count when opening the dialog
    void (async () => {
      try {
        const response =
          await buildListPartsApi.countBuildListsContainingGlobalPart(part.id);
        setBuildListCount(response.data.count);
      } catch {
        setBuildListCount(null);
      }
    })();
  };

  const handleEdit = (part: GlobalPartReadWithVotes) => {
    void navigate(`/global-parts/${part.id}/edit`);
  };

  const canDeleteGlobalPart = (globalPart: GlobalPartReadWithVotes) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  const canEditGlobalPart = (globalPart: GlobalPartReadWithVotes) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header with Browse All Parts button */}
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="My Parts" />
        <LinkButton to="/global-parts" variant="outline" size="md">
          Browse All Parts
        </LinkButton>
      </div>

      {error && displayData.length === 0 ? (
        <Card>
          <ErrorAlert message="Failed to load your parts. Please try again." />
        </Card>
      ) : (
        <GlobalPartList
          data={userGlobalParts}
          title="Parts I Created"
          emptyMessage="You haven't created any parts yet. Parts you create will appear here and can be added to build lists by other users."
          showVoteButtons={true}
          onVoteUpdate={() => {
            // Refresh votes if needed
            void fetchUserGlobalParts();
          }}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          canEdit={canEditGlobalPart}
          canDelete={canDeleteGlobalPart}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={deletingPartId !== null}
        onClose={() => {
          setDeletingPartId(null);
          setBuildListCount(null);
        }}
        onConfirm={() => {
          if (deletingPartId) {
            const part = userGlobalParts.find((p) => p.id === deletingPartId);
            if (part) {
              void handleDelete(part);
            }
          }
        }}
        itemName={
          userGlobalParts.find((p) => p.id === deletingPartId)?.name || ''
        }
        itemType="part"
        isProcessing={isDeleting}
        error={null}
        buildListCount={buildListCount !== null ? buildListCount : undefined}
      />
    </div>
  );
}

export default UserGlobalParts;
