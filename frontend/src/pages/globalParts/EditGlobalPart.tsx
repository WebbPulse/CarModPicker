import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { globalPartsApi } from '../../services/Api';

import SecondaryButton from '../../components/buttons/SecondaryButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EditGlobalPartForm from '../../components/globalParts/EditGlobalPartForm';
import PageHeader from '../../components/layout/PageHeader';

const fetchPartRequestFn = (partId: string) =>
  globalPartsApi.getGlobalPart(Number(partId));

function EditGlobalPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  useEffect(() => {
    if (partId) {
      void fetchPart(partId);
    }
  }, [partId, fetchPart]);

  const handlePartUpdated = async () => {
    if (partId) {
      await fetchPart(partId);
      // Navigate back to the part view page
      void navigate(`/global-parts/${partId}`);
    }
  };

  const handleCancel = () => {
    if (partId) {
      void navigate(`/global-parts/${partId}`);
    } else {
      void navigate('/global-parts');
    }
  };

  if (isLoadingPart) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        </Card>
      </div>
    );
  }

  if (partApiError) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message={`Failed to load part: ${partApiError}`} />
          <div className="mt-4">
            <SecondaryButton onClick={handleCancel}>Go Back</SecondaryButton>
          </div>
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="Part not found." />
          <div className="mt-4">
            <SecondaryButton onClick={handleCancel}>Go Back</SecondaryButton>
          </div>
        </Card>
      </div>
    );
  }

  // Check if user can edit this part
  const canEdit =
    currentUser &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);

  if (!canEdit) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="You don't have permission to edit this part." />
          <div className="mt-4">
            <SecondaryButton onClick={handleCancel}>Go Back</SecondaryButton>
          </div>
        </Card>
      </div>
    );
  }

  // Safety check - ensure part has required fields
  if (!part || !part.id || !part.name) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="Invalid part data received. Please try again." />
          <div className="mt-4">
            <SecondaryButton onClick={handleCancel}>Go Back</SecondaryButton>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={`Edit ${part.name}`} />
      <Card>
        <EditGlobalPartForm
          globalPart={part}
          onGlobalPartUpdated={handlePartUpdated}
          onCancel={handleCancel}
        />
      </Card>
    </div>
  );
}

export default EditGlobalPart;
