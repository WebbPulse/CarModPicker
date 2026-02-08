import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import type { CategoryResponse } from '../../types/Api';
import type { CrawlerRunResponse } from '../../services/Api';
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
  usersApi,
  votesApi,
} from '../../services/Api';

interface EntityCounts {
  users: number | null;
  cars: number | null;
  makes: number | null;
  carModels: number | null;
  buildLists: number | null;
  globalParts: number | null;
  categories: number | null;
  bucketObjects: number | null;
  buildLogPosts: number | null;
  buildListParts: number | null;
  votes: number | null;
  reports: number | null;
  bugReports: number | null;
}

function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [counts, setCounts] = useState<EntityCounts>({
    users: null,
    cars: null,
    makes: null,
    carModels: null,
    buildLists: null,
    globalParts: null,
    categories: null,
    bucketObjects: null,
    buildLogPosts: null,
    buildListParts: null,
    votes: null,
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
  const [isDeleteAllGlobalPartsConfirmOpen, setIsDeleteAllGlobalPartsConfirmOpen] =
    useState(false);
  const [isDeletingAllGlobalParts, setIsDeletingAllGlobalParts] = useState(false);
  const [deleteAllGlobalPartsError, setDeleteAllGlobalPartsError] =
    useState<string | null>(null);
  const [deleteAllGlobalPartsResult, setDeleteAllGlobalPartsResult] = useState<{
    deleted_count: number;
  } | null>(null);
  const [isInitCarGenerations, setIsInitCarGenerations] = useState(false);
  const [initCarGenerationsResult, setInitCarGenerationsResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isInitPartCategories, setIsInitPartCategories] = useState(false);
  const [initPartCategoriesResult, setInitPartCategoriesResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // Crawler tools
  const [crawlerAdapters, setCrawlerAdapters] = useState<string[]>([]);
  const [selectedCrawlers, setSelectedCrawlers] = useState<Set<string>>(
    new Set()
  );
  const [crawlerLimits, setCrawlerLimits] = useState<Record<string, string>>(
    {}
  );
  const [globalCrawlerLimit, setGlobalCrawlerLimit] = useState<string>('');
  const [crawlerUserId, setCrawlerUserId] = useState<string>('');
  const [crawlerDefaultCategoryId, setCrawlerDefaultCategoryId] =
    useState<string>('');
  const [crawlerCategories, setCrawlerCategories] = useState<
    CategoryResponse[]
  >([]);
  const [isLoadingCrawlers, setIsLoadingCrawlers] = useState(false);
  const [isRunningCrawlers, setIsRunningCrawlers] = useState(false);
  const [crawlerResult, setCrawlerResult] =
    useState<CrawlerRunResponse | null>(null);
  const [crawlerError, setCrawlerError] = useState<string | null>(null);

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
        makesCount,
        carModelsCount,
        buildListsCount,
        globalPartsCount,
        categoriesCount,
        bucketObjectsCount,
        buildLogPostsCount,
        buildListPartsCount,
        votesCount,
        reportsCount,
        bugReportsCount,
      ] = await Promise.all([
        fetchCount(() => usersApi.countUsers(), 'users'),
        fetchCount(() => carsApi.countCars(), 'cars'),
        fetchCount(() => carsApi.countMakes(), 'makes'),
        fetchCount(() => carsApi.countCarModels(), 'car models'),
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
        fetchCount(() => reportsApi.countReports(), 'reports'),
        fetchCount(() => bugReportsApi.countBugReports(), 'bug reports'),
      ]);

      setCounts({
        users: usersCount,
        cars: carsCount,
        makes: makesCount,
        carModels: carModelsCount,
        buildLists: buildListsCount,
        globalParts: globalPartsCount,
        categories: categoriesCount,
        bucketObjects: bucketObjectsCount,
        buildLogPosts: buildLogPostsCount,
        buildListParts: buildListPartsCount,
        votes: votesCount,
        reports: reportsCount,
        bugReports: bugReportsCount,
      });

      // Show error only if all requests failed
      const allFailed =
        usersCount === null &&
        carsCount === null &&
        makesCount === null &&
        carModelsCount === null &&
        buildListsCount === null &&
        globalPartsCount === null &&
        categoriesCount === null &&
        bucketObjectsCount === null &&
        buildLogPostsCount === null &&
        buildListPartsCount === null &&
        votesCount === null &&
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

  // Fetch entity counts and crawlers on mount
  useEffect(() => {
    void fetchCounts();
    void fetchCurrentRevision();
    void fetchCrawlers();
  }, [fetchCounts]);

  const fetchCrawlers = async () => {
    if (!user?.is_admin) return;
    setIsLoadingCrawlers(true);
    try {
      const [adaptersRes, categoriesRes] = await Promise.all([
        adminApi.getCrawlers(),
        categoriesApi.getCategories(),
      ]);
      setCrawlerAdapters(adaptersRes.data.adapters);
      setCrawlerCategories(categoriesRes.data);
    } catch {
      setCrawlerAdapters([]);
      setCrawlerCategories([]);
    } finally {
      setIsLoadingCrawlers(false);
    }
  };

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

  const handleInitCarGenerations = async () => {
    setIsInitCarGenerations(true);
    setInitCarGenerationsResult(null);
    try {
      const response = await adminApi.initCarGenerations();
      setInitCarGenerationsResult(response.data);
      if (response.data.success) void fetchCounts();
    } catch (error) {
      setInitCarGenerationsResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize car generations',
      });
    } finally {
      setIsInitCarGenerations(false);
    }
  };

  const handleInitPartCategories = async () => {
    setIsInitPartCategories(true);
    setInitPartCategoriesResult(null);
    try {
      const response = await adminApi.initPartCategories();
      setInitPartCategoriesResult(response.data);
      if (response.data.success) void fetchCounts();
    } catch (error) {
      setInitPartCategoriesResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize part categories',
      });
    } finally {
      setIsInitPartCategories(false);
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

  const handleConfirmDeleteAllGlobalParts = async () => {
    setIsDeletingAllGlobalParts(true);
    setDeleteAllGlobalPartsError(null);
    try {
      const response = await adminApi.deleteAllGlobalParts();
      setDeleteAllGlobalPartsResult(response.data);
      setIsDeleteAllGlobalPartsConfirmOpen(false);
      await fetchCounts();
    } catch (error) {
      setDeleteAllGlobalPartsError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all global parts.'
      );
    } finally {
      setIsDeletingAllGlobalParts(false);
    }
  };

  const toggleCrawlerSelection = (adapter: string) => {
    setSelectedCrawlers((prev) => {
      const next = new Set(prev);
      if (next.has(adapter)) {
        next.delete(adapter);
      } else {
        next.add(adapter);
      }
      return next;
    });
  };

  const selectAllCrawlers = () => {
    setSelectedCrawlers(new Set(crawlerAdapters));
  };

  const deselectAllCrawlers = () => {
    setSelectedCrawlers(new Set());
  };

  const handleRunSelectedCrawlers = async () => {
    const adapters = Array.from(selectedCrawlers);
    if (adapters.length === 0) {
      setCrawlerError('Select at least one crawler.');
      return;
    }
    await runCrawlersWithAdapters(adapters);
  };

  const handleRunAllCrawlers = async () => {
    await runCrawlersWithAdapters(['all']);
  };

  const runCrawlersWithAdapters = async (adapters: string[]) => {
    const userIdNum = parseInt(crawlerUserId, 10);
    const categoryIdNum = parseInt(crawlerDefaultCategoryId, 10);
    if (isNaN(userIdNum) || userIdNum < 1) {
      setCrawlerError('Enter a valid crawler user ID.');
      return;
    }
    if (isNaN(categoryIdNum) || categoryIdNum < 1) {
      setCrawlerError('Select a default category.');
      return;
    }

    setIsRunningCrawlers(true);
    setCrawlerError(null);
    setCrawlerResult(null);

    const limits: Record<string, number> = {};
    const globalLimitNum =
      globalCrawlerLimit.trim() === ''
        ? null
        : parseInt(globalCrawlerLimit, 10);
    const useGlobalLimit =
      globalLimitNum != null &&
      !isNaN(globalLimitNum) &&
      globalLimitNum > 0;

    if (adapters[0] !== 'all') {
      for (const adapter of adapters) {
        const val = crawlerLimits[adapter]?.trim();
        if (val) {
          const n = parseInt(val, 10);
          if (!isNaN(n) && n > 0) {
            limits[adapter] = n;
          }
        }
      }
    }

    try {
      const response = await adminApi.runCrawlers({
        adapters,
        crawler_user_id: userIdNum,
        crawler_default_category_id: categoryIdNum,
        limits: Object.keys(limits).length > 0 ? limits : undefined,
        global_limit: useGlobalLimit ? globalLimitNum ?? undefined : undefined,
        parallel: true,
      });
      setCrawlerResult(response.data);
      void fetchCounts();
    } catch (error) {
      setCrawlerError(
        error instanceof Error ? error.message : 'Failed to run crawlers.'
      );
    } finally {
      setIsRunningCrawlers(false);
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
                <div className="text-sm text-gray-400 mb-1">Makes</div>
                <div className="text-3xl font-bold text-sky-400">
                  {counts.makes?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                <div className="text-sm text-gray-400 mb-1">Car Models</div>
                <div className="text-3xl font-bold text-lime-400">
                  {counts.carModels?.toLocaleString() ?? '—'}
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
          <SectionHeader title="Data Initialization" />
          <div className="p-6 bg-amber-900/20 border-2 border-amber-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-amber-400 mb-2">
                Seed data (car generations & part categories)
              </h3>
              <p className="text-neutral-300 mb-4">
                Sync makes, car models, car generations, and part categories
                from the application source of truth into the database. Run
                these after deploying or when seed data has been updated.
              </p>
            </div>
            <div className="flex flex-wrap gap-4 mb-4">
              <ActionButton
                onClick={() => void handleInitCarGenerations()}
                disabled={isInitCarGenerations}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isInitCarGenerations ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Initializing...
                  </span>
                ) : (
                  '🚗 Init Car Generations'
                )}
              </ActionButton>
              <ActionButton
                onClick={() => void handleInitPartCategories()}
                disabled={isInitPartCategories}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isInitPartCategories ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Initializing...
                  </span>
                ) : (
                  '📦 Init Part Categories'
                )}
              </ActionButton>
            </div>
            {(initCarGenerationsResult || initPartCategoriesResult) && (
              <div className="space-y-3">
                {initCarGenerationsResult && (
                  <div
                    className={`p-4 rounded-lg border-2 ${
                      initCarGenerationsResult.success
                        ? 'bg-green-900/20 border-green-700'
                        : 'bg-red-900/20 border-red-700'
                    }`}
                  >
                    <span
                      className={
                        initCarGenerationsResult.success
                          ? 'text-green-400'
                          : 'text-red-400'
                      }
                    >
                      Car generations:{' '}
                      {initCarGenerationsResult.success
                        ? initCarGenerationsResult.message
                        : initCarGenerationsResult.message}
                    </span>
                  </div>
                )}
                {initPartCategoriesResult && (
                  <div
                    className={`p-4 rounded-lg border-2 ${
                      initPartCategoriesResult.success
                        ? 'bg-green-900/20 border-green-700'
                        : 'bg-red-900/20 border-red-700'
                    }`}
                  >
                    <span
                      className={
                        initPartCategoriesResult.success
                          ? 'text-green-400'
                          : 'text-red-400'
                      }
                    >
                      Part categories:{' '}
                      {initPartCategoriesResult.success
                        ? initPartCategoriesResult.message
                        : initPartCategoriesResult.message}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <SectionHeader title="Global parts" />
          <div className="p-6 bg-red-900/20 border-2 border-red-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-red-400 mb-2">
                Delete all global parts
              </h3>
              <p className="text-neutral-300 mb-4">
                Permanently remove every global part from the catalog. This
                also removes their part listings, votes, reports, and build list
                part associations. This action cannot be undone.
              </p>
              <p className="text-sm text-neutral-400 mb-4">
                Current global parts:{' '}
                <span className="font-semibold text-white">
                  {counts.globalParts?.toLocaleString() ?? '—'}
                </span>
              </p>
            </div>
            <div className="flex flex-wrap gap-4 mb-4">
              <ActionButton
                onClick={() => {
                  setDeleteAllGlobalPartsError(null);
                  setDeleteAllGlobalPartsResult(null);
                  setIsDeleteAllGlobalPartsConfirmOpen(true);
                }}
                disabled={isDeletingAllGlobalParts}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {isDeletingAllGlobalParts ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Deleting...
                  </span>
                ) : (
                  'Delete all global parts'
                )}
              </ActionButton>
            </div>
            {deleteAllGlobalPartsResult && (
              <div className="p-4 rounded-lg border border-green-700 bg-green-900/20">
                <p className="text-green-400 font-semibold">
                  Deleted {deleteAllGlobalPartsResult.deleted_count.toLocaleString()}{' '}
                  global part(s).
                </p>
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

      <div className="mt-6">
        <Card>
          <SectionHeader title="Crawler Tools" />
          <div className="p-6 bg-emerald-900/20 border-2 border-emerald-700 rounded-xl">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-emerald-400 mb-2">
                Retailer crawlers
              </h3>
              <p className="text-neutral-300 mb-4">
                Run crawlers to scrape part information from retailer sites. You
                can run individual crawlers or combinations. When running more
                than one crawler, they run in parallel. Set per-crawler limits or
                a global limit for all crawlers.
              </p>
            </div>

            {isLoadingCrawlers ? (
              <div className="flex justify-center items-center py-8">
                <LoadingSpinner />
              </div>
            ) : (
              <>
                <div className="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-300 mb-2">
                      Crawler user ID
                    </label>
                    <Input
                      type="number"
                      min="1"
                      placeholder="e.g. 1"
                      value={crawlerUserId}
                      onChange={(e) => setCrawlerUserId(e.target.value)}
                      className="max-w-[150px]"
                    />
                    <p className="text-xs text-neutral-400 mt-1">
                      User that will own crawler-created parts
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-300 mb-2">
                      Default category
                    </label>
                    <select
                      value={crawlerDefaultCategoryId}
                      onChange={(e) =>
                        setCrawlerDefaultCategoryId(e.target.value)
                      }
                      className="w-full max-w-[250px] min-h-[44px] px-5 rounded-xl border border-white/20 bg-gray-800 text-neutral-200 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 focus:outline-none"
                    >
                      <option value="">Select category...</option>
                      {crawlerCategories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-neutral-400 mt-1">
                      Category for new parts
                    </p>
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-neutral-300 mb-2">
                    Global limit (applies to all crawlers when set)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    placeholder="e.g. 50"
                    value={globalCrawlerLimit}
                    onChange={(e) => setGlobalCrawlerLimit(e.target.value)}
                    className="max-w-[150px]"
                  />
                </div>

                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-neutral-300">
                      Select crawlers
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={selectAllCrawlers}
                        className="text-sm text-emerald-400 hover:text-emerald-300"
                      >
                        Select all
                      </button>
                      <span className="text-neutral-500">|</span>
                      <button
                        type="button"
                        onClick={deselectAllCrawlers}
                        className="text-sm text-emerald-400 hover:text-emerald-300"
                      >
                        Deselect all
                      </button>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {crawlerAdapters.map((adapter) => (
                      <div
                        key={adapter}
                        className="flex items-center gap-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700"
                      >
                        <label className="flex items-center gap-2 cursor-pointer flex-1">
                          <input
                            type="checkbox"
                            checked={selectedCrawlers.has(adapter)}
                            onChange={() => toggleCrawlerSelection(adapter)}
                            className="rounded border-gray-600 bg-gray-700 text-emerald-500 focus:ring-emerald-500"
                          />
                          <span className="font-mono text-neutral-200">
                            {adapter}
                          </span>
                        </label>
                        <div className="flex items-center gap-2 w-32">
                          <span className="text-xs text-neutral-400">
                            Limit:
                          </span>
                          <Input
                            type="number"
                            min="1"
                            placeholder="—"
                            value={crawlerLimits[adapter] ?? ''}
                            onChange={(e) =>
                              setCrawlerLimits((prev) => ({
                                ...prev,
                                [adapter]: e.target.value,
                              }))
                            }
                            className="w-20"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-4 mb-4">
                  <ActionButton
                    onClick={() => void handleRunSelectedCrawlers()}
                    disabled={isRunningCrawlers}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {isRunningCrawlers ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Running...
                      </span>
                    ) : (
                      'Run selected crawlers'
                    )}
                  </ActionButton>
                  <ActionButton
                    onClick={() => void handleRunAllCrawlers()}
                    disabled={isRunningCrawlers}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    Run all crawlers
                  </ActionButton>
                </div>

                {crawlerError && (
                  <div className="mb-4">
                    <ErrorAlert message={crawlerError} />
                  </div>
                )}

                {crawlerResult && (
                  <div className="p-4 rounded-lg border-2 border-emerald-700 bg-gray-900/50">
                    <div className="mb-2 font-semibold text-emerald-400">
                      Crawl complete
                    </div>
                    <div className="text-sm text-neutral-300 mb-3">
                      Ingested: {crawlerResult.summary.total_ingested} | Skipped:{' '}
                      {crawlerResult.summary.total_skipped} | Errors:{' '}
                      {crawlerResult.summary.total_errors}
                    </div>
                    {crawlerResult.results.length > 0 && (
                      <details className="mb-2">
                        <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-300">
                          Per-crawler results
                        </summary>
                        <ul className="mt-2 space-y-1 text-sm text-neutral-300">
                          {crawlerResult.results.map((r) => (
                            <li key={r.adapter} className="font-mono">
                              {`${r.adapter}: ingested=${r.ingested} skipped=${r.skipped} errors=${r.errors} total=${r.total}`}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {crawlerResult.failed.length > 0 && (
                      <div className="text-sm text-red-400">
                        Failed:{' '}
                        {crawlerResult.failed
                          .map((f) => `${f.adapter}: ${f.error}`)
                          .join('; ')}
                      </div>
                    )}
                  </div>
                )}
              </>
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
      <DeleteConfirmationDialog
        isOpen={isDeleteAllGlobalPartsConfirmOpen}
        onClose={() => {
          setIsDeleteAllGlobalPartsConfirmOpen(false);
          setDeleteAllGlobalPartsError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllGlobalParts()}
        itemName="all global parts"
        itemType="catalog"
        isProcessing={isDeletingAllGlobalParts}
        error={deleteAllGlobalPartsError}
      />
    </div>
  );
}

export default AdminDashboard;
