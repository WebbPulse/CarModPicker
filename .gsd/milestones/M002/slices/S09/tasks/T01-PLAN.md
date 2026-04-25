---
estimated_steps: 3
estimated_files: 2
skills_used: []
---

# T01: Add components/ui/confirm-dialog.tsx and unit-test it

Create a new shadcn-style ConfirmDialog primitive on top of ui/dialog that replaces the deprecated common/DeleteConfirmationDialog pattern across the app. Used by S09 in three places (Delete Build List, Delete Phase, Delete Part) and by S10/S11/S12 thereafter. Must support destructive vs default variants, processing/loading state on the confirm button, an inline error region, and an optional warning slot for the existing 'in N build lists' notice that DeleteConfirmationDialog accepts.

Failure modes: dialog must NOT close on confirm-click while processing (parent controls open state via async handler). Negative tests: pressing Escape while processing still closes (matches Radix default; document this as accepted behavior). Load profile: rendered at most once per page, no perf concerns. No external deps reached — pure presentational.

No Threat-Surface concern (no user input persisted; dialog is presentational).

## Inputs

- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/common/DeleteConfirmationDialog.tsx``
- ``frontend/src/lib/utils.ts``

## Expected Output

- ``frontend/src/components/ui/confirm-dialog.tsx``
- ``frontend/src/components/ui/confirm-dialog.test.tsx``

## Verification

cd frontend && npm run type-check && npm test -- confirm-dialog

## Observability Impact

Adds data-testid='confirm-dialog' on DialogContent and data-testid='confirm-dialog-confirm' / 'confirm-dialog-cancel' on the action buttons so e2e specs (T04) can target them deterministically across viewports.
