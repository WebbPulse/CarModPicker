---
id: T01
parent: S09
milestone: M002
key_files:
  - frontend/src/components/ui/confirm-dialog.tsx
  - frontend/src/components/ui/confirm-dialog.test.tsx
key_decisions:
  - ConfirmDialog uses controlled open state — parent owns open/onOpenChange so async confirm handlers can keep the dialog visible during the await; the component never calls onOpenChange in response to confirm clicks
  - Reused buttonVariants via Button's `variant` prop instead of re-implementing destructive styling — keeps the design-system contract single-sourced
  - Escape-during-loading closes the dialog (Radix default) — accepted behavior per task plan; documented in test commentary
  - Added five data-testid hooks (`confirm-dialog`, `-confirm`, `-cancel`, `-warning`, `-error`) for downstream e2e and unit targeting
duration: 
verification_result: passed
completed_at: 2026-04-25T23:06:52.292Z
blocker_discovered: false
---

# T01: feat: Add ConfirmDialog primitive (ui/confirm-dialog) with destructive/default variants, loading state, and inline error/warning slots

**feat: Add ConfirmDialog primitive (ui/confirm-dialog) with destructive/default variants, loading state, and inline error/warning slots**

## What Happened

Created `frontend/src/components/ui/confirm-dialog.tsx`, a shadcn-style primitive layered on top of `ui/dialog` + `ui/button`. It accepts `open`/`onOpenChange` (controlled by parent — never auto-closes on confirm), `onConfirm`, `title`, optional `description`, configurable `confirmLabel`/`cancelLabel`, `variant` (`default` → primary button, `destructive` → destructive button), `loading` + `loadingLabel`, an `error` string region (role="alert"), an optional `warning` slot for the existing "in N build lists" notice, and a freeform `children` body. All three e2e-targeted hooks were added: `data-testid="confirm-dialog"` on DialogContent, `confirm-dialog-confirm` and `confirm-dialog-cancel` on the action buttons, plus `confirm-dialog-warning` and `confirm-dialog-error` for the conditional regions.

Wrote `confirm-dialog.test.tsx` with 14 cases covering: closed-state (no portal content), default labels rendering, onConfirm wiring, onOpenChange(false) on cancel, loading disables both buttons + sets aria-busy + swaps to loadingLabel, the critical "no auto-close on confirm during loading" guarantee (parent owns open state for async flows), cancel-while-loading is a no-op, error region presence/absence, warning slot presence/absence, destructive vs default variant produces the expected button class (bg-destructive vs bg-primary), and custom children rendering.

Followed established conventions: cn() utility for className merge, React.forwardRef pattern is unnecessary here (composite component, not a primitive ref-forwarder), and the variant strings map cleanly to existing buttonVariants. Did not need to re-export a cva instance because all styling reuses Button's variants.

Documented Radix-default behavior: pressing Escape while loading still closes the dialog (Radix manages this internally and we did not override). The task plan flagged this as accepted behavior.

## Verification

Ran the slice-specified verification: `cd frontend && npm run type-check` (exit 0) and `npm test -- confirm-dialog --run` (14/14 passing). The unit tests provide direct evidence of every must-have: variant switching, loading-state UI, error/warning slots, and the no-auto-close-on-confirm contract that S09's ViewBuildlist delete handler depends on.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | pass | 8000ms |
| 2 | `cd frontend && npm test -- confirm-dialog --run` | 0 | pass | 817ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/ui/confirm-dialog.tsx`
- `frontend/src/components/ui/confirm-dialog.test.tsx`
