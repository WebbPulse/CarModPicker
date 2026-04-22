import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert, SuccessAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { useAuth } from '../../hooks/useAuth';
import {
  adminApi,
  type CanonicalLinkGroupMember,
  type CanonicalLinkGroupResponse,
  type RescanResponse,
  type UrlLookupMatch,
} from '../../services/Api';

function formatAxiosError(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: string } } })
      .response;
    if (resp?.data?.detail) return resp.data.detail;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function truncate(value: string | null | undefined, n = 60): string {
  if (!value) return '';
  return value.length > n ? `${value.slice(0, n - 1)}…` : value;
}

function MemberRow({
  member,
  onPromote,
  onUnlink,
  onView,
  isBusy,
}: {
  member: CanonicalLinkGroupMember;
  onPromote: (id: string) => void;
  onUnlink: (id: string) => void;
  onView: (id: string) => void;
  isBusy: boolean;
}) {
  const badge = member.is_canonical ? (
    <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-800/40 border border-emerald-600/60 text-emerald-300 text-[10px] font-semibold uppercase tracking-wide">
      Canonical
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-800/60 border border-gray-700 text-gray-400 text-[10px] font-semibold uppercase tracking-wide">
      Duplicate
    </span>
  );

  return (
    <div className="flex items-start gap-3 p-3 border border-gray-800 rounded-lg bg-gray-950/40">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {badge}
          <span className="text-sm font-semibold text-gray-100 truncate">
            {member.name}
          </span>
          <span
            className="text-[10px] font-mono text-gray-500"
            title="Linker richness score"
          >
            score {member.richness_score}
          </span>
          <span className="text-[10px] text-gray-500">
            src: {member.source}
          </span>
        </div>
        <div className="mt-1 text-[11px] text-gray-500 truncate font-mono">
          {member.id}
        </div>
        {member.product_url ? (
          <a
            href={member.product_url}
            target="_blank"
            rel="noreferrer"
            className="block mt-1 text-[11px] text-sky-400 hover:text-sky-300 truncate"
            title={member.product_url}
          >
            {truncate(member.product_url, 80)}
          </a>
        ) : (
          <div className="mt-1 text-[11px] text-gray-600 italic">
            No product URL
          </div>
        )}
        <div className="mt-1 text-[10px] text-gray-600">
          Created {formatDate(member.created_at)}
        </div>
      </div>
      <div className="flex flex-col gap-1 shrink-0">
        <button
          type="button"
          onClick={() => onView(member.id)}
          className="px-2.5 py-1 rounded border border-gray-700 text-gray-300 text-xs hover:bg-gray-800 transition-colors"
          disabled={isBusy}
        >
          View
        </button>
        {!member.is_canonical && (
          <>
            <button
              type="button"
              onClick={() => onPromote(member.id)}
              className="px-2.5 py-1 rounded bg-emerald-700/40 border border-emerald-600 text-emerald-200 text-xs hover:bg-emerald-700/60 transition-colors disabled:opacity-50"
              disabled={isBusy}
              title="Make this part the canonical of its link group"
            >
              Promote
            </button>
            <button
              type="button"
              onClick={() => onUnlink(member.id)}
              className="px-2.5 py-1 rounded bg-amber-700/40 border border-amber-600 text-amber-200 text-xs hover:bg-amber-700/60 transition-colors disabled:opacity-50"
              disabled={isBusy}
              title="Detach this part so it becomes its own canonical"
            >
              Unlink
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function PartsCuration() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [lookupId, setLookupId] = useState(searchParams.get('part') ?? '');
  const [linkGroup, setLinkGroup] = useState<CanonicalLinkGroupResponse | null>(
    null
  );
  const [isLoadingGroup, setIsLoadingGroup] = useState(false);
  const [groupError, setGroupError] = useState<string | null>(null);

  const [lookupUrl, setLookupUrl] = useState('');
  const [isLookingUpUrl, setIsLookingUpUrl] = useState(false);
  const [urlLookupError, setUrlLookupError] = useState<string | null>(null);
  const [urlMatches, setUrlMatches] = useState<UrlLookupMatch[] | null>(null);

  const [manualDuplicateId, setManualDuplicateId] = useState('');
  const [manualCanonicalId, setManualCanonicalId] = useState('');
  const [manualLinkError, setManualLinkError] = useState<string | null>(null);
  const [manualLinkSuccess, setManualLinkSuccess] = useState<string | null>(
    null
  );
  const [isManualLinking, setIsManualLinking] = useState(false);

  const [isActionBusy, setIsActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [rescanBatchSize, setRescanBatchSize] = useState<string>('500');
  const [rescanResult, setRescanResult] = useState<RescanResponse | null>(null);
  const [isRescanning, setIsRescanning] = useState(false);
  const [rescanError, setRescanError] = useState<string | null>(null);
  const [rescanConfirmOpen, setRescanConfirmOpen] = useState(false);

  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const loadGroup = useCallback(async (partId: string) => {
    const trimmed = partId.trim();
    if (!trimmed) {
      setLinkGroup(null);
      setGroupError(null);
      return;
    }
    setIsLoadingGroup(true);
    setGroupError(null);
    setActionError(null);
    try {
      const resp = await adminApi.getPartLinkGroup(trimmed);
      setLinkGroup(resp.data);
    } catch (err) {
      setLinkGroup(null);
      setGroupError(formatAxiosError(err, 'Failed to load link group.'));
    } finally {
      setIsLoadingGroup(false);
    }
  }, []);

  // Load on mount if ?part= is in the URL.
  useEffect(() => {
    const fromUrl = searchParams.get('part');
    if (fromUrl) {
      void loadGroup(fromUrl);
    }
    // intentional: only on first mount — subsequent URL changes are triggered by handleLookup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLookup = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = lookupId.trim();
    if (!trimmed) return;
    setSearchParams({ part: trimmed }, { replace: true });
    await loadGroup(trimmed);
  };

  const loadGroupForMatch = useCallback(
    async (match: UrlLookupMatch) => {
      setLookupId(match.part_id);
      setSearchParams({ part: match.part_id }, { replace: true });
      await loadGroup(match.part_id);
    },
    [loadGroup, setSearchParams]
  );

  const handleUrlLookup = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = lookupUrl.trim();
    if (!trimmed) return;
    setIsLookingUpUrl(true);
    setUrlLookupError(null);
    setUrlMatches(null);
    try {
      const resp = await adminApi.lookupPartsByProductUrl(trimmed);
      const { matches } = resp.data;
      const [first, second] = matches;
      if (!first) {
        setUrlLookupError('No part has a listing with that product URL.');
        return;
      }
      setUrlMatches(matches);
      if (!second) {
        await loadGroupForMatch(first);
      }
    } catch (err) {
      setUrlLookupError(
        formatAxiosError(err, 'Failed to look up parts by URL.')
      );
    } finally {
      setIsLookingUpUrl(false);
    }
  };

  const handlePromote = async (partId: string) => {
    setIsActionBusy(true);
    setActionError(null);
    try {
      const resp = await adminApi.promotePartToCanonical(partId);
      setLinkGroup(resp.data);
      setLookupId(resp.data.canonical_id);
      setSearchParams({ part: resp.data.canonical_id }, { replace: true });
    } catch (err) {
      setActionError(formatAxiosError(err, 'Promote failed.'));
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleUnlink = async (partId: string) => {
    setIsActionBusy(true);
    setActionError(null);
    try {
      await adminApi.unlinkPartFromCanonical(partId);
      // After unlinking, reload the original anchor so the admin sees the reduced group.
      if (linkGroup) {
        const resp = await adminApi.getPartLinkGroup(linkGroup.canonical_id);
        setLinkGroup(resp.data);
      }
    } catch (err) {
      setActionError(formatAxiosError(err, 'Unlink failed.'));
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleView = (partId: string) => {
    // admin_curation=1 tells ViewPart to skip the duplicate→canonical redirect
    // so the admin can inspect the raw record of whichever member they clicked.
    // ViewPart gates the bypass on is_admin, so non-admins can't use the param.
    void navigate(`/parts/${partId}?admin_curation=1`);
  };

  const handleManualLink = async () => {
    const dup = manualDuplicateId.trim();
    const canonical = manualCanonicalId.trim();
    if (!dup || !canonical) {
      setManualLinkError('Both IDs are required.');
      return;
    }
    if (dup === canonical) {
      setManualLinkError('Duplicate and canonical IDs must differ.');
      return;
    }
    setIsManualLinking(true);
    setManualLinkError(null);
    setManualLinkSuccess(null);
    try {
      const resp = await adminApi.manuallyLinkParts({
        duplicate_id: dup,
        canonical_id: canonical,
      });
      setManualLinkSuccess(
        `Linked ${dup} as duplicate of ${canonical}. Link group now has ${resp.data.members.length} member(s).`
      );
      setLinkGroup(resp.data);
      setLookupId(resp.data.canonical_id);
      setSearchParams({ part: resp.data.canonical_id }, { replace: true });
      setManualDuplicateId('');
      setManualCanonicalId('');
    } catch (err) {
      setManualLinkError(formatAxiosError(err, 'Manual link failed.'));
    } finally {
      setIsManualLinking(false);
    }
  };

  const runRescan = async (dryRun: boolean) => {
    setIsRescanning(true);
    setRescanError(null);
    setRescanConfirmOpen(false);
    try {
      const batch = Number.parseInt(rescanBatchSize, 10);
      const resp = await adminApi.rescanPartsForCanonicalLinking({
        dry_run: dryRun,
        batch_size: Number.isFinite(batch) && batch > 0 ? batch : 500,
      });
      setRescanResult(resp.data);
    } catch (err) {
      setRescanError(formatAxiosError(err, 'Rescan failed.'));
    } finally {
      setIsRescanning(false);
    }
  };

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Parts Curation" />
        <Card>
          <ErrorAlert message="Please log in to access this page." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Parts Curation" />
        <Card>
          <ErrorAlert message="You do not have permission to access this page." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <PageHeader
        title="Parts Curation"
        subtitle="Inspect canonical link groups, promote/unlink duplicates, and re-scan the catalog."
      />

      <Card>
        <SectionHeader title="Look up a link group" />
        <form
          onSubmit={(e) => {
            void handleLookup(e);
          }}
          className="flex flex-col sm:flex-row gap-2 items-end"
        >
          <div className="flex-1">
            <Input
              label="Part ID"
              placeholder="Paste any Part ID (canonical or duplicate)"
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              autoComplete="off"
            />
          </div>
          <ActionButton
            onClick={() => {
              void handleLookup();
            }}
            disabled={isLoadingGroup || !lookupId.trim()}
          >
            {isLoadingGroup ? 'Loading…' : 'Load group'}
          </ActionButton>
        </form>
        {groupError && (
          <div className="mt-3">
            <ErrorAlert message={groupError} />
          </div>
        )}

        <div className="mt-5 pt-4 border-t border-gray-800">
          <form
            onSubmit={(e) => {
              void handleUrlLookup(e);
            }}
            className="flex flex-col sm:flex-row gap-2 items-end"
          >
            <div className="flex-1">
              <Input
                label="Product URL"
                placeholder="Paste a retailer product URL (e.g. https://a90shop.com/products/…)"
                value={lookupUrl}
                onChange={(e) => setLookupUrl(e.target.value)}
                autoComplete="off"
              />
            </div>
            <ActionButton
              onClick={() => {
                void handleUrlLookup();
              }}
              disabled={isLookingUpUrl || !lookupUrl.trim()}
            >
              {isLookingUpUrl ? 'Searching…' : 'Find by URL'}
            </ActionButton>
          </form>
          <p className="mt-2 text-[11px] text-gray-500">
            Matches any Part — catalog canonical, duplicate, or UGC — whose
            PartListing has this exact URL. UGC rows intentionally allow URL
            collisions, so you may see multiple matches.
          </p>
          {urlLookupError && (
            <div className="mt-3">
              <ErrorAlert message={urlLookupError} />
            </div>
          )}
          {urlMatches && urlMatches.length > 1 && (
            <div className="mt-3 space-y-2">
              <div className="text-xs text-gray-400">
                {urlMatches.length} parts match this URL. Pick one to load its
                link group:
              </div>
              {urlMatches.map((m) => (
                <div
                  key={m.part_id}
                  className="flex items-start gap-3 p-2.5 border border-gray-800 rounded-lg bg-gray-950/40"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {m.is_canonical ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-800/40 border border-emerald-600/60 text-emerald-300 text-[10px] font-semibold uppercase tracking-wide">
                          Canonical
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-800/60 border border-gray-700 text-gray-400 text-[10px] font-semibold uppercase tracking-wide">
                          Duplicate
                        </span>
                      )}
                      <span className="text-sm font-semibold text-gray-100 truncate">
                        {m.name}
                      </span>
                      <span className="text-[10px] text-gray-500">
                        src: {m.source}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-gray-500 truncate font-mono">
                      {m.part_id}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void loadGroupForMatch(m)}
                    className="px-2.5 py-1 rounded border border-gray-700 text-gray-300 text-xs hover:bg-gray-800 transition-colors shrink-0"
                    disabled={isLoadingGroup}
                  >
                    Load group
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {linkGroup && (
        <Card>
          <div className="flex items-center justify-between mb-2">
            <SectionHeader
              title={`Link group (${linkGroup.members.length} member${
                linkGroup.members.length === 1 ? '' : 's'
              })`}
            />
            <button
              type="button"
              onClick={() => void loadGroup(linkGroup.canonical_id)}
              className="text-xs text-gray-400 hover:text-white underline"
              disabled={isLoadingGroup || isActionBusy}
            >
              Refresh
            </button>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            Canonical is shown first and drives the public surface record.
            Promote a duplicate to swap roles; unlink to detach a member into
            its own canonical.
          </p>
          {actionError && (
            <div className="mb-3">
              <ErrorAlert message={actionError} />
            </div>
          )}
          <div className="space-y-2">
            {linkGroup.members.map((m) => (
              <MemberRow
                key={m.id}
                member={m}
                onPromote={(id) => void handlePromote(id)}
                onUnlink={(id) => void handleUnlink(id)}
                onView={handleView}
                isBusy={isActionBusy}
              />
            ))}
          </div>
        </Card>
      )}

      <Card>
        <SectionHeader title="Manual link" />
        <p className="text-xs text-gray-500 mb-3">
          Force a cross-group link when the automatic dedup keys don&apos;t
          agree (no shared GTIN or part number). The target must already be a
          canonical.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Duplicate part ID"
            placeholder="Part to become the duplicate"
            value={manualDuplicateId}
            onChange={(e) => setManualDuplicateId(e.target.value)}
            autoComplete="off"
          />
          <Input
            label="Canonical part ID"
            placeholder="Target canonical"
            value={manualCanonicalId}
            onChange={(e) => setManualCanonicalId(e.target.value)}
            autoComplete="off"
          />
        </div>
        <div className="mt-3 flex items-center gap-2">
          <ActionButton
            onClick={() => {
              void handleManualLink();
            }}
            disabled={
              isManualLinking ||
              !manualDuplicateId.trim() ||
              !manualCanonicalId.trim()
            }
          >
            {isManualLinking ? 'Linking…' : 'Link as duplicate'}
          </ActionButton>
        </div>
        {manualLinkError && (
          <div className="mt-3">
            <ErrorAlert message={manualLinkError} />
          </div>
        )}
        {manualLinkSuccess && (
          <div className="mt-3">
            <SuccessAlert message={manualLinkSuccess} />
          </div>
        )}
      </Card>

      <Card>
        <SectionHeader title="Catalog rescan" />
        <p className="text-xs text-gray-500 mb-3">
          Re-runs the canonical linker over every part in the catalog under the
          current dedup rules. Use dry-run first to preview changes. Execute
          applies in per-batch commits.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 items-end">
          <div className="w-40">
            <Input
              label="Batch size"
              type="number"
              value={rescanBatchSize}
              onChange={(e) => setRescanBatchSize(e.target.value)}
              min="1"
              max="5000"
            />
          </div>
          <ActionButton
            onClick={() => {
              void runRescan(true);
            }}
            disabled={isRescanning}
          >
            {isRescanning ? 'Running…' : 'Dry run'}
          </ActionButton>
          <button
            type="button"
            onClick={() => setRescanConfirmOpen(true)}
            className="px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white rounded-xl font-semibold transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isRescanning}
          >
            Execute
          </button>
        </div>
        {rescanError && (
          <div className="mt-3">
            <ErrorAlert message={rescanError} />
          </div>
        )}
        {rescanResult && (
          <div className="mt-4 rounded-lg border border-gray-800 bg-gray-950/60 p-3 text-xs text-gray-300 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                  rescanResult.dry_run
                    ? 'bg-sky-800/40 border border-sky-600 text-sky-200'
                    : 'bg-emerald-800/40 border border-emerald-600 text-emerald-200'
                }`}
              >
                {rescanResult.dry_run ? 'Dry run' : 'Executed'}
              </span>
              <span>
                Scanned{' '}
                <span className="font-semibold text-gray-100">
                  {rescanResult.scanned.toLocaleString()}
                </span>
              </span>
              <span>
                Changes{' '}
                <span className="font-semibold text-gray-100">
                  {rescanResult.changes.toLocaleString()}
                </span>
              </span>
              {rescanResult.diff_truncated && (
                <span className="text-amber-400">
                  Sample truncated (showing first{' '}
                  {rescanResult.diff_sample.length})
                </span>
              )}
            </div>
            {rescanResult.diff_sample.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-[11px] font-mono">
                  <thead>
                    <tr className="text-gray-500 text-left">
                      <th className="py-1 pr-3">Part</th>
                      <th className="py-1 pr-3">Action</th>
                      <th className="py-1 pr-3">Before canonical</th>
                      <th className="py-1">After canonical</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rescanResult.diff_sample.map((entry) => (
                      <tr
                        key={entry.part_id}
                        className="border-t border-gray-800"
                      >
                        <td className="py-1 pr-3 text-gray-300">
                          <button
                            type="button"
                            onClick={() => {
                              setLookupId(entry.part_id);
                              setSearchParams(
                                { part: entry.part_id },
                                { replace: true }
                              );
                              void loadGroup(entry.part_id);
                            }}
                            className="hover:text-white hover:underline text-left"
                            title={entry.part_id}
                          >
                            {truncate(entry.part_id, 13)}
                          </button>
                        </td>
                        <td className="py-1 pr-3 text-gray-400">
                          {entry.action}
                        </td>
                        <td className="py-1 pr-3 text-gray-500">
                          {entry.before_canonical_id
                            ? truncate(entry.before_canonical_id, 13)
                            : '—'}
                        </td>
                        <td className="py-1 text-gray-500">
                          {entry.after_canonical_id
                            ? truncate(entry.after_canonical_id, 13)
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>

      <Dialog
        isOpen={rescanConfirmOpen}
        onClose={() => setRescanConfirmOpen(false)}
        title="Execute catalog rescan?"
      >
        <div className="text-neutral-300">
          <p className="mb-4">
            This will re-run the canonical linker against every Part row and
            commit changes in batches of{' '}
            <span className="font-semibold text-white">
              {rescanBatchSize || '500'}
            </span>
            . Existing canonical links may be re-elected.
          </p>
          <p className="text-xs text-amber-400 mb-6">
            Run a dry-run first if you haven&apos;t — this mutation has no undo.
          </p>
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setRescanConfirmOpen(false)}
              className="glass-button px-6 py-3 rounded-xl text-neutral-300 hover:text-white transition-all"
              disabled={isRescanning}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                void runRescan(false);
              }}
              className="px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white rounded-xl font-semibold transition-all disabled:opacity-50"
              disabled={isRescanning}
            >
              {isRescanning ? 'Running…' : 'Confirm execute'}
            </button>
          </div>
        </div>
      </Dialog>

      {isLoadingGroup && (
        <div className="flex justify-center py-4">
          <LoadingSpinner />
        </div>
      )}
    </div>
  );
}

export default PartsCuration;
