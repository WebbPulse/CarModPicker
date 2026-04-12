import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import type {
  BackgroundJob,
  BackgroundJobList,
  CrawlerCronStatus,
  CrawlerRunRequest,
  CrawlerRunResponse,
  RescrapeArchivesQueuedResponse,
  RescrapeArchivesRequest,
} from '../../services/Api';
import { adminApi, categoriesApi } from '../../services/Api';
import type { CategoryResponse } from '../../types/Api';

function CrawlerAdmin() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Crawler tools
  const [crawlerAdapters, setCrawlerAdapters] = useState<string[]>([]);
  const [selectedCrawlers, setSelectedCrawlers] = useState<Set<string>>(
    () => new Set()
  );
  const [crawlerLimits, setCrawlerLimits] = useState<Record<string, string>>({});
  const [globalCrawlerLimit, setGlobalCrawlerLimit] = useState<string>('');
  const [crawlerUserId, setCrawlerUserId] = useState<string>('');
  const [crawlerDefaultCategoryId, setCrawlerDefaultCategoryId] = useState<string>('');
  const [crawlerCategories, setCrawlerCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCrawlers, setIsLoadingCrawlers] = useState(false);
  const [isRunningCrawlers, setIsRunningCrawlers] = useState(false);
  const [crawlerResult, setCrawlerResult] = useState<CrawlerRunResponse | null>(null);
  const [crawlerError, setCrawlerError] = useState<string | null>(null);
  const [crawlerDelaySec, setCrawlerDelaySec] = useState<number>(5);
  const [crawlerHtmlSaveDir, setCrawlerHtmlSaveDir] = useState<string>('');

  // Rescrape
  const [isRescrapingArchives, setIsRescrapingArchives] = useState(false);
  const [rescrapeArchivesResult, setRescrapeArchivesResult] =
    useState<RescrapeArchivesQueuedResponse | null>(null);
  const [rescrapeArchivesError, setRescrapeArchivesError] = useState<string | null>(null);

  // Background jobs
  const [jobsList, setJobsList] = useState<BackgroundJobList | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  // Cron
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

  // Default crawler user ID to the logged-in user
  useEffect(() => {
    if (user && crawlerUserId === '') {
      setCrawlerUserId(String(user.id));
    }
  }, [user, crawlerUserId]);

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
      // silently fail
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

  useEffect(() => {
    void fetchCrawlers();
    void fetchJobs();
    void fetchCronStatus();
  }, [fetchCrawlers, fetchJobs, fetchCronStatus]);

  // Poll jobs every 5 s while any job is running
  useEffect(() => {
    const hasRunning = jobsList?.items.some((j) => j.status === 'running');
    if (!hasRunning) return;
    const id = setInterval(() => {
      void fetchJobs();
    }, 5000);
    return () => clearInterval(id);
  }, [jobsList, fetchJobs]);

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
      globalCrawlerLimit.trim() === '' ? null : parseInt(globalCrawlerLimit, 10);
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
      void fetchJobs();
    } catch (error) {
      setCrawlerError(
        error instanceof Error ? error.message : 'Failed to run crawlers.'
      );
    } finally {
      setIsRunningCrawlers(false);
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

  if (!user) {
    return (
      <div>
        <PageHeader title="Crawler & Jobs" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Crawler & Jobs" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Crawler & Jobs"
        subtitle="Run crawlers, manage archives, configure schedule, and monitor background jobs"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
      </div>

      <div className="xl:grid xl:grid-cols-[3fr_2fr] xl:items-start gap-4">

      {/* Crawler & archives */}
      <Card padding="sm">
        <h2 className="text-lg font-semibold text-white mb-1">
          Crawler &amp; archives
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
                    onChange={(e) => setCrawlerDefaultCategoryId(e.target.value)}
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
                Fetch fresh pages from retailers. Configure delay, limits, and optional
                HTML export below.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-0.5">
                    Delay
                  </label>
                  <select
                    value={crawlerDelaySec}
                    onChange={(e) => setCrawlerDelaySec(Number(e.target.value))}
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
                        <span className="font-mono text-neutral-200">{adapter}</span>
                      </label>
                      <div className="flex items-center gap-1 w-24">
                        <span className="text-xs text-neutral-500">Limit</span>
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
                    {crawlerResult.status === 'started' ? 'Crawler job started' : 'Crawler'}
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
                Background job — watch server logs for per-outcome counts.
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

      {/* Right column: Schedule + Jobs */}
      <div className="flex flex-col gap-4 mt-4 xl:mt-0">

      {/* Crawler Schedule */}
      {!isCronUnavailable && (
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
                          customExpression:
                            d.customExpression || cronStatus.schedule_expression,
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

                  {cronDraft.preset !== 'custom' &&
                    cronStatus.presets[cronDraft.preset] && (
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
                        <span className="text-xs text-gray-500">
                          Current: {cronStatus.preset}
                        </span>
                      )}
                  </div>
                </div>

                {cronSaveError && <ErrorAlert message={cronSaveError} />}
              </div>
            )}
          </Card>
      )}

      {/* Background Jobs */}
        <Card>
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-white">Background Jobs</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Live status of crawler and rescrape jobs. Polls every 5 s while a job is
              running.
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
                      onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
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

      </div>{/* end right column */}
      </div>{/* end grid */}
    </div>
  );
}

export default CrawlerAdmin;
