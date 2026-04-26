// Subscribe button + dialog for the part detail page (M002/S07/T04).
// Anonymous users get redirected to /login?next=/parts/:partId on click;
// authenticated users see a Radix dialog with a number input prefilled to
// the current best price, and the Subscribe button POSTs to
// /api/part-price-alerts. On mount we fetch the user's active alerts and
// match this partId so the trigger label flips to "Manage alert ($X.XX)".
import { useEffect, useState } from 'react';
import type { AxiosError } from 'axios';
import { useNavigate } from 'react-router-dom';
import { partPriceAlertsApi } from '../../api/part_price_alerts';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Input } from '../ui/input';
import type { PartPriceAlertRead } from '../../types/Api';

interface Props {
  partId: string;
  currentBestPriceCents: number | null;
  defaultOpen?: boolean;
}

function centsToDollarString(cents: number | null | undefined): string {
  if (cents == null) return '';
  return (cents / 100).toFixed(2);
}

function dollarStringToCents(input: string): number | null {
  const trimmed = input.trim();
  if (trimmed === '') return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return null;
  return Math.round(parsed * 100);
}

export default function PriceAlertSubscribeButton({
  partId,
  currentBestPriceCents,
  defaultOpen = false,
}: Props) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(defaultOpen);
  const [existingAlert, setExistingAlert] = useState<PartPriceAlertRead | null>(
    null
  );
  const [thresholdInput, setThresholdInput] = useState<string>(() =>
    centsToDollarString(currentBestPriceCents)
  );
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // On mount (or when the user logs in), fetch active alerts and find the one
  // for this part so the label can flip to "Manage alert ($X.XX)" and the
  // dialog input pre-fills the current threshold.
  useEffect(() => {
    if (!user) {
      setExistingAlert(null);
      return;
    }
    let cancelled = false;
    void partPriceAlertsApi
      .listMine()
      .then((res) => {
        if (cancelled) return;
        const match = (res.data ?? []).find(
          (a) => a.part_id === partId && a.active
        );
        if (match) {
          setExistingAlert(match);
          setThresholdInput(centsToDollarString(match.threshold_cents));
        } else {
          setExistingAlert(null);
        }
      })
      .catch(() => {
        // Treat any failure (incl. 401) as "no existing alert" — the button
        // still works, the user just doesn't get the prefill.
        if (!cancelled) setExistingAlert(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user, partId]);

  const handleClickTrigger = () => {
    if (!user) {
      // Anonymous → bounce to login; do not open the dialog.
      void navigate(`/login?next=/parts/${partId}`);
      return;
    }
    // Authenticated — refresh prefill from existing alert (or current price)
    // and open the dialog.
    setErrorMessage(null);
    setThresholdInput(
      existingAlert
        ? centsToDollarString(existingAlert.threshold_cents)
        : centsToDollarString(currentBestPriceCents)
    );
    setOpen(true);
  };

  const handleSubscribe = async () => {
    setErrorMessage(null);
    const cents = dollarStringToCents(thresholdInput);
    if (cents == null || cents < 0) {
      // Reject negative / non-numeric client-side so the user gets a clear
      // message without burning a server roundtrip on a 422.
      setErrorMessage('Enter a non-negative number for the threshold price.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await partPriceAlertsApi.subscribe({
        part_id: partId,
        threshold_cents: cents,
      });
      setExistingAlert(res.data);
      setOpen(false);
    } catch (err) {
      const axiosErr = err as AxiosError<{
        detail?: string | { msg?: string }[];
      }>;
      const status = axiosErr.response?.status;
      if (status === 401) {
        // Token expired between page-load and submit — punt to login.
        void navigate(`/login?next=/parts/${partId}`);
        return;
      }
      const detail = axiosErr.response?.data?.detail;
      let message = 'Could not save the alert. Please try again.';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        message = detail[0].msg;
      }
      setErrorMessage(message);
    } finally {
      setSubmitting(false);
    }
  };

  const triggerLabel = existingAlert
    ? `Manage alert ($${centsToDollarString(existingAlert.threshold_cents)})`
    : 'Notify me on price drop';

  return (
    <>
      <Button
        type="button"
        variant="outline"
        onClick={handleClickTrigger}
        data-testid="price-alert-subscribe-trigger"
      >
        {triggerLabel}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="price-alert-subscribe-dialog">
          <DialogHeader>
            <DialogTitle>Get a price-drop alert</DialogTitle>
            <DialogDescription>
              We&apos;ll email you when an observed price drops to or below
              your threshold. You can unsubscribe at any time.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label
              htmlFor="price-alert-threshold"
              className="text-sm font-medium"
            >
              Threshold price (USD)
            </label>
            <Input
              id="price-alert-threshold"
              type="number"
              min="0"
              step="0.01"
              value={thresholdInput}
              onChange={(e) => setThresholdInput(e.target.value)}
              data-testid="price-alert-threshold-input"
            />
            {errorMessage && (
              <p
                className="text-sm text-destructive"
                data-testid="price-alert-error"
                role="alert"
              >
                {errorMessage}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                void handleSubscribe();
              }}
              loading={submitting}
              data-testid="price-alert-subscribe-submit"
            >
              Subscribe
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
