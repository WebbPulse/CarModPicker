import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DangerousActionDialog from '../../components/common/DangerousActionDialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import {
  buildListsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
  imageApi,
  usersApi,
} from '../../services/Api';

interface EntityCounts {
  users: number | null;
  cars: number | null;
  buildLists: number | null;
  globalParts: number | null;
  categories: number | null;
  bucketObjects: number | null;
}

function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [counts, setCounts] = useState<EntityCounts>({
    users: null,
    cars: null,
    buildLists: null,
    globalParts: null,
    categories: null,
    bucketObjects: null,
  });
  const [isLoadingCounts, setIsLoadingCounts] = useState(true);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [isDeleteAllDialogOpen, setIsDeleteAllDialogOpen] = useState(false);
  const [isDeletingAllCars, setIsDeletingAllCars] = useState(false);
  const [deleteAllError, setDeleteAllError] = useState<string | null>(null);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  // Fetch entity counts function
  const fetchCounts = useCallback(async () => {
    if (!user?.is_admin) return;

    setIsLoadingCounts(true);
    setCountsError(null);

    const failedEndpoints: string[] = [];

    const fetchCount = async (
      apiCall: () => Promise<{ data: { count: number } }>,
      entityName: string
    ): Promise<number | null> => {
      try {
        const response = await apiCall();
        return response.data.count;
      } catch {
        failedEndpoints.push(entityName);
        return null;
      }
    };

    try {
      // Fetch all counts in parallel, but handle failures individually
      const [
        usersCount,
        carsCount,
        buildListsCount,
        globalPartsCount,
        categoriesCount,
        bucketObjectsCount,
      ] = await Promise.all([
        fetchCount(() => usersApi.countUsers(), 'users'),
        fetchCount(() => carsApi.countCars(), 'cars'),
        fetchCount(() => buildListsApi.countBuildLists(), 'build lists'),
        fetchCount(() => globalPartsApi.countGlobalParts(), 'global parts'),
        fetchCount(() => categoriesApi.countCategories(), 'categories'),
        fetchCount(() => imageApi.countBucketObjects(), 'bucket objects'),
      ]);

      setCounts({
        users: usersCount,
        cars: carsCount,
        buildLists: buildListsCount,
        globalParts: globalPartsCount,
        categories: categoriesCount,
        bucketObjects: bucketObjectsCount,
      });

      // Show error only if all requests failed
      const allFailed =
        usersCount === null &&
        carsCount === null &&
        buildListsCount === null &&
        globalPartsCount === null &&
        categoriesCount === null &&
        bucketObjectsCount === null;

      if (allFailed) {
        setCountsError(
          'Failed to load statistics. Please check your connection and try refreshing the page.'
        );
      } else if (failedEndpoints.length > 0) {
        // Some failed, show a warning
        setCountsError(
          `Some statistics could not be loaded: ${failedEndpoints.join(', ')}. Other data is shown below.`
        );
      } else {
        // All succeeded, clear any previous errors
        setCountsError(null);
      }
    } catch {
      setCountsError(
        'An unexpected error occurred. Please try refreshing the page.'
      );
    } finally {
      setIsLoadingCounts(false);
    }
  }, [user]);

  // Fetch entity counts on mount
  useEffect(() => {
    void fetchCounts();
  }, [fetchCounts]);

  const handleDeleteAllCars = async () => {
    setIsDeletingAllCars(true);
    setDeleteAllError(null);

    try {
      await carsApi.deleteAllCars();
      setIsDeleteAllDialogOpen(false);
      // Refresh counts after deletion
      await fetchCounts();
    } catch (error) {
      setDeleteAllError(
        error instanceof Error ? error.message : 'Failed to delete all cars.'
      );
    } finally {
      setIsDeletingAllCars(false);
    }
  };

  if (!user) {
    return (
      <div>
        <PageHeader title="Admin Dashboard" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Admin Dashboard" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  const adminFeatures = [
    {
      title: 'Car Management',
      description:
        'Edit and manage car generations (primarily for editing existing cars)',
      icon: '🚗',
      path: '/admin/cars',
    },
    {
      title: 'Category Management',
      description: 'Create, edit, and manage part categories',
      icon: '📂',
      path: '/admin/categories',
    },
    {
      title: 'User Management',
      description: 'View and manage user accounts',
      icon: '👥',
      path: '/admin/users',
    },
    {
      title: 'Report Review',
      description: 'Review and manage part reports',
      icon: '🚨',
      path: '/admin/reports',
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Admin Dashboard"
        subtitle="Manage CarModPicker system settings and content"
      />

      <Card>
        <SectionHeader title="Admin Functions" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {adminFeatures.map((feature) => (
            <div
              key={feature.path}
              className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3 mb-2">
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="text-lg font-semibold text-gray-200">
                  {feature.title}
                </h3>
              </div>
              <p className="text-gray-400 mb-3">{feature.description}</p>
              <ActionButton
                onClick={() => void navigate(feature.path)}
                className="w-full"
              >
                Access {feature.title}
              </ActionButton>
            </div>
          ))}
        </div>
      </Card>

      <div className="mt-6">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <SectionHeader title="System Statistics" />
            {!isLoadingCounts && (
              <ActionButton
                onClick={() => void fetchCounts()}
                className="text-sm"
              >
                Refresh
              </ActionButton>
            )}
          </div>
          {countsError && (
            <div className="mb-4">
              <ErrorAlert message={countsError} />
            </div>
          )}
          {isLoadingCounts ? (
            <div className="flex justify-center items-center py-8">
              <LoadingSpinner />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Users</div>
                <div className="text-3xl font-bold text-blue-400">
                  {counts.users?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Cars</div>
                <div className="text-3xl font-bold text-green-400">
                  {counts.cars?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Build Lists</div>
                <div className="text-3xl font-bold text-yellow-400">
                  {counts.buildLists?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Global Parts</div>
                <div className="text-3xl font-bold text-purple-400">
                  {counts.globalParts?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Categories</div>
                <div className="text-3xl font-bold text-pink-400">
                  {counts.categories?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Bucket Objects</div>
                <div className="text-3xl font-bold text-cyan-400">
                  {counts.bucketObjects?.toLocaleString() ?? '—'}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <SectionHeader title="Dangerous Actions" />
          <div className="p-6 bg-red-900/20 border-2 border-red-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-red-400 mb-2">
                Delete All Cars
              </h3>
              <p className="text-neutral-300 mb-4">
                This will permanently delete all cars from the system. This
                action cannot be undone. Cars with associated build lists cannot
                be deleted.
              </p>
              <p className="text-sm text-neutral-400 mb-4">
                Current car count:{' '}
                <span className="font-semibold text-white">
                  {counts.cars?.toLocaleString() ?? '—'}
                </span>
              </p>
            </div>
            <ActionButton
              onClick={() => setIsDeleteAllDialogOpen(true)}
              className="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white"
            >
              🗑️ Delete All Cars
            </ActionButton>
          </div>
        </Card>
      </div>

      <DangerousActionDialog
        isOpen={isDeleteAllDialogOpen}
        onClose={() => {
          setIsDeleteAllDialogOpen(false);
          setDeleteAllError(null);
        }}
        onConfirm={() => void handleDeleteAllCars()}
        actionName="Delete All Cars"
        confirmationPhrase="DELETE ALL CARS"
        warningMessage={`You are about to permanently delete ALL ${counts.cars?.toLocaleString() ?? 'cars'} from the system. This action is irreversible and will affect all users. Build lists associated with deleted cars will have their car assignment removed and users will be prompted to assign a new car when they view those build lists.`}
        isProcessing={isDeletingAllCars}
        error={deleteAllError}
      />
    </div>
  );
}

export default AdminDashboard;
