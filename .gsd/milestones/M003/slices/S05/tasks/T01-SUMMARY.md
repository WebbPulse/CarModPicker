---
id: T01
parent: S05
milestone: M003
key_files:
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/components/ui/status-badge.tsx
  - frontend/src/components/ui/loading-overlay.tsx
  - frontend/src/components/ui/card-info-item.tsx
key_decisions:
  - StatusBadge variant enum locked to real consumer superset 'pending|in_progress|resolved|dismissed' (BugReportReview:199 uses in_progress, ReportReview:178 uses pending|resolved|dismissed). Task plan said 'active' but no consumer uses that label — followed reality, not the plan, per dispatcher's explicit invitation to make local factual corrections.
  - Status/Priority badge surfaces use semantic-token tints (warning/15, info/15, success/15, destructive/15, muted) rather than solid bg-* fills, matching the visual weight of the existing legacy admin badges (bg-yellow-600/etc with darker text) but in a shadcn-idiomatic semantic-token shape.
  - LoadingOverlay default backdrop is bg-background/80 backdrop-blur-sm exactly per task plan spec — replaces the legacy bg-gray-900/50 backdrop-blur-sm in three admin sites during T05.
  - Textarea uses inline className rather than a separate textarea-variants.ts file because there are no variants today; a future variants extraction is trivial if needed.
duration: 
verification_result: passed
completed_at: 2026-04-27T00:12:20.719Z
blocker_discovered: false
---

# T01: feat: Add Textarea, StatusBadge/PriorityBadge, LoadingOverlay primitives + retokenize card-info-item.tsx (semantic tokens only)

**feat: Add Textarea, StatusBadge/PriorityBadge, LoadingOverlay primitives + retokenize card-info-item.tsx (semantic tokens only)**

## What Happened

Landed the four atomic primitive additions/retokenizations that unblock the S05 polish batches (T03/T04/T05) without yet migrating any consumers.

**1. `frontend/src/components/ui/textarea.tsx` (new, 23 lines)** — Mirrors the `input.tsx` pattern: a function component forwarding all native `textarea` props to a real `<textarea>` element, with an `error?: boolean` prop that drives `aria-invalid`. Uses the same semantic-token surface as `inputVariants` (border-input / bg-background / text-foreground / placeholder:text-muted-foreground / focus-visible:ring-ring / aria-[invalid=true]:border-destructive). Min-height 80px to match common consumer expectations. No cva — single-shape primitive needs no variants today.

**2. `frontend/src/components/ui/status-badge.tsx` (new, 107 lines)** — Two named exports (`StatusBadge`, `PriorityBadge`) with cva variants. **Decision deviation from task plan**: the plan specified the StatusBadge enum as `'pending'|'active'|'resolved'|'dismissed'`, but the two real consumer factories (`pages/admin/ReportReview.tsx:178` and `pages/admin/BugReportReview.tsx:199`) use the superset `pending|in_progress|resolved|dismissed` (BugReportReview adds `in_progress`; `active` does not appear in either). I matched real consumer usage so T03/T04 swaps are drop-in. Variant→token mapping: `pending`→warning/15+text-warning, `in_progress`→info/15+text-info, `resolved`→success/15+text-success, `dismissed`→muted+muted-foreground. PriorityBadge uses `low|medium|high|critical` per BugReportReview:216, mapped to muted/warning-tinted/destructive surfaces. Both badges accept optional `children` to override the default capitalized label, preserving consumer flexibility for non-default text (e.g., "In Progress" instead of "in_progress").

**3. `frontend/src/components/ui/loading-overlay.tsx` (new, 43 lines)** — `visible: boolean` prop short-circuits render to null; when visible, renders `absolute inset-0 z-10 ... bg-background/80 backdrop-blur-sm rounded-lg` exactly per task plan spec. Replaces three admin sites (`pages/admin/ReportReview.tsx:256`, `UserManagement.tsx:340`, `BugReportReview.tsx:334`) that all use the legacy `bg-gray-900/50 backdrop-blur-sm` pattern. Includes Loader2 spinner, optional `label` prop, proper a11y (`role="status"`, `aria-live="polite"`, `aria-busy="true"`).

**4. `frontend/src/components/ui/card-info-item.tsx` (retokenized in place)** — Single 2-line edit: `text-gray-300` → `text-muted-foreground` for the label, `text-gray-300` → `text-foreground` for the value. No API change; consumers are unaffected. Picks up the visual delta uniformly across the ~4 InfoItem sites that will surface in T06's baseline cascade.

**Quality gates (Q3 Threat Surface)**: confirmed none — all four primitives are presentational. Textarea forwards onChange/value to a native textarea; consumers retain change-handling and validation. **Q4 Requirement Impact**: touches R060 (per-slice baseline refresh) for any spec screenshotting CardInfoItem; refresh deferred to T06's cascade pass.

**No consumer migration in this task** per task plan — T03/T04/T05 will swap textareas, status badges, and loading overlays. This task only lands the primitives.

## Verification

All 6 verification checks from S05/T01 plan pass:

1. `cd frontend && npm run type-check` → exit 0 (tsc -b --noEmit, no diagnostics)
2. `cd frontend && npm run lint` → exit 0 (eslint silent on success; no new errors over MEM062 baseline of 108)
3. `rg 'text-gray-' frontend/src/components/ui/card-info-item.tsx` → exit 1 / 0 hits (gate 3 satisfied)
4. `rg '\bbg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]|text-accent-' frontend/src/components/ui/{textarea,status-badge,loading-overlay,card-info-item}.tsx` → exit 1 / 0 hits (gate 4 satisfied — semantic tokens only in all 4 new/touched primitives)
5. TypeScript surfaces verified by inspection: Textarea extends TextareaHTMLAttributes + `error?: boolean`; StatusBadge `variant: 'pending'|'in_progress'|'resolved'|'dismissed'` (real consumer enum, see narrative deviation note); PriorityBadge `priority: 'low'|'medium'|'high'|'critical'`; LoadingOverlay `visible: boolean` rendering `absolute inset-0 z-10 ... bg-background/80 backdrop-blur-sm rounded-lg` (gate 5 satisfied)
6. `npm test -- --run` → exit 0, 90 test files / 594 tests passed (5.27s) — no consumers swapped, no test churn (gate 6 satisfied)

Slice-level gates (S05 inherits 12 standing grep gates from S04): not exercised in T01 since no consumer files were edited; will be re-checked in T06's final cascade.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 12000ms |
| 2 | `npm run lint (in frontend/)` | 0 | ✅ pass | 8000ms |
| 3 | `rg 'text-gray-' frontend/src/components/ui/card-info-item.tsx` | 1 | ✅ pass (0 hits) | 50ms |
| 4 | `rg '\bbg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]|text-accent-' frontend/src/components/ui/{textarea,status-badge,loading-overlay,card-info-item}.tsx` | 1 | ✅ pass (0 hits) | 60ms |
| 5 | `npm test -- --run (in frontend/)` | 0 | ✅ pass (594/594 tests, 90 files) | 5270ms |

## Deviations

Task plan listed StatusBadge variants as 'pending|active|resolved|dismissed'; actual consumer code uses 'pending|in_progress|resolved|dismissed' (BugReportReview adds in_progress, ReportReview is a subset, neither uses 'active'). Used the real consumer enum so T03/T04 swaps are drop-in. Documented in narrative key-decisions.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/ui/status-badge.tsx`
- `frontend/src/components/ui/loading-overlay.tsx`
- `frontend/src/components/ui/card-info-item.tsx`
