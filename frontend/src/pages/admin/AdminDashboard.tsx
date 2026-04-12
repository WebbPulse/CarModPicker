import axios from 'axios';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
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
import type {
  AdminTableCountsResponse,
  BackgroundJob,
  BackgroundJobList,
  BucketEntityTypeCountResponse,
  CrawlerCronStatus,
  CrawlerRunRequest,
  CrawlerRunResponse,
  RescrapeArchivesQueuedResponse,
  RescrapeArchivesRequest,
} from '../../services/Api';
import {
  adminApi,
  brandsApi,
  bugReportsApi,
  buildListPartsApi,
  buildListsApi,
  buildLogsApi,
  carsApi,
  categoriesApi,
  globalPartsApi,
  imageApi,
  reportsApi,
  retailersApi,
  usersApi,
  votesApi,
} from '../../services/Api';
import type { CategoryResponse } from '../../types/Api';

function getHttpStatus(error: unknown): number | undefined {
  if (axios.isAxiosError(error)) {
    return error.response?.status;
  }
  return undefined;
}

/** Preferred order for S3 key prefix labels (matches upload entity_type values). */
const BUCKET_ENTITY_TYPE_ORDER = [
  'user',
  'car',
  'build_list',
  'global_part',
  'build_log_post',
] as const;

function formatStatCount(value: number | null): string {
  return value?.toLocaleString() ?? '—';
}

