import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import {
  adminApi,
  bugReportsApi,
  buildListPartsApi,
  buildListsApi,
  buildLogsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
  imageApi,
  reportsApi,
  subscriptionsApi,
  usersApi,
  votesApi,
} from '../../services/Api';

interface EntityCounts {
  users: number | null;
  cars: number | null;
  buildLists: number | null;
  globalParts: number | null;
  categories: number | null;
  bucketObjects: number | null;
  buildLogPosts: number | null;
  buildListParts: number | null;
  votes: number | null;
  subscriptions: number | null;
  reports: number | null;
  bugReports: number | null;
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
    buildLogPosts: null,
    buildListParts: null,
    votes: null,
    subscriptions: null,
    reports: null,
    bugReports: null,
  });
  const [isLoadingCounts, setIsLoadingCounts] = useState(true);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [isRunningMigrations, setIsRunningMigrations] = useState(false);
  const [migrationResult, setMigrationResult] = useState<{
    success: boolean;
    output: string;
    error: string | null;
    current_revision: string | null;
  } | null>(null);
  const [currentRevision, setCurrentRevision] = useState<string | null>(null);
  const [isLoadingRevision, setIsLoadingRevision] = useState(false);
  const [orphanedResult, setOrphanedResult] = useState<{
    count: number;
    total_bucket: number;
    total_referenced: number;
    orphaned_keys: string[];
  } | null>(null);
  const [isListingOrphaned, setIsListingOrphaned] = useState(false);
  const [isPurgingOrphaned, setIsPurgingOrphaned] = useState(false);
  const [isPurgeOrphanConfirmOpen, setIsPurgeOrphanConfirmOpen] =
    useState(false);
  const [purgeOrphanError, setPurgeOrphanError] = useState<string | null>(null);

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
        buildLogPostsCount,
        buildListPartsCount,
        votesCount,
        subscriptionsCount,
        reportsCount,
        bugReportsCount,
      ] = await Promise.all([
        fetchCount(() => usersApi.countUsers(), 'users'),
        fetchCount(() => carsApi.countCars(), 'cars'),
        fetchCount(() => buildListsApi.countBuildLists(), 'build lists'),
        fetchCount(() => globalPartsApi.countGlobalParts(), 'global parts'),
        fetchCount(() => categoriesApi.countCategories(), 'categories'),
        fetchCount(() => imageApi.countBucketObjects(), 'bucket objects'),
        fetchCount(() => buildLogsApi.countBuildLogPosts(), 'build log posts'),
        fetchCount(
          () => buildListPartsApi.countBuildListParts(),
          'build list parts'
        ),
        fetchCount(() => votesApi.countVotes(), 'votes'),
        fetchCount(
          () => subscriptionsApi.countSubscriptions(),
          'subscriptions'
        ),
        fetchCount(() => reportsApi.countReports(), 'reports'),
        fetchCount(() => bugReportsApi.countBugReports(), 'bug reports'),
      ]);

      setCounts({
        users: usersCount,
        cars: carsCount,
        buildLists: buildListsCount,
        globalParts: globalPartsCount,
        categories: categoriesCount,
        bucketObjects: bucketObjectsCount,
        buildLogPosts: buildLogPostsCount,
        buildListParts: buildListPartsCount,
        votes: votesCount,
        subscriptions: subscriptionsCount,
        reports: reportsCount,
        bugReports: bugReportsCount,
      });

      // Show error only if all requests failed
      const allFailed =
        usersCount === null &&
        carsCount === null &&
        buildListsCount === null &&
        globalPartsCount === null &&
        categoriesCount === null &&
        bucketObjectsCount === null &&
        buildLogPostsCount === null &&
        buildListPartsCount === null &&
        votesCount === null &&
        subscriptionsCount === null &&
        reportsCount === null &&
        bugReportsCount === null;

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
    void fetchCurrentRevision();
  }, [fetchCounts]);

  const fetchCurrentRevision = async () => {
    setIsLoadingRevision(true);
    try {
      const response = await adminApi.getCurrentRevision();
      setCurrentRevision(response.data.current_revision);
    } catch (error) {
      console.error('Failed to fetch current revision:', error);
    } finally {
      setIsLoadingRevision(false);
    }
  };

  const handleRunMigrations = async () => {
    setIsRunningMigrations(true);
    setMigrationResult(null);

    try {
      const response = await adminApi.runMigrations();
      setMigrationResult(response.data);
      // Refresh revision after migration
      await fetchCurrentRevision();
    } catch (error) {
      setMigrationResult({
        success: false,
        output: '',
        error:
          error instanceof Error ? error.message : 'Failed to run migrations',
        current_revision: null,
      });
    } finally {
      setIsRunningMigrations(false);
    }
  };

  const handleListOrphaned = async () => {
    setIsListingOrphaned(true);
    setOrphanedResult(null);
    try {
      const response = await imageApi.getOrphanedBucketObjects();
      setOrphanedResult(response.data);
    } catch {
      setOrphanedResult(null);
    } finally {
      setIsListingOrphaned(false);
    }
  };

  const handleConfirmPurgeOrphaned = async () => {
    setIsPurgingOrphaned(true);
    setPurgeOrphanError(null);
    try {
      await imageApi.purgeOrphanedBucketObjects();
      setIsPurgeOrphanConfirmOpen(false);
      setOrphanedResult(null);
      await fetchCounts();
    } catch (error) {
      setPurgeOrphanError(
        error instanceof Error
          ? error.message
          : 'Failed to purge orphaned bucket objects.'
      );
    } finally {
      setIsPurgingOrphaned(false);
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
    {
      title: 'Bug Reports',
      description: 'Review and manage bug reports',
      icon: '🐛',
      path: '/admin/bug-reports',
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
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">
                  Build Log Posts
                </div>
                <div className="text-3xl font-bold text-orange-400">
                  {counts.buildLogPosts?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">
                  Build List Parts
                </div>
                <div className="text-3xl font-bold text-indigo-400">
                  {counts.buildListParts?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Votes</div>
                <div className="text-3xl font-bold text-teal-400">
                  {counts.votes?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Subscriptions</div>
                <div className="text-3xl font-bold text-emerald-400">
                  {counts.subscriptions?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Reports</div>
                <div className="text-3xl font-bold text-red-400">
                  {counts.reports?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Bug Reports</div>
                <div className="text-3xl font-bold text-amber-400">
                  {counts.bugReports?.toLocaleString() ?? '—'}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <SectionHeader title="Database Migrations" />
          <div className="p-6 bg-blue-900/20 border-2 border-blue-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-blue-400 mb-2">
                Run Database Migrations
              </h3>
              <p className="text-neutral-300 mb-4">
                Manually run database migrations to update the database schema.
                This is useful if automatic migrations fail or need to be run
                on-demand.
              </p>
              {currentRevision && (
                <p className="text-sm text-neutral-400 mb-4">
                  Current revision:{' '}
                  <span className="font-mono font-semibold text-white">
                    {currentRevision || 'Unknown'}
                  </span>
                </p>
              )}
            </div>
            <div className="flex gap-4 mb-4">
              <ActionButton
                onClick={() => void handleRunMigrations()}
                disabled={isRunningMigrations}
                className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
              >
                {isRunningMigrations ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Running Migrations...
                  </span>
                ) : (
                  '🔄 Run Migrations'
                )}
              </ActionButton>
              <ActionButton
                onClick={() => void fetchCurrentRevision()}
                disabled={isLoadingRevision}
                className="text-sm"
              >
                {isLoadingRevision ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Loading...
                  </span>
                ) : (
                  '🔄 Refresh Revision'
                )}
              </ActionButton>
            </div>
            {migrationResult && (
              <div
                className={`p-4 rounded-lg border-2 ${
                  migrationResult.success
                    ? 'bg-green-900/20 border-green-700'
                    : 'bg-red-900/20 border-red-700'
                }`}
              >
                <div className="mb-2">
                  <span
                    className={`font-semibold ${
                      migrationResult.success
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {migrationResult.success
                      ? '✓ Migrations completed successfully'
                      : '✗ Migration failed'}
                  </span>
                </div>
                {migrationResult.current_revision && (
                  <div className="text-sm text-neutral-300 mb-2">
                    <span className="font-semibold">New revision:</span>{' '}
                    <span className="font-mono">
                      {migrationResult.current_revision}
                    </span>
                  </div>
                )}
                {migrationResult.output && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-300">
                      View output
                    </summary>
                    <pre className="mt-2 p-2 bg-gray-900 rounded text-xs text-neutral-300 overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.output}
                    </pre>
                  </details>
                )}
                {migrationResult.error && (
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-red-400 mb-1">
                      Error:
                    </p>
                    <pre className="p-2 bg-gray-900 rounded text-xs text-red-300 overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.error}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <SectionHeader title="Storage / Bucket" />
          <div className="p-6 bg-cyan-900/20 border-2 border-cyan-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-cyan-400 mb-2">
                Railway bucket orphan cleanup
              </h3>
              <p className="text-neutral-300 mb-4">
                Bucket objects that are not referenced by any entity (global
                parts, users, cars, build lists, image cache) can be safely
                removed to free space. This is non-destructive: only orphaned
                objects are deleted; no entity loses its images.
              </p>
              <p className="text-sm text-neutral-400 mb-4">
                Total bucket objects:{' '}
                <span className="font-semibold text-white">
                  {counts.bucketObjects?.toLocaleString() ?? '—'}
                </span>
              </p>
            </div>
            <div className="flex flex-wrap gap-4 mb-4">
              <ActionButton
                onClick={() => void handleListOrphaned()}
                disabled={isListingOrphaned}
                className="bg-cyan-600 hover:bg-cyan-700 text-white"
              >
                {isListingOrphaned ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Listing...
                  </span>
                ) : (
                  'List orphaned (dry run)'
                )}
              </ActionButton>
              <ActionButton
                onClick={() => {
                  setPurgeOrphanError(null);
                  setIsPurgeOrphanConfirmOpen(true);
                }}
                disabled={isPurgingOrphaned}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isPurgingOrphaned ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Purging...
                  </span>
                ) : (
                  'Purge orphaned objects'
                )}
              </ActionButton>
            </div>
            {orphanedResult && (
              <div className="p-4 rounded-lg border border-cyan-700 bg-gray-900/50">
                <p className="text-neutral-300 mb-2">
                  <span className="font-semibold text-cyan-400">
                    {orphanedResult.count.toLocaleString()}
                  </span>{' '}
                  orphaned object(s) of{' '}
                  <span className="font-semibold">
                    {orphanedResult.total_bucket.toLocaleString()}
                  </span>{' '}
                  total in bucket (
                  {orphanedResult.total_referenced.toLocaleString()} referenced
                  by entities).
                </p>
                {orphanedResult.orphaned_keys.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-300">
                      Show key list (first 50)
                    </summary>
                    <pre className="mt-2 p-2 bg-gray-800 rounded text-xs text-neutral-300 overflow-x-auto max-h-48 overflow-y-auto">
                      {orphanedResult.orphaned_keys.slice(0, 50).join('\n')}
                      {orphanedResult.orphaned_keys.length > 50 &&
                        `\n... and ${orphanedResult.orphaned_keys.length - 50} more`}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      <DeleteConfirmationDialog
        isOpen={isPurgeOrphanConfirmOpen}
        onClose={() => {
          setIsPurgeOrphanConfirmOpen(false);
          setPurgeOrphanError(null);
        }}
        onConfirm={() => void handleConfirmPurgeOrphaned()}
        itemName="orphaned bucket objects (only unreferenced images)"
        itemType="storage"
        isProcessing={isPurgingOrphaned}
        error={purgeOrphanError}
      />
    </div>
  );
}

export default AdminDashboard;
