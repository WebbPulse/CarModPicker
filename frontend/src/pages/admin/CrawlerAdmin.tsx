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
  CrawlerAdapterConfig,
  CrawlerAdapterConfigUpdate,
  CrawlerRunRequest,
  CrawlerRunResponse,
  CrawlerSchedule,
  CrawlerScheduleCreate,
  CrawlerScheduleUpdate,
  CrawlerServiceAccount,
  RescrapeArchivesQueuedResponse,
  RescrapeArchivesRequest,
} from '../../services/Api';
import { adminApi, categoriesApi } from '../../services/Api';
import type { CategoryResponse } from '../../types/Api';

// ── Job display helpers ──────────────────────────────────────────────────

/** Parse a server datetime string as UTC. Pydantic serialises naive datetimes
 *  without a timezone suffix, so JS would parse them as local time — causing a
 *  wrong offset equal to the user's UTC offset. Appending 'Z' forces UTC. */
function parseServerDate(s: string): Date {
  if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + 'Z');
  }
  return new Date(s);
}

function fmtElapsed(startedAt: Date, endedAt?: Date | null): string {
  const ms = (endedAt ?? new Date()).getTime() - startedAt.getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function CrawlerRunResult({ summary }: { summary: Record<string, unknown> }) {
  type AdapterResult = {
    adapter: string;
    ingested: number;
    skipped: number;
    errors: number;
    total: number;
  };
  type FailedAdapter = { adapter: string; error: string };
  const totals = summary['summary'] as
    | {
        total_ingested?: number;
        total_skipped?: number;
        total_errors?: number;
      }
    | undefined;
  const results = (summary['results'] ?? []) as AdapterResult[];
  const failed = (summary['failed'] ?? []) as FailedAdapter[];
  return (
    <div className="space-y-2">
      {totals && (
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-900/50 border border-emerald-700/60 text-xs text-emerald-300">
            <span className="font-semibold">{totals.total_ingested ?? 0}</span>{' '}
            ingested
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-800/60 border border-gray-600/60 text-xs text-gray-400">
            <span className="font-semibold">{totals.total_skipped ?? 0}</span>{' '}
            skipped
          </span>
          {(totals.total_errors ?? 0) > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-900/50 border border-red-700/60 text-xs text-red-300">
              <span className="font-semibold">{totals.total_errors}</span>{' '}
              errors
            </span>
          )}
        </div>
      )}
      {results.length > 0 && (
        <div className="rounded border border-gray-700/60 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700/60 bg-gray-900/50">
                <th className="text-left px-2 py-1 text-gray-500 font-medium">
                  Adapter
                </th>
                <th className="text-right px-2 py-1 text-gray-500 font-medium">
                  Total
                </th>
                <th className="text-right px-2 py-1 text-emerald-500/80 font-medium">
                  Ingested
                </th>
                <th className="text-right px-2 py-1 text-gray-500 font-medium">
                  Skipped
                </th>
                <th className="text-right px-2 py-1 text-red-500/80 font-medium">
                  Errors
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.adapter}
                  className="border-b border-gray-700/30 last:border-0"
                >
                  <td className="px-2 py-1 font-mono text-gray-300">
                    {r.adapter}
                  </td>
                  <td className="px-2 py-1 text-right text-gray-400 tabular-nums">
                    {r.total}
                  </td>
                  <td className="px-2 py-1 text-right text-emerald-400 tabular-nums font-medium">
                    {r.ingested}
                  </td>
                  <td className="px-2 py-1 text-right text-gray-400 tabular-nums">
                    {r.skipped}
                  </td>
                  <td
                    className={`px-2 py-1 text-right tabular-nums ${r.errors > 0 ? 'text-red-400 font-medium' : 'text-gray-600'}`}
                  >
                    {r.errors}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {failed.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
            Failed adapters
          </p>
          {failed.map((f) => (
            <div
              key={f.adapter}
              className="rounded px-2 py-1 bg-red-950/40 border border-red-800/40 text-xs"
            >
              <span className="font-mono text-red-300">{f.adapter}</span>
              <span className="text-red-400/70 ml-2">{f.error}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArchiveRescrapeResult({
  summary,
}: {
  summary: Record<string, unknown>;
}) {
  const rows: { label: string; value: number; variant: string }[] = [
    {
      label: 'Parsed OK',
      value: Number(summary['parsed_ok'] ?? 0),
      variant: 'ok',
    },
    {
      label: 'Parse failed',
      value: Number(summary['parse_failed'] ?? 0),
      variant: 'err',
    },
    {
      label: 'Ingest failed',
      value: Number(summary['ingest_failed'] ?? 0),
      variant: 'err',
    },
    {
      label: 'No adapter',
      value: Number(summary['skipped_no_adapter'] ?? 0),
      variant: 'muted',
    },
    {
      label: 'No HTML',
      value: Number(summary['skipped_no_html'] ?? 0),
      variant: 'muted',
    },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {rows.map((r) => (
        <span
          key={r.label}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs ${
            r.value > 0 && r.variant === 'ok'
              ? 'bg-emerald-900/50 border-emerald-700/60 text-emerald-300'
              : r.value > 0 && r.variant === 'err'
                ? 'bg-red-900/50 border-red-700/60 text-red-300'
                : 'bg-gray-800/60 border-gray-600/60 text-gray-500'
          }`}
        >
          <span className="font-semibold">{r.value}</span> {r.label}
        </span>
      ))}
    </div>
  );
}

function JobParams({ job }: { job: BackgroundJob }) {
  const p = job.params;
  if (!p) return null;
  if (job.job_type === 'crawler_run') {
    const adapters = (p['adapters'] as string[] | undefined) ?? [];
    const limits = (p['limits'] as Record<string, number> | undefined) ?? {};
    const globalLimit = p['global_limit'] as number | undefined;
    const delaySec = p['delay_sec'] as number | undefined;
    return (
      <div className="space-y-1.5">
        <div className="flex flex-wrap gap-1">
          {adapters.map((a) => (
            <span
              key={a}
              className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-600/60 font-mono text-xs text-gray-300"
            >
              {a}
              {limits[a] !== undefined && (
                <span className="ml-1 text-gray-500">×{limits[a]}</span>
              )}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          {delaySec !== undefined && (
            <span>
              delay: <span className="text-gray-400">{delaySec}s</span>
            </span>
          )}
          {globalLimit !== undefined && (
            <span>
              global limit: <span className="text-gray-400">{globalLimit}</span>
            </span>
          )}
        </div>
      </div>
    );
  }
  return (
    <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
      {JSON.stringify(p, null, 2)}
    </pre>
  );
}

function jobInlineSummary(job: BackgroundJob): string | null {
  if (job.status === 'running') return null;
  const s = job.result_summary;
  if (!s) return null;
  if (job.job_type === 'crawler_run') {
    const totals = s['summary'] as
      | { total_ingested?: number; total_errors?: number }
      | undefined;
    if (!totals) return null;
    const parts = [`${totals.total_ingested ?? 0} ingested`];
    if ((totals.total_errors ?? 0) > 0)
      parts.push(`${totals.total_errors} errors`);
    return parts.join(' · ');
  }
  if (job.job_type === 'archive_rescrape') {
    const ok = Number(s['parsed_ok'] ?? 0);
    const failed =
      Number(s['parse_failed'] ?? 0) + Number(s['ingest_failed'] ?? 0);
    const parts = [`${ok} parsed`];
    if (failed > 0) parts.push(`${failed} failed`);
    return parts.join(' · ');
  }
  return null;
}

function CrawlerAdmin() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Crawler tools
  const [crawlerAdapters, setCrawlerAdapters] = useState<string[]>([]);
  const [selectedCrawlers, setSelectedCrawlers] = useState<Set<string>>(
    () => new Set()
  );
  const [crawlerLimits, setCrawlerLimits] = useState<Record<string, string>>(
    {}
  );
  const [globalCrawlerLimit, setGlobalCrawlerLimit] = useState<string>('');
  const [crawlerServiceAccount, setCrawlerServiceAccount] =
    useState<CrawlerServiceAccount | null>(null);
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
  const [skipKnownUrls, setSkipKnownUrls] = useState<boolean>(false);

  // Rescrape
  const [isRescrapingArchives, setIsRescrapingArchives] = useState(false);
  const [rescrapeArchivesResult, setRescrapeArchivesResult] =
    useState<RescrapeArchivesQueuedResponse | null>(null);
  const [rescrapeArchivesError, setRescrapeArchivesError] = useState<
    string | null
  >(null);

  // Background jobs
  const [jobsList, setJobsList] = useState<BackgroundJobList | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  // User-defined crawler schedules (N schedules ↔ M adapters; reconciled on
  // enabled/expression change, not on membership change).
  const [schedules, setSchedules] = useState<CrawlerSchedule[]>([]);
  const [schedulePresets, setSchedulePresets] = useState<
    Record<string, string>
  >({});
  const [scheduleDrafts, setScheduleDrafts] = useState<
    Record<string, { preset: string; customExpression: string }>
  >({});
  const [isLoadingSchedules, setIsLoadingSchedules] = useState(false);
  const [isSchedulesUnavailable, setIsSchedulesUnavailable] = useState(false);
  const [savingScheduleId, setSavingScheduleId] = useState<string | null>(null);
  const [scheduleSaveError, setScheduleSaveError] = useState<string | null>(
    null
  );
  const [isReconcilingAll, setIsReconcilingAll] = useState(false);

  // Create-schedule form state
  const [isCreatingSchedule, setIsCreatingSchedule] = useState(false);
  const [newScheduleName, setNewScheduleName] = useState('');
  const [newSchedulePreset, setNewSchedulePreset] = useState<
    'monthly' | 'weekly' | 'daily' | 'custom'
  >('monthly');
  const [newScheduleCustomExpression, setNewScheduleCustomExpression] =
    useState('');
  const [newScheduleAdapters, setNewScheduleAdapters] = useState<string[]>([]);

  // Per-adapter retailer tuning (separate from schedule membership).
  const [adapterConfigs, setAdapterConfigs] = useState<CrawlerAdapterConfig[]>(
    []
  );
  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false);
  const [savingConfigName, setSavingConfigName] = useState<string | null>(null);
  const [configSaveError, setConfigSaveError] = useState<string | null>(null);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const fetchCrawlers = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingCrawlers(true);
    try {
      const [adaptersRes, categoriesRes, serviceAccountRes] = await Promise.all(
        [
          adminApi.getCrawlers(),
          categoriesApi.getCategories(),
          adminApi.getCrawlerServiceAccount(),
        ]
      );
      setCrawlerAdapters(adaptersRes.data.adapters);
      setCrawlerCategories(categoriesRes.data);
      setCrawlerServiceAccount(serviceAccountRes.data);
      const otherCategory = categoriesRes.data.find(
        (c: CategoryResponse) => c.name.toLowerCase() === 'other'
      );
      if (otherCategory) {
        setCrawlerDefaultCategoryId(String(otherCategory.id));
      }
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

  const presetForExpression = useCallback(
    (expression: string, presets: Record<string, string>): string => {
      for (const [name, expr] of Object.entries(presets)) {
        if (expr === expression) return name;
      }
      return 'custom';
    },
    []
  );

  const fetchSchedules = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingSchedules(true);
    try {
      const res = await adminApi.listCrawlerSchedules();
      setSchedules(res.data.items);
      setSchedulePresets(res.data.presets);
      setScheduleDrafts(
        Object.fromEntries(
          res.data.items.map((row) => {
            const preset = presetForExpression(
              row.schedule_expression,
              res.data.presets
            );
            return [
              row.id,
              {
                preset,
                customExpression:
                  preset === 'custom' ? row.schedule_expression : '',
              },
            ];
          })
        )
      );
      setIsSchedulesUnavailable(false);
    } catch {
      setIsSchedulesUnavailable(true);
    } finally {
      setIsLoadingSchedules(false);
    }
  }, [user?.is_admin, presetForExpression]);

  const fetchAdapterConfigs = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingConfigs(true);
    try {
      const res = await adminApi.listCrawlerAdapterConfigs();
      setAdapterConfigs(res.data.items);
    } catch {
      setAdapterConfigs([]);
    } finally {
      setIsLoadingConfigs(false);
    }
  }, [user?.is_admin]);

  const mergeScheduleRow = (row: CrawlerSchedule) => {
    setSchedules((prev) => prev.map((r) => (r.id === row.id ? row : r)));
    setScheduleDrafts((prev) => {
      const preset = presetForExpression(
        row.schedule_expression,
        schedulePresets
      );
      return {
        ...prev,
        [row.id]: {
          preset,
          customExpression: preset === 'custom' ? row.schedule_expression : '',
        },
      };
    });
  };

  const handleSaveSchedule = async (
    scheduleId: string,
    patch: CrawlerScheduleUpdate
  ) => {
    setSavingScheduleId(scheduleId);
    setScheduleSaveError(null);
    try {
      const res = await adminApi.updateCrawlerSchedule(scheduleId, patch);
      mergeScheduleRow(res.data);
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to update schedule.'
      );
    } finally {
      setSavingScheduleId(null);
    }
  };

  const handleToggleAdapterInSchedule = async (
    row: CrawlerSchedule,
    adapterName: string
  ) => {
    const current = row.adapters.map((a) => a.adapter_name);
    const next = current.includes(adapterName)
      ? current.filter((n) => n !== adapterName)
      : [...current, adapterName];
    await handleSaveSchedule(row.id, { adapters: next });
  };

  const handleCreateSchedule = async () => {
    const name = newScheduleName.trim();
    if (!name) return;
    setIsCreatingSchedule(true);
    setScheduleSaveError(null);
    const body: CrawlerScheduleCreate = {
      name,
      enabled: false,
      adapters: newScheduleAdapters,
      ...(newSchedulePreset === 'custom'
        ? { schedule_expression: newScheduleCustomExpression.trim() }
        : { preset: newSchedulePreset }),
    };
    try {
      await adminApi.createCrawlerSchedule(body);
      setNewScheduleName('');
      setNewSchedulePreset('monthly');
      setNewScheduleCustomExpression('');
      setNewScheduleAdapters([]);
      await fetchSchedules();
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to create schedule.'
      );
    } finally {
      setIsCreatingSchedule(false);
    }
  };

  const handleDeleteSchedule = async (row: CrawlerSchedule) => {
    if (
      !window.confirm(`Delete schedule '${row.name}'? This cannot be undone.`)
    )
      return;
    setSavingScheduleId(row.id);
    setScheduleSaveError(null);
    try {
      await adminApi.deleteCrawlerSchedule(row.id);
      setSchedules((prev) => prev.filter((r) => r.id !== row.id));
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to delete schedule.'
      );
    } finally {
      setSavingScheduleId(null);
    }
  };

  const handleReconcileAll = async () => {
    setIsReconcilingAll(true);
    setScheduleSaveError(null);
    try {
      await adminApi.reconcileCrawlerSchedules();
      await fetchSchedules();
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to reconcile schedules.'
      );
    } finally {
      setIsReconcilingAll(false);
    }
  };

  const handleSaveAdapterConfig = async (
    adapterName: string,
    patch: CrawlerAdapterConfigUpdate
  ) => {
    setSavingConfigName(adapterName);
    setConfigSaveError(null);
    try {
      const res = await adminApi.updateCrawlerAdapterConfig(adapterName, patch);
      setAdapterConfigs((prev) =>
        prev.map((r) => (r.adapter_name === adapterName ? res.data : r))
      );
    } catch (e) {
      setConfigSaveError(
        e instanceof Error
          ? `${adapterName}: ${e.message}`
          : `${adapterName}: failed to update tuning.`
      );
    } finally {
      setSavingConfigName(null);
    }
  };

  useEffect(() => {
    void fetchCrawlers();
    void fetchJobs();
    void fetchSchedules();
    void fetchAdapterConfigs();
  }, [fetchCrawlers, fetchJobs, fetchSchedules, fetchAdapterConfigs]);

  // Poll jobs every 5 s while any job is running
  useEffect(() => {
    const hasRunning = jobsList?.items.some((j) => j.status === 'running');
    if (!hasRunning) return;
    const id = setInterval(() => {
      void fetchJobs();
    }, 5000);
    return () => clearInterval(id);
  }, [jobsList, fetchJobs]);

  // Tick every second to keep elapsed-time display fresh for running jobs
  const [, setElapsedTick] = useState(0);
  useEffect(() => {
    const hasRunning = jobsList?.items.some((j) => j.status === 'running');
    if (!hasRunning) return;
    const id = setInterval(() => setElapsedTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [jobsList]);

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
    if (!crawlerDefaultCategoryId) {
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
        crawler_default_category_id: crawlerDefaultCategoryId,
        parallel: true,
        delay_sec: crawlerDelaySec,
      };
      if (Object.keys(limits).length > 0) body.limits = limits;
      if (useGlobalLimit && globalLimitNum != null && globalLimitNum > 0)
        body.global_limit = globalLimitNum;
      if (crawlerHtmlSaveDir.trim()) {
        body.crawl_html_save_dir = crawlerHtmlSaveDir.trim();
      }
      if (skipKnownUrls) body.skip_known_urls = true;
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
    if (!crawlerDefaultCategoryId) {
      setRescrapeArchivesError('Select a default category.');
      return;
    }

    setIsRescrapingArchives(true);
    setRescrapeArchivesResult(null);
    setRescrapeArchivesError(null);
    try {
      const body: RescrapeArchivesRequest = {
        default_category_id: crawlerDefaultCategoryId,
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
            Run live retailer crawls or re-process stored HTML archives. Crawler
            user and default category apply to both.
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
                      Crawler service account
                    </label>
                    {crawlerServiceAccount ? (
                      <div className="flex items-center gap-2 px-3 py-1.5 min-h-[36px] rounded-lg border border-white/10 bg-gray-800/60 text-sm">
                        <span className="font-mono text-neutral-200">
                          {crawlerServiceAccount.username}
                        </span>
                        <span className="text-xs text-neutral-500">
                          #{crawlerServiceAccount.id}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center px-3 py-1.5 min-h-[36px] rounded-lg border border-yellow-600/40 bg-yellow-900/20 text-xs text-yellow-400">
                        Not found — restart app
                      </div>
                    )}
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
                  Fetch fresh pages from retailers. Configure delay, limits, and
                  optional HTML export below.
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
                  <div className="md:col-span-2 flex items-center gap-2">
                    <input
                      id="skip-known-urls"
                      type="checkbox"
                      checked={skipKnownUrls}
                      onChange={(e) => setSkipKnownUrls(e.target.checked)}
                      className="h-4 w-4 rounded border-neutral-600 bg-neutral-800 text-emerald-500 focus:ring-emerald-500"
                    />
                    <label
                      htmlFor="skip-known-urls"
                      className="text-sm text-neutral-300 select-none cursor-pointer"
                    >
                      Skip already-archived URLs
                    </label>
                    <span className="text-xs text-neutral-500">
                      (omit URLs with parse_status=parsed from this run)
                    </span>
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
                  <div className="space-y-1.5">
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
                  Re-run parse → ingest on every URL that has archived HTML
                  (same pipeline as a live crawl: parts, category and car
                  inference, listings, and price history when a price is found).
                  Stale snapshots still record a price observation.
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
          {/* Crawler Schedules */}
          <Card>
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Crawler Schedules
                </h2>
                <p className="text-sm text-gray-400 mt-0.5">
                  Each schedule fires one EventBridge trigger and runs all its
                  member adapters in parallel. Mix adapters freely —
                  per-retailer tuning below travels with the adapter.
                </p>
              </div>
              <ActionButton
                onClick={() => void handleReconcileAll()}
                disabled={
                  isReconcilingAll ||
                  isLoadingSchedules ||
                  isSchedulesUnavailable
                }
                className="bg-gray-700 hover:bg-gray-600 text-white text-xs py-1 px-3 shrink-0"
              >
                {isReconcilingAll ? 'Reconciling…' : 'Reconcile all'}
              </ActionButton>
            </div>

            {isSchedulesUnavailable && (
              <div className="flex items-start gap-2 p-3 mb-4 rounded-lg border border-yellow-600/50 bg-yellow-900/20 text-yellow-300 text-sm">
                <span className="mt-0.5 shrink-0">⚠</span>
                <span>
                  Schedules unavailable — could not load from the backend. This
                  feature requires AWS EventBridge plumbing that may not be
                  configured in this environment.
                </span>
              </div>
            )}

            {scheduleSaveError && (
              <div className="mb-4">
                <ErrorAlert message={scheduleSaveError} />
              </div>
            )}

            {/* Create new schedule */}
            <div className="mb-4 p-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/30">
              <p className="text-xs font-medium text-gray-400 mb-2">
                New schedule
              </p>
              <div className="space-y-2">
                <Input
                  id="new-schedule-name"
                  placeholder="e.g. retailers-daily (letters, digits, hyphens)"
                  value={newScheduleName}
                  onChange={(e) =>
                    setNewScheduleName(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9-]+/g, '-')
                        .replace(/^-+/, '')
                        .slice(0, 26)
                    )
                  }
                />
                <div className="flex flex-wrap gap-1.5">
                  {(['monthly', 'weekly', 'daily', 'custom'] as const).map(
                    (p) => (
                      <button
                        key={p}
                        onClick={() => setNewSchedulePreset(p)}
                        className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                          newSchedulePreset === p
                            ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                            : 'border-gray-600 text-gray-400 hover:border-gray-400'
                        }`}
                      >
                        {p.charAt(0).toUpperCase() + p.slice(1)}
                      </button>
                    )
                  )}
                </div>
                {newSchedulePreset === 'custom' && (
                  <input
                    type="text"
                    value={newScheduleCustomExpression}
                    onChange={(e) =>
                      setNewScheduleCustomExpression(e.target.value)
                    }
                    placeholder="cron(0 2 1 * ? *)"
                    className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
                  />
                )}
                <div className="flex flex-wrap gap-1.5">
                  {crawlerAdapters.map((name) => {
                    const checked = newScheduleAdapters.includes(name);
                    return (
                      <button
                        key={name}
                        onClick={() =>
                          setNewScheduleAdapters((prev) =>
                            checked
                              ? prev.filter((n) => n !== name)
                              : [...prev, name]
                          )
                        }
                        className={`px-2.5 py-0.5 text-xs rounded-full border font-mono transition-colors ${
                          checked
                            ? 'border-emerald-500 bg-emerald-900/40 text-emerald-300'
                            : 'border-gray-600 text-gray-400 hover:border-gray-400'
                        }`}
                      >
                        {name}
                      </button>
                    );
                  })}
                </div>
                <ActionButton
                  onClick={() => void handleCreateSchedule()}
                  disabled={
                    isCreatingSchedule ||
                    !newScheduleName.trim() ||
                    newScheduleAdapters.length === 0 ||
                    (newSchedulePreset === 'custom' &&
                      !newScheduleCustomExpression.trim())
                  }
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs py-1 px-3"
                >
                  {isCreatingSchedule ? 'Creating…' : 'Create schedule'}
                </ActionButton>
              </div>
            </div>

            {isLoadingSchedules && schedules.length === 0 ? (
              <div className="flex justify-center py-6">
                <LoadingSpinner size="sm" />
              </div>
            ) : schedules.length === 0 ? (
              <p className="text-sm text-gray-500 py-3">
                No schedules yet — create one above.
              </p>
            ) : (
              <div className="space-y-3">
                {schedules.map((row) => {
                  const draft = scheduleDrafts[row.id] ?? {
                    preset: presetForExpression(
                      row.schedule_expression,
                      schedulePresets
                    ),
                    customExpression: '',
                  };
                  const isSaving = savingScheduleId === row.id;
                  const reconcileFailed = !!row.last_reconcile_error;
                  const memberNames = new Set(
                    row.adapters.map((a) => a.adapter_name)
                  );
                  return (
                    <div
                      key={row.id}
                      className="p-3 rounded-lg border border-gray-700 bg-gray-900/40"
                    >
                      <div className="flex items-center justify-between gap-3 mb-3">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-100 font-mono truncate">
                            {row.name}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {row.enabled ? (
                              <span className="text-emerald-400">Enabled</span>
                            ) : (
                              <span>Disabled</span>
                            )}
                            {' · '}
                            <span className="font-mono">
                              {row.schedule_expression}
                            </span>
                          </p>
                        </div>
                        <button
                          onClick={() =>
                            void handleSaveSchedule(row.id, {
                              enabled: !row.enabled,
                            })
                          }
                          disabled={isSaving}
                          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
                            row.enabled ? 'bg-emerald-600' : 'bg-gray-600'
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ${
                              row.enabled ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        </button>
                      </div>

                      <div className="space-y-3">
                        {/* Adapter membership chips */}
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1.5">
                            Adapters ({row.adapters.length})
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {crawlerAdapters.map((name) => {
                              const selected = memberNames.has(name);
                              return (
                                <button
                                  key={name}
                                  onClick={() =>
                                    void handleToggleAdapterInSchedule(
                                      row,
                                      name
                                    )
                                  }
                                  disabled={isSaving}
                                  className={`px-2.5 py-0.5 text-xs rounded-full border font-mono transition-colors disabled:opacity-50 ${
                                    selected
                                      ? 'border-emerald-500 bg-emerald-900/40 text-emerald-300'
                                      : 'border-gray-600 text-gray-500 hover:border-gray-400'
                                  }`}
                                >
                                  {name}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Interval pills */}
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1.5">
                            Interval
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {(['monthly', 'weekly', 'daily'] as const).map(
                              (p) => (
                                <button
                                  key={p}
                                  onClick={() =>
                                    setScheduleDrafts((prev) => ({
                                      ...prev,
                                      [row.id]: {
                                        preset: p,
                                        customExpression: '',
                                      },
                                    }))
                                  }
                                  className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                                    draft.preset === p
                                      ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                                      : 'border-gray-600 text-gray-400 hover:border-gray-400'
                                  }`}
                                >
                                  {p.charAt(0).toUpperCase() + p.slice(1)}
                                </button>
                              )
                            )}
                            <button
                              onClick={() =>
                                setScheduleDrafts((prev) => ({
                                  ...prev,
                                  [row.id]: {
                                    preset: 'custom',
                                    customExpression:
                                      draft.customExpression ||
                                      row.schedule_expression,
                                  },
                                }))
                              }
                              className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                                draft.preset === 'custom'
                                  ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                                  : 'border-gray-600 text-gray-400 hover:border-gray-400'
                              }`}
                            >
                              Custom
                            </button>
                          </div>
                          {draft.preset === 'custom' && (
                            <input
                              type="text"
                              value={draft.customExpression}
                              onChange={(e) =>
                                setScheduleDrafts((prev) => ({
                                  ...prev,
                                  [row.id]: {
                                    ...draft,
                                    customExpression: e.target.value,
                                  },
                                }))
                              }
                              placeholder="cron(0 2 1 * ? *)"
                              className="mt-1.5 w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
                            />
                          )}
                          {draft.preset !== 'custom' &&
                            schedulePresets[draft.preset] && (
                              <p className="text-xs text-gray-500 font-mono mt-1">
                                {schedulePresets[draft.preset]}
                              </p>
                            )}
                        </div>

                        {/* Save interval / delete row */}
                        <div className="flex items-center gap-2 pt-1">
                          {draft.preset === 'custom' ||
                          presetForExpression(
                            row.schedule_expression,
                            schedulePresets
                          ) !== draft.preset ? (
                            <ActionButton
                              onClick={() =>
                                void handleSaveSchedule(
                                  row.id,
                                  draft.preset === 'custom'
                                    ? {
                                        schedule_expression:
                                          draft.customExpression,
                                      }
                                    : {
                                        preset: draft.preset as
                                          | 'monthly'
                                          | 'weekly'
                                          | 'daily',
                                      }
                                )
                              }
                              disabled={
                                isSaving ||
                                (draft.preset === 'custom' &&
                                  !draft.customExpression.trim())
                              }
                              className="bg-blue-600 hover:bg-blue-700 text-white text-xs py-1 px-3"
                            >
                              {isSaving ? 'Saving…' : 'Save interval'}
                            </ActionButton>
                          ) : null}
                          <button
                            onClick={() => void handleDeleteSchedule(row)}
                            disabled={isSaving}
                            className="ml-auto text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </div>

                        {/* Reconcile status */}
                        <div className="text-xs text-gray-500 pt-1 border-t border-gray-700/50">
                          {reconcileFailed ? (
                            <span className="text-red-400">
                              Last reconcile failed: {row.last_reconcile_error}
                            </span>
                          ) : row.last_reconciled_at ? (
                            <span>
                              Last reconciled{' '}
                              {parseServerDate(
                                row.last_reconciled_at
                              ).toLocaleString()}
                            </span>
                          ) : (
                            <span>Not yet reconciled to AWS.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Adapter Tuning */}
          <Card>
            <div className="mb-4">
              <h2 className="text-xl font-semibold text-white">
                Adapter Tuning
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Per-retailer request delay, run limit, and default category.
                Edits take effect on the next run of any schedule this adapter
                is a member of — no AWS reconcile needed.
              </p>
            </div>

            {configSaveError && (
              <div className="mb-4">
                <ErrorAlert message={configSaveError} />
              </div>
            )}

            {isLoadingConfigs && adapterConfigs.length === 0 ? (
              <div className="flex justify-center py-6">
                <LoadingSpinner size="sm" />
              </div>
            ) : adapterConfigs.length === 0 ? (
              <p className="text-sm text-gray-500 py-3">
                No adapters registered yet.
              </p>
            ) : (
              <div className="space-y-3">
                {adapterConfigs.map((row) => {
                  const isSaving = savingConfigName === row.adapter_name;
                  return (
                    <div
                      key={row.id}
                      className="p-3 rounded-lg border border-gray-700 bg-gray-900/40"
                    >
                      <p className="text-sm font-medium text-gray-100 font-mono mb-3">
                        {row.adapter_name}
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label
                            htmlFor={`tune-delay-${row.adapter_name}`}
                            className="block text-xs font-medium text-gray-400 mb-1"
                          >
                            Delay (s)
                          </label>
                          <select
                            id={`tune-delay-${row.adapter_name}`}
                            value={String(row.delay_sec)}
                            onChange={(e) =>
                              void handleSaveAdapterConfig(row.adapter_name, {
                                delay_sec: Number(e.target.value),
                              })
                            }
                            disabled={isSaving}
                            className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                          >
                            {[2.5, 5, 10, 15, 30].map((v) => (
                              <option key={v} value={String(v)}>
                                {v}s
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label
                            htmlFor={`tune-limit-${row.adapter_name}`}
                            className="block text-xs font-medium text-gray-400 mb-1"
                          >
                            Per-run limit
                          </label>
                          <Input
                            id={`tune-limit-${row.adapter_name}`}
                            type="number"
                            min="1"
                            value={
                              row.per_run_limit == null
                                ? ''
                                : String(row.per_run_limit)
                            }
                            placeholder="Unlimited"
                            onBlur={(e) => {
                              const raw = e.target.value.trim();
                              if (raw === '') {
                                if (row.per_run_limit != null) {
                                  void handleSaveAdapterConfig(
                                    row.adapter_name,
                                    { clear_per_run_limit: true }
                                  );
                                }
                              } else {
                                const n = Number(raw);
                                if (
                                  Number.isFinite(n) &&
                                  n >= 1 &&
                                  n !== row.per_run_limit
                                ) {
                                  void handleSaveAdapterConfig(
                                    row.adapter_name,
                                    { per_run_limit: n }
                                  );
                                }
                              }
                            }}
                            disabled={isSaving}
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-1 gap-3 mt-3">
                        <label className="inline-flex items-center gap-2 text-xs text-gray-300">
                          <input
                            type="checkbox"
                            checked={row.skip_known_urls}
                            onChange={(e) =>
                              void handleSaveAdapterConfig(row.adapter_name, {
                                skip_known_urls: e.target.checked,
                              })
                            }
                            disabled={isSaving}
                            className="h-3.5 w-3.5 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                          />
                          Skip URLs already archived as parsed
                        </label>
                        <div>
                          <label
                            htmlFor={`tune-cat-${row.adapter_name}`}
                            className="block text-xs font-medium text-gray-400 mb-1"
                          >
                            Default category (new parts)
                          </label>
                          <select
                            id={`tune-cat-${row.adapter_name}`}
                            value={row.default_category_id}
                            onChange={(e) =>
                              void handleSaveAdapterConfig(row.adapter_name, {
                                default_category_id: e.target.value,
                              })
                            }
                            disabled={
                              isSaving || crawlerCategories.length === 0
                            }
                            className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                          >
                            {crawlerCategories.map((c) => (
                              <option key={c.id} value={String(c.id)}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Background Jobs */}
          <Card>
            <div className="mb-4">
              <h2 className="text-xl font-semibold text-white">
                Background Jobs
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Live status of crawler and rescrape jobs. Polls every 5 s while
                a job is running.
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
              <p className="text-sm text-gray-500 text-center py-6">
                No jobs yet.
              </p>
            )}

            {jobsList && jobsList.items.length > 0 && (
              <div className="space-y-2">
                {jobsList.items.map((job: BackgroundJob) => {
                  const isExpanded = expandedJobId === job.id;
                  const isRunning = job.status === 'running';
                  const statusColor =
                    job.status === 'completed'
                      ? 'text-emerald-400'
                      : job.status === 'failed'
                        ? 'text-red-400'
                        : isRunning
                          ? 'text-yellow-400'
                          : 'text-gray-400';
                  const statusBg =
                    job.status === 'completed'
                      ? 'border-emerald-800/60 bg-emerald-950/30'
                      : job.status === 'failed'
                        ? 'border-red-800/60 bg-red-950/30'
                        : isRunning
                          ? 'border-yellow-800/60 bg-yellow-950/30'
                          : 'border-gray-700 bg-gray-900/30';

                  const typeLabel =
                    job.job_type === 'crawler_run'
                      ? 'Crawler Run'
                      : job.job_type === 'archive_rescrape'
                        ? 'Archive Rescrape'
                        : job.job_type;

                  const startedAt = parseServerDate(job.started_at);
                  const completedAt = job.completed_at
                    ? parseServerDate(job.completed_at)
                    : null;
                  const elapsed = fmtElapsed(startedAt, completedAt);
                  const inlineSummary = jobInlineSummary(job);

                  return (
                    <div
                      key={job.id}
                      className={`rounded-lg border text-sm ${statusBg}`}
                    >
                      {/* Indeterminate progress bar for running jobs */}
                      {isRunning && (
                        <div className="h-0.5 w-full rounded-t-lg overflow-hidden bg-yellow-950/50">
                          <div className="h-full bg-yellow-400/70 animate-[progress-indeterminate_1.8s_ease-in-out_infinite] w-1/3" />
                        </div>
                      )}
                      <div className="px-3 py-2">
                        <button
                          className="w-full flex items-center justify-between gap-2 text-left"
                          onClick={() =>
                            setExpandedJobId(isExpanded ? null : job.id)
                          }
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {/* Status indicator */}
                            {isRunning ? (
                              <span className="relative flex h-2 w-2 shrink-0">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-400" />
                              </span>
                            ) : null}
                            <span
                              className={`font-semibold text-xs uppercase tracking-wide shrink-0 ${statusColor}`}
                            >
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
                            {inlineSummary && (
                              <span
                                className={`tabular-nums ${job.status === 'failed' ? 'text-red-400/70' : 'text-gray-400'}`}
                              >
                                {inlineSummary}
                              </span>
                            )}
                            <span className="tabular-nums">
                              {isRunning ? (
                                <span className="text-yellow-400/80">
                                  {elapsed}
                                </span>
                              ) : (
                                elapsed
                              )}
                            </span>
                            <span className="text-gray-600">
                              {isExpanded ? '▲' : '▼'}
                            </span>
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="mt-2 pt-2 border-t border-gray-700/60 space-y-3">
                            {/* Started at */}
                            <p className="text-xs text-gray-500">
                              Started {startedAt.toLocaleString()}
                              {completedAt && (
                                <> · Finished {completedAt.toLocaleString()}</>
                              )}
                            </p>

                            {/* Params */}
                            {job.params && (
                              <div>
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                                  Parameters
                                </p>
                                <JobParams job={job} />
                              </div>
                            )}

                            {/* Running: no result yet */}
                            {isRunning && (
                              <div className="flex items-center gap-2 text-xs text-yellow-400/80">
                                <span className="relative flex h-1.5 w-1.5">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-yellow-400" />
                                </span>
                                Running for {elapsed} — results will appear when
                                the job completes
                              </div>
                            )}

                            {/* Result summary */}
                            {job.result_summary && (
                              <div>
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                                  Result
                                </p>
                                {job.job_type === 'crawler_run' ? (
                                  <CrawlerRunResult
                                    summary={job.result_summary}
                                  />
                                ) : job.job_type === 'archive_rescrape' ? (
                                  <ArchiveRescrapeResult
                                    summary={job.result_summary}
                                  />
                                ) : (
                                  <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                                    {JSON.stringify(
                                      job.result_summary,
                                      null,
                                      2
                                    )}
                                  </pre>
                                )}
                              </div>
                            )}

                            {/* Error */}
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

                            {/* Cancel */}
                            {isRunning && (
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
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
        {/* end right column */}
      </div>
      {/* end grid */}
    </div>
  );
}

export default CrawlerAdmin;
