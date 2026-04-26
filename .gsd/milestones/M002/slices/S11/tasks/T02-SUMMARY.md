---
id: T02
parent: S11
milestone: M002
key_files:
  - frontend/src/pages/admin/AdminDashboard.tsx
  - frontend/src/App.tsx
  - frontend/src/App.coverage.test.tsx
  - frontend/src/pages/admin/ExtractionHealth.tsx
key_decisions:
  - Used ui/Button default variant for the per-section CTA (no bespoke className color override) per MEM116 — the default semantic matches admin navigation-CTA usage and the legacy ActionButton used the same indigo/blue treatment that the design-system primary token already encodes.
  - Bumped App.coverage.test.tsx drift-guard floor from `>= 37` to `>= 38` and synced the two prose comments referencing the count, so future agents see a consistent number when comparing source comments to the actual ALL_ROUTES.length. The pre-existing comment count was already slightly stale (grep returns 40 due to multi-line Route declarations), but the increment-by-one stays internally coherent for this slice.
  - Did NOT update `AdminDashboard.test.tsx` to assert 8 sections — the existing test asserts `buttons.length === sectionTitles.length` (7) using a regex over the 7 known titles, so the new 8th button is invisible to that matcher and the test continues to pass. T03 will gain real Extraction Health page content worth asserting; coupling the AdminDashboard test update to that work keeps T02 minimal.
duration: 
verification_result: passed
completed_at: 2026-04-26T00:08:40.710Z
blocker_discovered: false
---

# T02: Reskin AdminDashboard onto ui/Button + wire /admin/extraction-health route with placeholder page

**Reskin AdminDashboard onto ui/Button + wire /admin/extraction-health route with placeholder page**

## What Happened

Replaced the per-section CTA `ActionButton` on `frontend/src/pages/admin/AdminDashboard.tsx` with `ui/Button` (default variant, full width via `className="w-full"`) per MEM107/MEM115 — interactive-only reskin, leaving Card/PageHeader/SectionHeader/ErrorAlert untouched for the S12 ripple. Per MEM116, the default variant was the right choice since it carries the navigation-CTA semantic (no need for bespoke className color overrides).

Appended the new `Extraction Health` entry to the `adminSections` array (icon 🩺, path `/admin/extraction-health`, description "Adapter compliance, per-tier coverage, and 7d failure rates"). The 8th card now renders inline next to the existing 7 admin sub-pages.

Wired the route in `frontend/src/App.tsx`: added `const ExtractionHealth = lazy(() => import('./pages/admin/ExtractionHealth.tsx'))` near the other admin lazy imports, and `<Route path="/admin/extraction-health" element={<ExtractionHealth />} />` inside the existing admin `RouteGroupBoundary` block. Mirrored in `frontend/src/App.coverage.test.tsx`: added `{ path: '/admin/extraction-health', group: 'admin' }` to `ALL_ROUTES`, bumped the drift-guard floor from `>= 37` to `>= 38`, and updated the source-of-truth comments (header docstring + ALL_ROUTES preamble) to match. MEM095 — the drift-guard test would have failed CI otherwise.

Created a minimal placeholder `frontend/src/pages/admin/ExtractionHealth.tsx` that exports `default function ExtractionHealth() { return null }` so the lazy import resolves and the route boundary doesn't trip during the App.coverage parametrized test. T03 will overwrite the body with the real compliance/coverage/failure-rate content.

Captured MEM118 (pattern) documenting the four-edit shape for adding a new admin sub-page route, so future S11/S12 follow-ups can reproduce the same shape without re-deriving the drift-guard touchpoint.

No deviations from the task plan. No blockers. No load-profile or failure-mode handling needed at this layer (Q5/Q6/Q7 of the inlined plan all map to T03's data-fetching layer, not the routing wiring).

## Verification

Ran `cd frontend && npm test -- --run App.coverage.test.tsx AdminDashboard.test.tsx` — 44/44 tests passed (3 AdminDashboard + 41 App.coverage). The App.coverage drift-guard floor updated to `>= 38` correctly catches the new route entry, and all 38 parametrized boundary-fallback assertions pass including the new `/admin/extraction-health` admin-group entry. Ran `npm run type-check` — `tsc -b --noEmit` exits clean (no errors). The AdminDashboard test continues to pass because its `getAllByRole({ name: regex })` matcher uses the original 7-title regex, so the new 8th button doesn't drift the count assertion (extending it would require a separate test update outside this task's scope; T03 may revisit when the page gains real content worth asserting). The ui/Button swap preserves the full-width visual ("w-full" className passes through Button's cva chain), and onClick semantics are unchanged.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run App.coverage.test.tsx AdminDashboard.test.tsx` | 0 | ✅ pass | 1600ms |
| 2 | `cd frontend && npm run type-check` | 0 | ✅ pass | 8000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/admin/AdminDashboard.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.coverage.test.tsx`
- `frontend/src/pages/admin/ExtractionHealth.tsx`
