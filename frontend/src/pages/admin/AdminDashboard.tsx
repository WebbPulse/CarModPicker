import axios from 'axios';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import type {
  AdminTableCountsResponse,
  BucketEntityTypeCountResponse,
} from '../../services/Api';
import {
  adminApi,
  partManufacturersApi,
  bugReportsApi,
  buildListPartsApi,
  buildListsApi,
  buildLogsApi,
  carGenerationsApi,
  categoriesApi,
  partsApi,
  imageApi,
  reportsApi,
  retailersApi,
  usersApi,
  votesApi,
} from '../../services/Api';

function getHttpStatus(error: unknown): number | undefined {
  if (axios.isAxiosError(error)) {
    return error.response?.status;
  }
  return undefined;
}

/** Preferred order for S3 key prefix labels (matches upload entity_type values). */
const BUCKET_ENTITY_TYPE_ORDER = [
  'user',
  'car_generation',
  'build_list',
  'part',
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

/** One metric row: must be direct children of StatPanel's grid (fragment = two cells). */
function StatRow({ label, value }: { label: string; value: number | null }) {
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
  subValue?: string | undefined;
  detail?: ReactNode | undefined;
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
          <div className="text-[10px] tabular-nums text-gray-500">
            {subValue}
          </div>
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
  parts: number | null;
  categories: number | null;
  part_manufacturers: number | null;
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
  partCars: number | null;
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
    parts: null,
    categories: null,
    part_manufacturers: null,
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
    partCars: null,
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

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

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
      const [
        usersCount,
        carsCount,
        makesCount,
        carModelsCount,
        buildListsCount,
        partsCount,
        categoriesCount,
        partManufacturersCount,
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
        fetchCount(() => carGenerationsApi.countCars(), 'cars'),
        fetchCount(() => carGenerationsApi.countMakes(), 'makes'),
        fetchCount(() => carGenerationsApi.countCarModels(), 'car models'),
        fetchCount(() => buildListsApi.countBuildLists(), 'build lists'),
        fetchCount(() => partsApi.countParts(), 'global parts'),
        fetchCount(() => categoriesApi.countCategories(), 'categories'),
        fetchCount(
          () => partManufacturersApi.countPartManufacturers(),
          'part manufacturers'
        ),
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
        parts: partsCount,
        categories: categoriesCount,
        part_manufacturers: partManufacturersCount,
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
        partCars: adminTable?.part_cars ?? null,
        votes: votesCount,
        reports: reportsCount,
        bugReports: bugReportsCount,
      });

      const allFailed =
        usersCount === null &&
        carsCount === null &&
        makesCount === null &&
        carModelsCount === null &&
        buildListsCount === null &&
        partsCount === null &&
        categoriesCount === null &&
        partManufacturersCount === null &&
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
        setCountsError(
          `Some statistics could not be loaded: ${failedEndpoints.join(', ')}. Other data is shown below.`
        );
      } else if (staleApiRoutesNotice) {
        setCountsError(
          'The API process looks out of date (new routes returned 404). Restart the backend so it loads the latest code—for example: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000. Until then, S3 totals may still appear from the legacy count endpoint, but bucket prefix breakdown and supplemental table counts stay empty.'
        );
      } else {
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

  useEffect(() => {
    void fetchCounts();
  }, [fetchCounts]);

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

  const adminSections = [
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
    {
      title: 'Crawler & Jobs',
      description:
        'Run crawlers, manage archives, schedule, and background jobs',
      icon: '🕷️',
      path: '/admin/crawler',
    },
    {
      title: 'System & Database',
      description:
        'Migrations, data initialization, and destructive operations',
      icon: '⚙️',
      path: '/admin/system',
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Admin Dashboard"
        subtitle="Manage CarModPicker system settings and content"
      />

      {/* Navigation cards */}
      <Card>
        <SectionHeader title="Admin Sections" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {adminSections.map((section) => (
            <div
              key={section.path}
              className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3 mb-2">
                <span className="text-2xl">{section.icon}</span>
                <h3 className="text-lg font-semibold text-gray-200">
                  {section.title}
                </h3>
              </div>
              <p className="text-gray-400 mb-3 text-sm">
                {section.description}
              </p>
              <ActionButton
                onClick={() => void navigate(section.path)}
                className="w-full"
              >
                {section.title}
              </ActionButton>
            </div>
          ))}
        </div>
      </Card>

      {/* System Statistics */}
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
                <StatRow
                  label="Build list parts"
                  value={counts.buildListParts}
                />
                <StatRow
                  label="Build list phases"
                  value={counts.buildListPhases}
                />
                <StatRow label="Build logs" value={counts.buildLogs} />
                <StatRow label="Build log posts" value={counts.buildLogPosts} />
              </StatPanel>

              <StatPanel title="Parts & catalog">
                <StatRow label="Global parts" value={counts.parts} />
                <StatRow label="Categories" value={counts.categories} />
                <StatRow
                  label="Part Manufacturers"
                  value={counts.part_manufacturers}
                />
                <StatRow label="Retailers" value={counts.retailers} />
                <StatRow label="Part ↔ car links" value={counts.partCars} />
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
                            const n =
                              bucketEntitySummary.by_entity_type[prefix];
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
                        Uploads from the app/extension (USER_IMAGES_BUCKET).
                        Scraped part photos are usually remote URLs, not counted
                        here.
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
                        <span className="font-mono text-gray-500">
                          crawl_html/
                        </span>{' '}
                        on disk instead. Set{' '}
                        <span className="font-mono text-gray-500">
                          CRAWL_BUCKET
                        </span>{' '}
                        (and AWS / LocalStack) to store archives in S3—then
                        counts appear here (about two objects per archived page:
                        .html + .url).
                      </p>
                    ) : adminTableCounts?.crawl_bucket_error ? (
                      <p className="text-[10px] text-red-400/90">
                        {adminTableCounts.crawl_bucket_error}
                      </p>
                    ) : adminTableCounts &&
                      adminTableCounts.crawl_bucket_configured &&
                      Object.keys(adminTableCounts.crawl_bucket_by_prefix)
                        .length > 0 ? (
                      <div className="rounded border border-gray-800/90 bg-black/25 px-1.5 py-1">
                        <div className="text-[9px] font-medium uppercase tracking-wide text-gray-600 mb-0.5">
                          By top-level prefix
                        </div>
                        <div className="grid grid-cols-2 min-[420px]:grid-cols-3 gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-500">
                          {Object.entries(
                            adminTableCounts.crawl_bucket_by_prefix
                          )
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
                        Bucket is configured but empty (no archived HTML keys
                        yet).
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
                        {Object.entries(adminTableCounts.reports_by_entity_type)
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
    </div>
  );
}

export default AdminDashboard;