/** Panel with a 2-column metric grid so values align within the card (no full-width label/value stretch). */
function StatPanel({
  title,
  children,
  className = '',
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-gray-800/90 bg-gray-950/65 px-2.5 py-2 min-w-0 ${className}`}
    >
      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5 pb-1 border-b border-gray-800">
        {title}
      </h3>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 gap-y-1 items-baseline text-xs">
        {children}
      </div>
    </section>
  );
}

/** One metric row: must be direct children of StatPanel’s grid (fragment = two cells). */
function StatRow({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <>
      <span
        className="text-[11px] text-gray-500 truncate min-w-0 leading-tight"
        title={label}
      >
        {label}
      </span>
      <span className="text-xs font-semibold tabular-nums text-gray-100 text-right leading-tight">
        {formatStatCount(value)}
      </span>
    </>
  );
}

/** Metric row plus optional detail block spanning both grid columns. */
function StatRowWithDetail({
  label,
  value,
  subValue,
  detail,
}: {
  label: string;
  value: number | null;
  /** Optional secondary value shown below the main count (e.g. "1.23 GB"). */
  subValue?: string;
  detail?: ReactNode;
}) {
  return (
    <>
      <span
        className="text-[11px] text-gray-500 truncate min-w-0 leading-tight"
        title={label}
      >
        {label}
      </span>
      <div className="text-right leading-tight">
        <div className="text-xs font-semibold tabular-nums text-gray-100">
          {formatStatCount(value)}
        </div>
        {subValue !== undefined && (
          <div className="text-[10px] tabular-nums text-gray-500">{subValue}</div>
        )}
      </div>
      {detail ? (
        <div className="col-span-2 min-w-0 -mt-0.5 mb-0.5">{detail}</div>
      ) : null}
    </>
  );
}

interface EntityCounts {
  users: number | null;
  cars: number | null;
  makes: number | null;
  carModels: number | null;
  buildLists: number | null;
  globalParts: number | null;
  categories: number | null;
  brands: number | null;
  retailers: number | null;
  bucketObjects: number | null;
  buildLogPosts: number | null;
  buildListParts: number | null;
  buildListPhases: number | null;
  crawledPages: number | null;
  partListings: number | null;
  partPriceHistories: number | null;
  imageSourceMappings: number | null;
  buildLogs: number | null;
  globalPartCars: number | null;
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
    brands: null,
    retailers: null,
    bucketObjects: null,
    buildLogPosts: null,
    buildListParts: null,
    buildListPhases: null,
    crawledPages: null,
    partListings: null,
    partPriceHistories: null,
    imageSourceMappings: null,
    buildLogs: null,
    globalPartCars: null,
    votes: null,
    reports: null,
    bugReports: null,
  });
  const [bucketEntitySummary, setBucketEntitySummary] =
    useState<BucketEntityTypeCountResponse | null>(null);
  const [adminTableCounts, setAdminTableCounts] =
    useState<AdminTableCountsResponse | null>(null);
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
  const [
    isDeleteAllGlobalPartsConfirmOpen,
    setIsDeleteAllGlobalPartsConfirmOpen,
  ] = useState(false);
  const [isDeletingAllGlobalParts, setIsDeletingAllGlobalParts] =
    useState(false);
  const [deleteAllGlobalPartsError, setDeleteAllGlobalPartsError] = useState<
    string | null
  >(null);
  const [deleteAllGlobalPartsResult, setDeleteAllGlobalPartsResult] = useState<{
    deleted_count: number;
  } | null>(null);
  const [isDeleteAllBrandsConfirmOpen, setIsDeleteAllBrandsConfirmOpen] =
    useState(false);
  const [isDeletingAllBrands, setIsDeletingAllBrands] = useState(false);
  const [deleteAllBrandsError, setDeleteAllBrandsError] = useState<
    string | null
  >(null);
  const [deleteAllBrandsResult, setDeleteAllBrandsResult] = useState<{
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
  const [isDeleteAllCarsConfirmOpen, setIsDeleteAllCarsConfirmOpen] =
    useState(false);
  const [isDeletingAllCars, setIsDeletingAllCars] = useState(false);
  const [deleteAllCarsError, setDeleteAllCarsError] = useState<string | null>(
    null
  );
  const [deleteAllCarsResult, setDeleteAllCarsResult] = useState<{
    deleted_count: number;
    deleted_car_models_count: number;
    deleted_makes_count: number;
  } | null>(null);

  // Crawler tools
  const [crawlerAdapters, setCrawlerAdapters] = useState<string[]>([]);
  const [selectedCrawlers, setSelectedCrawlers] = useState<Set<string>>(
    () => new Set()
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
  const [crawlerResult, setCrawlerResult] = useState<CrawlerRunResponse | null>(
    null
  );
  const [crawlerError, setCrawlerError] = useState<string | null>(null);
  const [crawlerDelaySec, setCrawlerDelaySec] = useState<number>(5);
  const [crawlerHtmlSaveDir, setCrawlerHtmlSaveDir] = useState<string>('');
  // Rescrape archived HTML (batch re-parse + ingest)
  const [isRescrapingArchives, setIsRescrapingArchives] = useState(false);
  const [rescrapeArchivesResult, setRescrapeArchivesResult] =
    useState<RescrapeArchivesQueuedResponse | null>(null);
  const [rescrapeArchivesError, setRescrapeArchivesError] = useState<
    string | null
  >(null);

  // Background jobs panel
  const [jobsList, setJobsList] = useState<BackgroundJobList | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  // Cron schedule management
  const [cronStatus, setCronStatus] = useState<CrawlerCronStatus | null>(null);
  const [cronDraft, setCronDraft] = useState<{
    preset: string;
    customExpression: string;
  }>({ preset: 'monthly', customExpression: '' });
  const [isCronUnavailable, setIsCronUnavailable] = useState(false);
  const [isSavingCron, setIsSavingCron] = useState(false);
  const [cronSaveError, setCronSaveError] = useState<string | null>(null);

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
    let staleApiRoutesNotice = false;

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

    const fetchBucketEntitySummary =
      async (): Promise<BucketEntityTypeCountResponse | null> => {
        try {
          const response = await imageApi.getBucketCountByEntityType();
          return response.data;
        } catch (e) {
          const status = getHttpStatus(e);
          // Older API build (route missing): try legacy total-only count.
          if (status === 404) {
            try {
              const legacy = await imageApi.countBucketObjects();
              staleApiRoutesNotice = true;
              return {
                total: legacy.data.count,
                by_entity_type: {},
                other: 0,
              };
            } catch (e2) {
              if (getHttpStatus(e2) === 503) {
                return null;
              }
              failedEndpoints.push('bucket objects (S3)');
              return null;
            }
          }
          if (status === 503) {
            return null;
          }
          failedEndpoints.push('bucket objects (S3)');
          return null;
        }
      };

    const fetchAdminTableStats =
      async (): Promise<AdminTableCountsResponse | null> => {
        try {
          const response = await adminApi.getTableCounts();
          return response.data;
        } catch (e) {
          const status = getHttpStatus(e);
          if (status === 404) {
            staleApiRoutesNotice = true;
            return null;
          }
          failedEndpoints.push('admin supplemental table counts');
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
        brandsCount,
        retailersCount,
        bucketSummary,
        adminTable,
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
        fetchCount(() => brandsApi.countBrands(), 'brands'),
        fetchCount(() => retailersApi.countRetailers(), 'retailers'),
        fetchBucketEntitySummary(),
        fetchAdminTableStats(),
        fetchCount(() => buildLogsApi.countBuildLogPosts(), 'build log posts'),
        fetchCount(
          () => buildListPartsApi.countBuildListParts(),
          'build list parts'
        ),
        fetchCount(() => votesApi.countVotes(), 'votes'),
        fetchCount(() => reportsApi.countReports(), 'reports'),
        fetchCount(() => bugReportsApi.countBugReports(), 'bug reports'),
      ]);

      setBucketEntitySummary(bucketSummary);
      setAdminTableCounts(adminTable);

      setCounts({
        users: usersCount,
        cars: carsCount,
        makes: makesCount,
        carModels: carModelsCount,
        buildLists: buildListsCount,
        globalParts: globalPartsCount,
        categories: categoriesCount,
        brands: brandsCount,
        retailers: retailersCount,
        bucketObjects: bucketSummary?.total ?? null,
        buildLogPosts: buildLogPostsCount,
        buildListParts: buildListPartsCount,
        buildListPhases: adminTable?.build_list_phases ?? null,
        crawledPages: adminTable?.crawled_pages ?? null,
        partListings: adminTable?.part_listings ?? null,
        partPriceHistories: adminTable?.part_price_histories ?? null,
        imageSourceMappings: adminTable?.image_source_mappings ?? null,
        buildLogs: adminTable?.build_logs ?? null,
        globalPartCars: adminTable?.global_part_cars ?? null,
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
        brandsCount === null &&
        retailersCount === null &&
        bucketSummary === null &&
        adminTable === null &&
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
      } else if (staleApiRoutesNotice) {
        setCountsError(
          'The API process looks out of date (new routes returned 404). Restart the backend so it loads the latest code—for example: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000. Until then, S3 totals may still appear from the legacy count endpoint, but bucket prefix breakdown and supplemental table counts stay empty.'
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

  const fetchCrawlers = useCallback(async () => {
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
  }, [user?.is_admin]);

  const fetchJobs = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingJobs(true);
    try {
      const res = await adminApi.listJobs({ limit: 20 });
      setJobsList(res.data);
    } catch {
      // silently fail — jobs panel is supplementary
    } finally {
      setIsLoadingJobs(false);
    }
  }, [user?.is_admin]);

  const fetchCronStatus = useCallback(async () => {
    if (!user?.is_admin) return;
    try {
      const res = await adminApi.getCrawlerCron();
      setCronStatus(res.data);
      setCronDraft({
        preset: res.data.preset === 'custom' ? 'custom' : res.data.preset,
        customExpression:
          res.data.preset === 'custom' ? res.data.schedule_expression : '',
      });
      setIsCronUnavailable(false);
    } catch {
      // 404 / 503 = scheduler not configured in this environment — hide the panel
      setIsCronUnavailable(true);
    }
  }, [user?.is_admin]);

  const handleSaveCron = async (patch: {
    enabled?: boolean;
    preset?: string;
    customExpression?: string;
  }) => {
    setIsSavingCron(true);
    setCronSaveError(null);
    try {
      const body: { enabled?: boolean; preset?: string; schedule_expression?: string } = {};
      if (patch.enabled !== undefined) body.enabled = patch.enabled;
      if (patch.preset && patch.preset !== 'custom') {
        body.preset = patch.preset as 'monthly' | 'weekly' | 'daily';
      } else if (patch.customExpression) {
        body.schedule_expression = patch.customExpression;
      }
      const res = await adminApi.updateCrawlerCron(body);
      setCronStatus(res.data);
      setCronDraft({
        preset: res.data.preset === 'custom' ? 'custom' : res.data.preset,
        customExpression:
          res.data.preset === 'custom' ? res.data.schedule_expression : '',
      });
    } catch (e) {
      setCronSaveError(e instanceof Error ? e.message : 'Failed to update schedule.');
    } finally {
      setIsSavingCron(false);
    }
  };

  // Fetch entity counts, crawlers, jobs, and cron status on mount
  useEffect(() => {
    void fetchCounts();
    void fetchCurrentRevision();
    void fetchCrawlers();
    void fetchJobs();
    void fetchCronStatus();
  }, [fetchCounts, fetchCrawlers, fetchJobs, fetchCronStatus]);

  // Poll jobs every 5 s while any job is running
  useEffect(() => {
    const hasRunning = jobsList?.items.some((j) => j.status === 'running');
    if (!hasRunning) return;
    const id = setInterval(() => {
      void fetchJobs();
    }, 5000);
    return () => clearInterval(id);
  }, [jobsList, fetchJobs]);

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

  const handleConfirmDeleteAllCars = async () => {
    setIsDeletingAllCars(true);
    setDeleteAllCarsError(null);
    try {
      const response = await adminApi.deleteAllCars();
      setDeleteAllCarsResult(response.data);
      setIsDeleteAllCarsConfirmOpen(false);
      await fetchCounts();
    } catch (error) {
      setDeleteAllCarsError(
        error instanceof Error ? error.message : 'Failed to delete all cars.'
      );
    } finally {
      setIsDeletingAllCars(false);
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

  const handleConfirmDeleteAllBrands = async () => {
    setIsDeletingAllBrands(true);
    setDeleteAllBrandsError(null);
    try {
      const response = await adminApi.deleteAllBrands();
      setDeleteAllBrandsResult(response.data);
      setIsDeleteAllBrandsConfirmOpen(false);
      await fetchCounts();
    } catch (error) {
      setDeleteAllBrandsError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all part brands.'
      );
    } finally {
      setIsDeletingAllBrands(false);
    }
  };

  const handleRescrapeArchives = async () => {
    const userIdNum = parseInt(crawlerUserId, 10);
    const categoryIdNum = parseInt(crawlerDefaultCategoryId, 10);
    if (isNaN(userIdNum) || userIdNum < 1) {
      setRescrapeArchivesError('Enter a valid crawler user ID (1 or greater).');
      return;
    }
    if (isNaN(categoryIdNum) || categoryIdNum < 1) {
      setRescrapeArchivesError('Select a default category.');
      return;
    }

    setIsRescrapingArchives(true);
    setRescrapeArchivesResult(null);
    setRescrapeArchivesError(null);
    try {
      const body: RescrapeArchivesRequest = {
        crawler_user_id: userIdNum,
        default_category_id: categoryIdNum,
      };
      const response = await adminApi.rescrapeArchives(body);
      setRescrapeArchivesResult(response.data);
      void fetchCounts();
      void fetchJobs();
    } catch (error) {
      setRescrapeArchivesError(
        error instanceof Error
          ? error.message
          : 'Failed to start rescrape archives job.'
      );
    } finally {
      setIsRescrapingArchives(false);
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
      globalLimitNum != null && !isNaN(globalLimitNum) && globalLimitNum > 0;

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
      const body: CrawlerRunRequest = {
        adapters,
        crawler_user_id: userIdNum,
        crawler_default_category_id: categoryIdNum,
        parallel: true,
        delay_sec: crawlerDelaySec,
      };
      if (Object.keys(limits).length > 0) body.limits = limits;
      if (useGlobalLimit && globalLimitNum != null && globalLimitNum > 0)
        body.global_limit = globalLimitNum;
      if (crawlerHtmlSaveDir.trim()) {
        body.crawl_html_save_dir = crawlerHtmlSaveDir.trim();
      }
      const response = await adminApi.runCrawlers(body);
      setCrawlerResult(response.data);
      setCrawlerError(null);
      void fetchCounts();
      void fetchJobs();
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
          <div className="flex items-center justify-between mb-2">
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
            <div className="mb-2">
              <ErrorAlert message={countsError} />
            </div>
          )}
          {isLoadingCounts ? (
            <div className="flex justify-center items-center py-6">
              <LoadingSpinner />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2 [&>*]:min-w-0">
              <StatPanel title="Users & vehicles">
                <StatRow label="Users" value={counts.users} />
                <StatRow label="Cars" value={counts.cars} />
                <StatRow label="Makes" value={counts.makes} />
                <StatRow label="Car models" value={counts.carModels} />
              </StatPanel>

              <StatPanel title="Builds & logs">
                <StatRow label="Build lists" value={counts.buildLists} />
                <StatRow label="Build list parts" value={counts.buildListParts} />
                <StatRow
                  label="Build list phases"
                  value={counts.buildListPhases}
                />
                <StatRow label="Build logs" value={counts.buildLogs} />
                <StatRow label="Build log posts" value={counts.buildLogPosts} />
              </StatPanel>

              <StatPanel title="Parts & catalog">
                <StatRow label="Global parts" value={counts.globalParts} />
                <StatRow label="Categories" value={counts.categories} />
                <StatRow label="Brands" value={counts.brands} />
                <StatRow label="Retailers" value={counts.retailers} />
                <StatRow
                  label="Part ↔ car links"
                  value={counts.globalPartCars}
                />
              </StatPanel>

              <StatPanel title="Crawling & listings">
                <StatRow label="Crawled pages" value={counts.crawledPages} />
                <StatRow label="Part listings" value={counts.partListings} />
                <StatRow
                  label="Price history rows"
                  value={counts.partPriceHistories}
                />
              </StatPanel>

              <StatPanel title="Media & storage">
                <StatRowWithDetail
                  label="User images S3 (total)"
                  value={counts.bucketObjects}
                  subValue={
                    bucketEntitySummary?.size_gb != null
                      ? `${bucketEntitySummary.size_gb.toFixed(3)} GB`
                      : undefined
                  }
                  detail={
                    bucketEntitySummary ? (
                      <div className="rounded border border-gray-800/90 bg-black/25 px-1.5 py-1">
                        <div className="text-[9px] font-medium uppercase tracking-wide text-gray-600 mb-0.5">
                          By key prefix
                        </div>
                        <div className="grid grid-cols-2 min-[420px]:grid-cols-3 gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-500">
                          {BUCKET_ENTITY_TYPE_ORDER.map((prefix) => {
                            const n = bucketEntitySummary.by_entity_type[prefix];
                            if (!n) return null;
                            return (
                              <div
                                key={prefix}
                                className="flex justify-between gap-1 min-w-0 leading-tight"
                              >
                                <span className="truncate">{prefix}</span>
                                <span className="tabular-nums shrink-0 text-gray-400">
                                  {n.toLocaleString()}
                                </span>
                              </div>
                            );
                          })}
                          {Object.keys(bucketEntitySummary.by_entity_type)
                            .filter(
                              (k) =>
                                !BUCKET_ENTITY_TYPE_ORDER.includes(
                                  k as (typeof BUCKET_ENTITY_TYPE_ORDER)[number]
                                )
                            )
                            .sort()
                            .map((prefix) => {
                              const n =
                                bucketEntitySummary.by_entity_type[prefix];
                              return (
                                <div
                                  key={prefix}
                                  className="flex justify-between gap-1 min-w-0 leading-tight"
                                >
                                  <span className="truncate">{prefix}</span>
                                  <span className="tabular-nums shrink-0 text-gray-400">
                                    {(n ?? 0).toLocaleString()}
                                  </span>
                                </div>
                              );
                            })}
                          {bucketEntitySummary.other > 0 ? (
                            <div className="col-span-2 min-[420px]:col-span-3 flex justify-between gap-2 text-amber-500/90 leading-tight pt-0.5 border-t border-gray-800/80 mt-0.5">
                              <span>Non-standard keys</span>
                              <span className="tabular-nums shrink-0">
                                {bucketEntitySummary.other.toLocaleString()}
                              </span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <p className="text-[10px] text-gray-600 leading-snug">
                        Uploads from the app/extension (USER_IMAGES_BUCKET). Scraped
                        part photos are usually remote URLs, not counted here.
                      </p>
                    )
                  }
                />
                <StatRowWithDetail
                  label="Crawl HTML S3 (CRAWL_BUCKET)"
                  value={
                    adminTableCounts == null
                      ? null
                      : adminTableCounts.crawl_bucket_configured
                        ? adminTableCounts.crawl_bucket_total
                        : null
                  }
                  subValue={
                    adminTableCounts?.crawl_bucket_configured &&
                    adminTableCounts.crawl_bucket_size_gb != null &&
                    !adminTableCounts.crawl_bucket_error
                      ? `${adminTableCounts.crawl_bucket_size_gb.toFixed(3)} GB`
                      : undefined
                  }
                  detail={
                    adminTableCounts &&
                    !adminTableCounts.crawl_bucket_configured ? (
                      <p className="text-[10px] text-gray-600 leading-snug">
                        Bucket not configured: scraped page HTML is saved under{' '}
                        <span className="font-mono text-gray-500">crawl_html/</span>{' '}
                        on disk instead. Set{' '}
                        <span className="font-mono text-gray-500">CRAWL_BUCKET</span>{' '}
                        (and AWS / LocalStack) to store archives in S3—then counts
                        appear here (about two objects per archived page: .html + .url).
                      </p>
                    ) : adminTableCounts?.crawl_bucket_error ? (
                      <p className="text-[10px] text-red-400/90">
                        {adminTableCounts.crawl_bucket_error}
                      </p>
                    ) : adminTableCounts &&
                      adminTableCounts.crawl_bucket_configured &&
                      Object.keys(adminTableCounts.crawl_bucket_by_prefix).length >
                        0 ? (
                      <div className="rounded border border-gray-800/90 bg-black/25 px-1.5 py-1">
                        <div className="text-[9px] font-medium uppercase tracking-wide text-gray-600 mb-0.5">
                          By top-level prefix
                        </div>
                        <div className="grid grid-cols-2 min-[420px]:grid-cols-3 gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-500">
                          {Object.entries(adminTableCounts.crawl_bucket_by_prefix)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([prefix, n]) => (
                              <div
                                key={prefix}
                                className="flex justify-between gap-1 min-w-0 leading-tight"
                              >
                                <span className="truncate">{prefix}</span>
                                <span className="tabular-nums shrink-0 text-gray-400">
                                  {n.toLocaleString()}
                                </span>
                              </div>
                            ))}
                        </div>
                      </div>
                    ) : adminTableCounts?.crawl_bucket_configured ? (
                      <p className="text-[10px] text-gray-600 leading-snug">
                        Bucket is configured but empty (no archived HTML keys yet).
                      </p>
                    ) : undefined
                  }
                />
                <StatRow
                  label="Image source mappings"
                  value={counts.imageSourceMappings}
                />
              </StatPanel>

              <StatPanel title="Community">
                <StatRowWithDetail
                  label="Votes"
                  value={counts.votes}
                  detail={
                    adminTableCounts &&
                    Object.keys(adminTableCounts.votes_by_entity_type).length >
                      0 ? (
                      <div className="rounded border border-gray-800/90 bg-black/25 px-1.5 py-1 grid grid-cols-1 min-[360px]:grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-500">
                        {Object.entries(adminTableCounts.votes_by_entity_type)
                          .sort(([a], [b]) => a.localeCompare(b))
                          .map(([entityType, n]) => (
                            <div
                              key={entityType}
                              className="flex justify-between gap-1 min-w-0 leading-tight"
                            >
                              <span className="truncate">{entityType}</span>
                              <span className="tabular-nums shrink-0 text-gray-400">
                                {n.toLocaleString()}
                              </span>
                            </div>
                          ))}
                      </div>
                    ) : undefined
                  }
                />
                <StatRowWithDetail
                  label="Reports"
                  value={counts.reports}
                  detail={
                    adminTableCounts &&
                    Object.keys(adminTableCounts.reports_by_entity_type)
                      .length > 0 ? (
                      <div className="rounded border border-gray-800/90 bg-black/25 px-1.5 py-1 grid grid-cols-1 min-[360px]:grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-500">
                        {Object.entries(
                          adminTableCounts.reports_by_entity_type
                        )
                          .sort(([a], [b]) => a.localeCompare(b))
                          .map(([entityType, n]) => (
                            <div
                              key={entityType}
                              className="flex justify-between gap-1 min-w-0 leading-tight"
                            >
                              <span className="truncate">{entityType}</span>
                              <span className="tabular-nums shrink-0 text-gray-400">
                                {n.toLocaleString()}
                              </span>
                            </div>
                          ))}
                      </div>
                    ) : undefined
                  }
                />
                <StatRow label="Bug reports" value={counts.bugReports} />
              </StatPanel>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-3">
        <Card padding="sm">
          <div className="mb-2">
            <h2 className="text-lg font-semibold text-white mb-1">
              Database Migrations
            </h2>
            <p className="text-sm text-neutral-400">
              Run migrations to update the database schema on-demand.
              {currentRevision && (
                <>
                  {' '}
                  Current:{' '}
                  <span className="font-mono text-white">
                    {currentRevision}
                  </span>
                </>
              )}
            </p>
          </div>
          <div className="p-3 bg-blue-900/20 border border-blue-700 rounded-lg">
            <div className="flex flex-wrap items-center gap-3 mb-2">
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
                className={`p-3 rounded-lg border text-sm ${
                  migrationResult.success
                    ? 'bg-green-900/20 border-green-700'
                    : 'bg-red-900/20 border-red-700'
                }`}
              >
                <div className="mb-1">
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
                  <div className="text-neutral-300 mb-1">
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

      <div className="mt-3">
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-white mb-1">
            Data Initialization
          </h2>
          <p className="text-sm text-neutral-400 mb-3">
            Sync car generations and part categories from source of truth.
          </p>
          <div className="p-3 bg-amber-900/20 border border-amber-700 rounded-lg">
            <div className="flex flex-wrap gap-3 mb-2">
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
              <div className="space-y-2 mt-2">
                {initCarGenerationsResult && (
                  <div
                    className={`p-2 rounded border text-sm ${
                      initCarGenerationsResult.success
                        ? 'bg-green-900/20 border-green-700 text-green-400'
                        : 'bg-red-900/20 border-red-700 text-red-400'
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
                    className={`p-2 rounded border text-sm ${
                      initPartCategoriesResult.success
                        ? 'bg-green-900/20 border-green-700 text-green-400'
                        : 'bg-red-900/20 border-red-700 text-red-400'
                    }`}
                  >
                    <span>
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

      <div className="mt-3">
        <Card padding="sm">
          <details className="group border border-red-800/50 rounded-lg overflow-hidden">
            <summary className="cursor-pointer list-none px-3 py-2 bg-red-900/20 hover:bg-red-900/30 transition-colors flex items-center justify-between text-sm">
              <span className="font-semibold text-red-400">
                Deletion options (cars, global parts, brands, bucket)
              </span>
              <span className="text-red-400/80 group-open:rotate-180 transition-transform inline-block">
                ▼
              </span>
            </summary>
            <div className="divide-y divide-gray-700">
              <div className="p-3 bg-orange-900/20 border-t border-orange-700/50">
                <h3 className="text-base font-semibold text-orange-400 mb-1">
                  Delete all cars (generations)
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Permanently remove every car generation, car model, and make
                  from the catalog. Build lists are unlinked from cars (not
                  deleted). Run &quot;Init Car Generations&quot; afterward to
                  repopulate from a clean slate. This action cannot be undone.
                </p>
                <p className="text-xs text-neutral-400 mb-2">
                  Cars:{' '}
                  <span className="font-semibold text-white">
                    {counts.cars?.toLocaleString() ?? '—'}
                  </span>
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => {
                      setDeleteAllCarsError(null);
                      setDeleteAllCarsResult(null);
                      setIsDeleteAllCarsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllCars}
                    className="bg-orange-600 hover:bg-orange-700 text-white text-sm py-1.5 px-3"
                  >
                    {isDeletingAllCars ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Deleting...
                      </span>
                    ) : (
                      'Delete all cars'
                    )}
                  </ActionButton>
                </div>
                {deleteAllCarsResult && (
                  <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                    <p className="font-semibold">
                      Deleted{' '}
                      {deleteAllCarsResult.deleted_count.toLocaleString()}{' '}
                      car(s),{' '}
                      {deleteAllCarsResult.deleted_car_models_count.toLocaleString()}{' '}
                      car model(s), and{' '}
                      {deleteAllCarsResult.deleted_makes_count.toLocaleString()}{' '}
                      make(s). Run Init Car Generations to repopulate.
                    </p>
                  </div>
                )}
              </div>

              <div className="p-3 bg-red-900/20 border-t border-red-700/50">
                <h3 className="text-base font-semibold text-red-400 mb-1">
                  Delete all global parts / part brands
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Permanently remove every global part from the catalog (also
                  removes their part listings, votes, reports, and build list
                  part associations). Or remove only part brands (parts keep
                  their data; brand references are cleared). These actions
                  cannot be undone.
                </p>
                <p className="text-xs text-neutral-400 mb-2">
                  Parts:{' '}
                  <span className="font-semibold text-white">
                    {counts.globalParts?.toLocaleString() ?? '—'}
                  </span>
                  {' · '}
                  Brands:{' '}
                  <span className="font-semibold text-white">
                    {counts.brands?.toLocaleString() ?? '—'}
                  </span>
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => {
                      setDeleteAllGlobalPartsError(null);
                      setDeleteAllGlobalPartsResult(null);
                      setIsDeleteAllGlobalPartsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllGlobalParts}
                    className="bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
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
                  <ActionButton
                    onClick={() => {
                      setDeleteAllBrandsError(null);
                      setDeleteAllBrandsResult(null);
                      setIsDeleteAllBrandsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllBrands}
                    className="bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
                  >
                    {isDeletingAllBrands ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Deleting...
                      </span>
                    ) : (
                      'Delete all part brands'
                    )}
                  </ActionButton>
                </div>
                {(deleteAllGlobalPartsResult || deleteAllBrandsResult) && (
                  <div className="space-y-1 mt-2">
                    {deleteAllGlobalPartsResult && (
                      <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllGlobalPartsResult.deleted_count.toLocaleString()}{' '}
                          global part(s).
                        </p>
                      </div>
                    )}
                    {deleteAllBrandsResult && (
                      <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllBrandsResult.deleted_count.toLocaleString()}{' '}
                          part brand(s). Parts keep their data; brand references
                          were cleared.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="p-3 bg-cyan-900/20 border-t border-cyan-700/50">
                <h3 className="text-base font-semibold text-cyan-400 mb-1">
                  Bucket orphan cleanup
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Bucket objects that are not referenced by any entity (global
                  parts, users, cars, build lists, image cache) can be safely
                  removed to free space. Only orphaned objects are deleted; no
                  entity loses its images.
                </p>
                <p className="text-xs text-neutral-400 mb-2">
                  Bucket:{' '}
                  <span className="font-semibold text-white">
                    {counts.bucketObjects?.toLocaleString() ?? '—'}
                  </span>
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => void handleListOrphaned()}
                    disabled={isListingOrphaned}
                    className="bg-cyan-600 hover:bg-cyan-700 text-white text-sm py-1.5 px-3"
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
                    className="bg-amber-600 hover:bg-amber-700 text-white text-sm py-1.5 px-3"
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
                  <div className="p-2 rounded border border-cyan-700 bg-gray-900/50 text-sm text-neutral-300">
                    <p className="mb-1">
                      <span className="font-semibold text-cyan-400">
                        {orphanedResult.count.toLocaleString()}
                      </span>{' '}
                      orphaned object(s) of{' '}
                      <span className="font-semibold">
                        {orphanedResult.total_bucket.toLocaleString()}
                      </span>{' '}
                      total in bucket (
                      {orphanedResult.total_referenced.toLocaleString()}{' '}
                      referenced by entities).
                    </p>
                    {orphanedResult.orphaned_keys.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-xs text-neutral-400 hover:text-neutral-300">
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
            </div>
          </details>
        </Card>
      </div>

      <div className="mt-3">
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-white mb-1">
            Crawler & archives
          </h2>
          <p className="text-sm text-neutral-400 mb-3">
            Run live retailer crawls or re-process stored HTML archives. Crawler user and
            default category apply to both.
          </p>

          {isLoadingCrawlers ? (
            <div className="flex justify-center items-center py-10">
              <LoadingSpinner />
            </div>
          ) : (
            <>
              <div className="mb-4 p-3 rounded-lg border border-white/15 bg-gray-900/40">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-400 mb-2">
                  Shared defaults
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-neutral-400 mb-0.5">
                      Crawler user ID
                    </label>
                    <Input
                      type="number"
                      min="1"
                      placeholder="e.g. 1"
                      value={crawlerUserId}
                      onChange={(e) => setCrawlerUserId(e.target.value)}
                      className="max-w-[140px] min-h-[36px] text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-400 mb-0.5">
                      Default category
                    </label>
                    <select
                      value={crawlerDefaultCategoryId}
                      onChange={(e) =>
                        setCrawlerDefaultCategoryId(e.target.value)
                      }
                      className="w-full max-w-xs min-h-[36px] px-3 py-1.5 text-sm rounded-lg border border-white/20 bg-gray-800 text-neutral-200 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 focus:outline-none"
                    >
                      <option value="">Select category...</option>
                      {crawlerCategories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-emerald-900/20 border border-emerald-700 rounded-lg mb-4">
                <h3 className="text-sm font-semibold text-emerald-200 mb-2">
                  Live crawlers
                </h3>
                <p className="text-xs text-neutral-400 mb-3">
                  Fetch fresh pages from retailers. Configure delay, limits, and optional HTML
                  export below.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-neutral-400 mb-0.5">
                      Delay
                    </label>
                    <select
                      value={crawlerDelaySec}
                      onChange={(e) =>
                        setCrawlerDelaySec(Number(e.target.value))
                      }
                      className="max-w-[120px] min-h-[36px] px-2 py-1 text-sm rounded-lg border border-white/20 bg-gray-800 text-neutral-200 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 focus:outline-none"
                    >
                      <option value={2.5}>2.5 s</option>
                      <option value={5}>5 s</option>
                      <option value={10}>10 s</option>
                      <option value={15}>15 s</option>
                      <option value={30}>30 s</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-400 mb-0.5">
                      Global limit
                    </label>
                    <Input
                      type="number"
                      min="1"
                      placeholder="—"
                      value={globalCrawlerLimit}
                      onChange={(e) => setGlobalCrawlerLimit(e.target.value)}
                      className="max-w-[80px] min-h-[36px] text-sm"
                    />
                  </div>
                  <div className="md:col-span-2 flex flex-col sm:flex-row sm:items-end gap-2">
                    <Input
                      type="text"
                      placeholder="HTML save dir (optional)"
                      value={crawlerHtmlSaveDir}
                      onChange={(e) => setCrawlerHtmlSaveDir(e.target.value)}
                      className="min-h-[36px] text-sm flex-1 min-w-0"
                    />
                  </div>
                </div>

                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-neutral-400">
                      Crawlers
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={selectAllCrawlers}
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        All
                      </button>
                      <span className="text-neutral-500">|</span>
                      <button
                        type="button"
                        onClick={deselectAllCrawlers}
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        None
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {crawlerAdapters.map((adapter) => (
                      <div
                        key={adapter}
                        className="flex items-center gap-2 py-1.5 px-2 bg-gray-800/50 rounded border border-gray-700"
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
                        <div className="flex items-center gap-1 w-24">
                          <span className="text-xs text-neutral-500">
                            Limit
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
                            className="w-16 min-h-[28px] text-sm"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => void handleRunSelectedCrawlers()}
                    disabled={isRunningCrawlers}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm py-1.5 px-3"
                  >
                    {isRunningCrawlers ? (
                      <span className="flex items-center">
                        <LoadingSpinner size="sm" inline />
                        <span className="ml-1">Running...</span>
                      </span>
                    ) : (
                      'Run selected'
                    )}
                  </ActionButton>
                  <ActionButton
                    onClick={() => void handleRunAllCrawlers()}
                    disabled={isRunningCrawlers}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm py-1.5 px-3"
                  >
                    Run all
                  </ActionButton>
                </div>

                {crawlerError && (
                  <div className="mb-2">
                    <ErrorAlert message={crawlerError} />
                  </div>
                )}

                {crawlerResult && (
                  <div className="p-2 rounded border border-emerald-700 bg-gray-900/50 text-sm">
                    <div className="font-semibold text-emerald-400">
                      {crawlerResult.status === 'started'
                        ? 'Crawler job started'
                        : 'Crawler'}
                    </div>
                    <p className="text-neutral-300">{crawlerResult.message}</p>
                    {crawlerResult.adapters.length > 0 && (
                      <p className="text-xs text-neutral-400 font-mono mt-0.5">
                        {crawlerResult.adapters.join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>

              <div className="p-3 bg-violet-900/20 border border-violet-700 rounded-lg">
                <h3 className="text-sm font-semibold text-violet-200 mb-2">
                  Archive rescrape
                </h3>
                <p className="text-xs text-neutral-400 mb-2">
                  Re-run parse → ingest on every URL that has archived HTML (same pipeline as
                  a live crawl: parts, category and car inference, listings, and price history
                  when a price is found). Stale snapshots still record a price observation.
                </p>
                <p className="text-xs text-neutral-500 mb-3">
                  Archived pages:{' '}
                  <span className="font-semibold text-neutral-200">
                    {counts.crawledPages?.toLocaleString() ?? '—'}
                  </span>
                  <span className="text-neutral-600"> · </span>
                  <span className="text-neutral-500">
                    Background job—watch server logs for per-outcome counts.
                  </span>
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <ActionButton
                    onClick={() => void handleRescrapeArchives()}
                    disabled={isRescrapingArchives}
                    className="bg-violet-600 hover:bg-violet-700 text-white text-sm py-1.5 px-3"
                  >
                    {isRescrapingArchives ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Starting…
                      </span>
                    ) : (
                      'Rescrape latest archives'
                    )}
                  </ActionButton>
                </div>
                {rescrapeArchivesError && (
                  <div className="mt-2">
                    <ErrorAlert message={rescrapeArchivesError} />
                  </div>
                )}
                {rescrapeArchivesResult && (
                  <div className="p-2 rounded border text-sm mt-2 bg-green-900/20 border-green-700">
                    <p className="font-semibold text-green-400">
                      {rescrapeArchivesResult.status === 'started'
                        ? 'Job queued.'
                        : rescrapeArchivesResult.status}
                    </p>
                    <p className="text-neutral-300 text-xs mt-1">
                      {rescrapeArchivesResult.message}
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Crawler cron schedule */}
      {!isCronUnavailable && (
        <div className="mt-6">
          <Card>
            <div className="mb-4">
              <h2 className="text-xl font-semibold text-white">Crawler Schedule</h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Monthly automated run of all crawler adapters via EventBridge Scheduler.
                Changes take effect immediately — no deploy needed.
              </p>
            </div>

            {cronStatus === null ? (
              <div className="flex justify-center py-6">
                <LoadingSpinner size="sm" />
              </div>
            ) : (
              <div className="space-y-4">
                {/* Enable / disable toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-900/40">
                  <div>
                    <p className="text-sm font-medium text-gray-200">Scheduled runs</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {cronStatus.enabled
                        ? `Active — ${cronStatus.schedule_expression}`
                        : 'Disabled — no automatic runs'}
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      void handleSaveCron({ enabled: !cronStatus.enabled })
                    }
                    disabled={isSavingCron}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
                      cronStatus.enabled ? 'bg-emerald-600' : 'bg-gray-600'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ${
                        cronStatus.enabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Interval picker */}
                <div className="p-3 rounded-lg border border-gray-700 bg-gray-900/40 space-y-3">
                  <p className="text-sm font-medium text-gray-200">Run interval</p>
                  <div className="flex flex-wrap gap-2">
                    {(['monthly', 'weekly', 'daily'] as const).map((p) => (
                      <button
                        key={p}
                        onClick={() =>
                          setCronDraft((d) => ({ ...d, preset: p, customExpression: '' }))
                        }
                        className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                          cronDraft.preset === p
                            ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                            : 'border-gray-600 text-gray-400 hover:border-gray-400'
                        }`}
                      >
                        {p.charAt(0).toUpperCase() + p.slice(1)}
                      </button>
                    ))}
                    <button
                      onClick={() =>
                        setCronDraft((d) => ({
                          ...d,
                          preset: 'custom',
                          customExpression: d.customExpression || cronStatus.schedule_expression,
                        }))
                      }
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        cronDraft.preset === 'custom'
                          ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                          : 'border-gray-600 text-gray-400 hover:border-gray-400'
                      }`}
                    >
                      Custom
                    </button>
                  </div>

                  {cronDraft.preset === 'custom' && (
                    <div className="flex gap-2 items-center">
                      <input
                        type="text"
                        value={cronDraft.customExpression}
                        onChange={(e) =>
                          setCronDraft((d) => ({
                            ...d,
                            customExpression: e.target.value,
                          }))
                        }
                        placeholder="cron(0 2 1 * ? *)"
                        className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  )}

                  {cronDraft.preset !== 'custom' && cronStatus.presets[cronDraft.preset] && (
                    <p className="text-xs text-gray-500 font-mono">
                      {cronStatus.presets[cronDraft.preset]}
                    </p>
                  )}

                  <div className="flex items-center gap-3 pt-1">
                    <ActionButton
                      onClick={() =>
                        void handleSaveCron({
                          preset: cronDraft.preset,
                          customExpression: cronDraft.customExpression,
                        })
                      }
                      disabled={
                        isSavingCron ||
                        (cronDraft.preset === 'custom' &&
                          !cronDraft.customExpression.trim())
                      }
                      className="bg-blue-600 hover:bg-blue-700 text-white text-xs py-1 px-3"
                    >
                      {isSavingCron ? 'Saving…' : 'Save interval'}
                    </ActionButton>
                    {cronStatus.preset !== 'custom' &&
                      cronDraft.preset === cronStatus.preset && (
                        <span className="text-xs text-gray-500">Current: {cronStatus.preset}</span>
                      )}
                  </div>
                </div>

                {cronSaveError && (
                  <ErrorAlert message={cronSaveError} />
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Background Jobs */}
      <div className="mt-6">
        <Card>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-white">Background Jobs</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Live status of crawler and rescrape jobs. Polls every 5 s while a job is running.
            </p>
          </div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-gray-500">
              {jobsList ? `${jobsList.total} total` : ''}
            </span>
            <button
              onClick={() => void fetchJobs()}
              disabled={isLoadingJobs}
              className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
            >
              {isLoadingJobs ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {!jobsList && isLoadingJobs && (
            <div className="flex justify-center py-6">
              <LoadingSpinner size="sm" />
            </div>
          )}

          {jobsList && jobsList.items.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-6">No jobs yet.</p>
          )}

          {jobsList && jobsList.items.length > 0 && (
            <div className="space-y-2">
              {jobsList.items.map((job: BackgroundJob) => {
                const isExpanded = expandedJobId === job.id;
                const statusColor =
                  job.status === 'completed'
                    ? 'text-emerald-400'
                    : job.status === 'failed'
                      ? 'text-red-400'
                      : job.status === 'running'
                        ? 'text-yellow-400'
                        : 'text-gray-400';
                const statusBg =
                  job.status === 'completed'
                    ? 'border-emerald-800/60 bg-emerald-950/30'
                    : job.status === 'failed'
                      ? 'border-red-800/60 bg-red-950/30'
                      : job.status === 'running'
                        ? 'border-yellow-800/60 bg-yellow-950/30'
                        : 'border-gray-700 bg-gray-900/30';

                const typeLabel =
                  job.job_type === 'crawler_run'
                    ? 'Crawler Run'
                    : job.job_type === 'archive_rescrape'
                      ? 'Archive Rescrape'
                      : job.job_type;

                const startedAt = new Date(job.started_at);
                const completedAt = job.completed_at
                  ? new Date(job.completed_at)
                  : null;
                const durationSec = completedAt
                  ? Math.round(
                      (completedAt.getTime() - startedAt.getTime()) / 1000
                    )
                  : null;

                return (
                  <div
                    key={job.id}
                    className={`rounded-lg border px-3 py-2 text-sm ${statusBg}`}
                  >
                    <button
                      className="w-full flex items-center justify-between gap-2 text-left"
                      onClick={() =>
                        setExpandedJobId(isExpanded ? null : job.id)
                      }
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={`font-semibold text-xs uppercase tracking-wide shrink-0 ${statusColor}`}
                        >
                          {job.status === 'running' ? '● ' : ''}
                          {job.status}
                        </span>
                        <span className="text-gray-300 font-medium truncate">
                          #{job.id} — {typeLabel}
                        </span>
                        <span className="text-gray-500 text-xs shrink-0">
                          {job.triggered_by}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                        <span>{startedAt.toLocaleString()}</span>
                        {durationSec !== null && (
                          <span className="tabular-nums">
                            {durationSec < 60
                              ? `${durationSec}s`
                              : `${Math.floor(durationSec / 60)}m ${durationSec % 60}s`}
                          </span>
                        )}
                        <span className="text-gray-600">{isExpanded ? '▲' : '▼'}</span>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="mt-2 pt-2 border-t border-gray-700/60 space-y-2">
                        {job.params && (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                              Params
                            </p>
                            <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                              {JSON.stringify(job.params, null, 2)}
                            </pre>
                          </div>
                        )}
                        {job.result_summary && (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                              Result
                            </p>
                            <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                              {JSON.stringify(job.result_summary, null, 2)}
                            </pre>
                          </div>
                        )}
                        {job.error_message && (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500 mb-1">
                              Error
                            </p>
                            <pre className="text-xs text-red-300 bg-red-950/40 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                              {job.error_message}
                            </pre>
                          </div>
                        )}
                        {job.status === 'running' && (
                          <div className="flex gap-2 pt-1">
                            <button
                              onClick={() => {
                                void adminApi
                                  .cancelJob(job.id)
                                  .then(() => fetchJobs())
                                  .catch(() => undefined);
                              }}
                              className="text-xs text-red-400 hover:text-red-300 underline"
                            >
                              Cancel job
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
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
      <DeleteConfirmationDialog
        isOpen={isDeleteAllBrandsConfirmOpen}
        onClose={() => {
          setIsDeleteAllBrandsConfirmOpen(false);
          setDeleteAllBrandsError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllBrands()}
        itemName="all part brands"
        itemType="catalog"
        isProcessing={isDeletingAllBrands}
        error={deleteAllBrandsError}
      />
      <DeleteConfirmationDialog
        isOpen={isDeleteAllCarsConfirmOpen}
        onClose={() => {
          setIsDeleteAllCarsConfirmOpen(false);
          setDeleteAllCarsError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllCars()}
        itemName="all cars (generations)"
        itemType="catalog"
        isProcessing={isDeletingAllCars}
        error={deleteAllCarsError}
      />
    </div>
  );
}

export default AdminDashboard;
