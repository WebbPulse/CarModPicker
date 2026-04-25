---
estimated_steps: 5
estimated_files: 4
skills_used: []
---

# T02: Reskin AdminDashboard interactive primitives + add Extraction Health entry + wire route

Replace `ActionButton` with `ui/Button` (default variant, full width via `className="w-full"`) on `AdminDashboard.tsx` for the per-section CTA. Leave `Card`, `PageHeader`, `SectionHeader`, `ErrorAlert` untouched per MEM107/MEM115 (they belong to S12). Append a new entry to the `adminSections` array: `{ title: 'Extraction Health', description: 'Adapter compliance, per-tier coverage, and 7d failure rates', icon: '🩺', path: '/admin/extraction-health' }`.

Wire the new route in `frontend/src/App.tsx`: add `const ExtractionHealth = lazy(() => import('./pages/admin/ExtractionHealth.tsx'));` near the other admin lazy imports, and `<Route path="/admin/extraction-health" element={<ExtractionHealth />} />` inside the existing admin `RouteGroupBoundary` block.

Mirror in `frontend/src/App.coverage.test.tsx`: add `{ path: '/admin/extraction-health', group: 'admin' }` to `ALL_ROUTES` (or whatever shape the existing entries use — copy the closest existing admin entry verbatim and change path). MEM095 — the drift-guard test fails CI otherwise.

The `ExtractionHealth.tsx` page itself is built in T03; for this task, a minimal placeholder export so the lazy import resolves is acceptable: `export default function ExtractionHealth() { return null; }`. T03 will overwrite the body.

**Failure modes (Q5):** lazy import path mismatch → runtime error at route boundary (caught by Suspense + RouteGroupBoundary). **Negative tests (Q7):** App.coverage.test.tsx already enforces ALL_ROUTES count >= N; if you forget to add the entry, that test fails. No load-profile concerns (Q6 N/A).

## Inputs

- ``frontend/src/pages/admin/AdminDashboard.tsx``
- ``frontend/src/App.tsx``
- ``frontend/src/App.coverage.test.tsx``
- ``frontend/src/components/ui/button.tsx``

## Expected Output

- ``frontend/src/pages/admin/AdminDashboard.tsx``
- ``frontend/src/App.tsx``
- ``frontend/src/App.coverage.test.tsx``
- ``frontend/src/pages/admin/ExtractionHealth.tsx``

## Verification

cd frontend && npm test -- --run App.coverage.test.tsx AdminDashboard.test.tsx && npm run type-check
