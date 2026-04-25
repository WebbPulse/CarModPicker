// Account-level price-drop alerts management page (M002/S07/T05).
// Lists the current user's active alerts (one row per part) and lets them
// unsubscribe inline. Reachable only via /account/alerts inside the
// ProtectedRoute group, so we can assume the user is authenticated.
//
// The token-as-auth public unsubscribe endpoint redirects here with
// ?status=success or ?status=error after a one-click email-link unsubscribe;
// surface a status banner so the redirect lands somewhere meaningful.
import { useCallback, useEffect, useState } from 'react';
import type { AxiosError } from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { partPriceAlertsApi } from '../../api/part_price_alerts';
import { partsApi } from '../../api/parts';
import { ErrorAlert, SuccessAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { Button } from '../../components/ui/button';
import type { PartPriceAlertRead, PartRead } from '../../types/Api';

const fetchMineRequestFn = () => partPriceAlertsApi.listMine();

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

interface AlertRowProps {
  alert: PartPriceAlertRead;
  partName: string | null;
  partLoading: boolean;
  onUnsubscribed: (alertId: string) => void;
}

function AlertRow({
  alert,
  partName,
  partLoading,
  onUnsubscribed,
}: AlertRowProps) {
  const [submitting, setSubmitting] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  const handleUnsubscribe = async () => {
    setRowError(null);
    setSubmitting(true);
    try {
      await partPriceAlertsApi.deleteAlert(alert.id);
      onUnsubscribed(alert.id);
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      const detail = axiosErr.response?.data?.detail;
      setRowError(
        typeof detail === 'string'
          ? detail
          : 'Could not remove this alert. Please try again.'
      );
      setSubmitting(false);
    }
  };

  return (
    <li
      data-testid="alert-row"
      data-alert-id={alert.id}
      className="flex flex-wrap items-center justify-between gap-3 p-4 bg-gray-800/60 rounded-lg border border-gray-700/50"
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium text-white">
          <Link
            to={`/parts/${alert.part_id}`}
            className="text-blue-400 hover:text-blue-300 underline transition-colors"
            data-testid="alert-row-part-link"
          >
            {partLoading
              ? 'Loading part…'
              : (partName ?? 'Part unavailable')}
          </Link>
        </div>
        <div className="mt-1 text-sm text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
          <span data-testid="alert-row-threshold">
            Threshold: {formatCents(alert.threshold_cents)}
          </span>
          <span data-testid="alert-row-created">
            Created {formatDate(alert.created_at)}
          </span>
          <span data-testid="alert-row-last-fired">
            {alert.last_fired_at
              ? `Last sent ${formatDate(alert.last_fired_at)}`
              : 'Not sent yet'}
          </span>
        </div>
        {rowError && (
          <p
            className="mt-2 text-sm text-red-400"
            role="alert"
            data-testid="alert-row-error"
          >
            {rowError}
          </p>
        )}
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          void handleUnsubscribe();
        }}
        loading={submitting}
        data-testid="alert-row-unsubscribe"
      >
        Unsubscribe
      </Button>
    </li>
  );
}

function AccountAlerts() {
  useDocumentMeta({
    title: 'Your price-drop alerts',
    description:
      'Manage the parts you’re watching for price drops on CarModPicker.',
    canonicalPath: '/account/alerts',
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status');

  const {
    data: alerts,
    isLoading,
    error,
    executeRequest: fetchAlerts,
  } = useApiRequest(fetchMineRequestFn);

  const [partsById, setPartsById] = useState<Record<string, PartRead | null>>(
    {}
  );
  const [loadingPartIds, setLoadingPartIds] = useState<Set<string>>(new Set());
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());

  // Initial load.
  useEffect(() => {
    void fetchAlerts(undefined);
  }, [fetchAlerts]);

  // Per-row part hydration. Per the task plan: simple lazy fetch via
  // partsApi.getPart for each unique part_id. Flag scale issues in Follow-ups
  // if alert lists ever grow large enough to make this O(N) request fanout
  // a problem (today: capped by per-user list, expected single digits).
  useEffect(() => {
    if (!alerts) return;
    const uniqueIds = Array.from(new Set(alerts.map((a) => a.part_id)));
    const idsToFetch = uniqueIds.filter(
      (id) => !(id in partsById) && !loadingPartIds.has(id)
    );
    if (idsToFetch.length === 0) return;

    setLoadingPartIds((prev) => {
      const next = new Set(prev);
      idsToFetch.forEach((id) => next.add(id));
      return next;
    });

    let cancelled = false;
    Promise.allSettled(idsToFetch.map((id) => partsApi.getPart(id))).then(
      (results) => {
        if (cancelled) return;
        const updates: Record<string, PartRead | null> = {};
        idsToFetch.forEach((id, i) => {
          const r = results[i];
          updates[id] = r && r.status === 'fulfilled' ? r.value.data : null;
        });
        setPartsById((prev) => ({ ...prev, ...updates }));
        setLoadingPartIds((prev) => {
          const next = new Set(prev);
          idsToFetch.forEach((id) => next.delete(id));
          return next;
        });
      }
    );
    return () => {
      cancelled = true;
    };
  }, [alerts, partsById, loadingPartIds]);

  const handleUnsubscribed = useCallback(
    (alertId: string) => {
      setRemovedIds((prev) => {
        const next = new Set(prev);
        next.add(alertId);
        return next;
      });
    },
    []
  );

  const dismissStatusBanner = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('status');
    setSearchParams(next, { replace: true });
  };

  const visibleAlerts = (alerts ?? []).filter((a) => !removedIds.has(a.id));

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Your price-drop alerts" />

      {status === 'success' && (
        <div className="mb-4" data-testid="status-banner-success">
          <SuccessAlert message="You’ve been unsubscribed from that price-drop alert." />
          <button
            type="button"
            onClick={dismissStatusBanner}
            className="mt-2 text-xs text-gray-400 hover:text-gray-200 underline"
          >
            Dismiss
          </button>
        </div>
      )}
      {status === 'error' && (
        <div className="mb-4" data-testid="status-banner-error">
          <ErrorAlert message="That unsubscribe link is invalid or has already been used." />
          <button
            type="button"
            onClick={dismissStatusBanner}
            className="mt-2 text-xs text-gray-400 hover:text-gray-200 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <Card>
        <SectionHeader title="Active alerts" />

        {isLoading && !alerts && (
          <div data-testid="alerts-loading">
            <LoadingSpinner />
          </div>
        )}

        {error && (
          <ErrorAlert message={`Could not load your alerts: ${error}`} />
        )}

        {!isLoading && !error && alerts && visibleAlerts.length === 0 && (
          <div
            className="py-6 text-center text-gray-300"
            data-testid="alerts-empty"
          >
            <p className="mb-2">
              You have no active price-drop alerts. Visit a part page to create
              one.
            </p>
            <Link
              to="/parts"
              className="text-blue-400 hover:text-blue-300 underline transition-colors"
            >
              Browse parts
            </Link>
          </div>
        )}

        {!error && visibleAlerts.length > 0 && (
          <ul className="space-y-3" data-testid="alerts-list">
            {visibleAlerts.map((alert) => {
              const part = partsById[alert.part_id];
              const partLoading =
                !(alert.part_id in partsById) &&
                loadingPartIds.has(alert.part_id);
              return (
                <AlertRow
                  key={alert.id}
                  alert={alert}
                  partName={part ? part.name : null}
                  partLoading={partLoading}
                  onUnsubscribed={handleUnsubscribed}
                />
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default AccountAlerts;
