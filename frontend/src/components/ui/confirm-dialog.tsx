import * as React from 'react';

import { cn } from '../../lib/utils';
import { Button } from './button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './dialog';

export type ConfirmDialogVariant = 'default' | 'destructive';

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmDialogVariant;
  loading?: boolean;
  loadingLabel?: string;
  error?: string | null;
  warning?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  loading = false,
  loadingLabel,
  error,
  warning,
  children,
  className,
}: ConfirmDialogProps) {
  const handleCancel = () => {
    if (loading) return;
    onOpenChange(false);
  };

  const confirmButtonLabel =
    loading && loadingLabel ? loadingLabel : confirmLabel;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="confirm-dialog"
        className={cn('sm:max-w-md', className)}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : null}
        </DialogHeader>

        {warning ? (
          <div
            data-testid="confirm-dialog-warning"
            className="rounded-md border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-200"
          >
            {warning}
          </div>
        ) : null}

        {children ? <div className="text-sm">{children}</div> : null}

        {error ? (
          <div
            data-testid="confirm-dialog-error"
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="secondary"
            onClick={handleCancel}
            disabled={loading}
            data-testid="confirm-dialog-cancel"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={variant === 'destructive' ? 'destructive' : 'default'}
            onClick={onConfirm}
            loading={loading}
            data-testid="confirm-dialog-confirm"
          >
            {confirmButtonLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

ConfirmDialog.displayName = 'ConfirmDialog';
