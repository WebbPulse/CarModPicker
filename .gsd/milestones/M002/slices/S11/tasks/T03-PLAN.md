---
estimated_steps: 10
estimated_files: 2
skills_used: []
---

# T03: Build ExtractionHealth page rendering compliance + coverage + failure-rate

Replace the placeholder `frontend/src/pages/admin/ExtractionHealth.tsx` with a full implementation:

1. **Auth guard** — same shape as `AdminDashboard.tsx`: `useAuth()`; if `user && !user.is_admin` navigate to `/`; render `ErrorAlert` if no user or non-admin (mirrors AdminDashboard idioms).
2. **Data fetch** — `useEffect` on mount calling `adminApi.getExtractionHealth()`; track `data | null`, `error | null`, `loading: boolean`. Use existing `LoadingSpinner` + `ErrorAlert` from `components/common/`.
3. **Compliance section** — render `data.compliance.compliant + ' / ' + data.compliance.total` as a hero figure plus three per-tier pills (`http`, `tls`, `browser`) showing the `<n>/<n>` strings from `data.compliance.per_tier`. Use `ui/Button` ONLY for any interactive controls (e.g., a refresh button); inert text/numbers stay in plain divs/spans with Tailwind classes consistent with the existing admin pages.
4. **Coverage heatmap** — for each tier in `data.coverage.per_tier`, render a section with `parts_with_specs / parts_total` and a simple table mapping each entry of `per_field` (field name → ratio rendered as `(ratio * 100).toFixed(1) + '%'`). Field name iteration order: sort field names alphabetically for deterministic snapshots.
5. **Failure-rate table** — render `data.failure_rate_7d` as a table with columns: Adapter, Tier, Parsed, Failed, Rate (as percentage). Sort by rate desc by default. Show window subtitle: `'Last ' + data.window.days + ' days (since ' + data.window.since + ')'`.
6. **Empty/zero states** — if `failure_rate_7d.length === 0` show 'No failures in window'; if a tier has 0 parts_total show '—' rather than NaN.
7. **Page chrome** — wrap in `<div className="container mx-auto px-4 py-8">` + reuse existing `PageHeader` (title 'Extraction Health', subtitle from window) + `Card` + `SectionHeader` (per MEM107: layout chrome stays).

Add `frontend/src/pages/admin/ExtractionHealth.test.tsx` covering: (a) renders compliance numbers from a mocked `getExtractionHealth` response; (b) shows error state when API rejects; (c) redirects non-admin user (asserts `useNavigate` called with `/`). Use the existing `vi.mock('../../hooks/useAuth', () => ({ useAuth: () => mockUseAuth() }))` pattern (MEM094) — do NOT rely on `testScenarios.adminAuthenticated` (MEM093 — type-stale).

**Failure modes (Q5):** API 401/500 → ErrorAlert; missing `data.coverage.per_tier.tier` key → safe-guard via `Object.entries(data?.coverage?.per_tier ?? {})`. **Negative tests (Q7):** test (b) covers the error path; type-checker covers shape mismatches against the `ExtractionHealthResponse` interface from T01. **Load profile (Q6):** single API call on mount; no polling; no concurrent requests; well within budget.

## Inputs

- ``frontend/src/pages/admin/ExtractionHealth.tsx``
- ``frontend/src/pages/admin/AdminDashboard.tsx``
- ``frontend/src/api/admin.ts``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/common/Alerts.tsx``
- ``frontend/src/components/common/LoadingSpinner.tsx``
- ``frontend/src/components/common/Card.tsx``
- ``frontend/src/components/layout/PageHeader.tsx``
- ``frontend/src/components/layout/SectionHeader.tsx``
- ``frontend/src/hooks/useAuth.tsx``
- ``frontend/src/test/utils/test-utils.tsx``
- ``frontend/src/test/mocks/api.ts``

## Expected Output

- ``frontend/src/pages/admin/ExtractionHealth.tsx``
- ``frontend/src/pages/admin/ExtractionHealth.test.tsx``

## Verification

cd frontend && npm test -- --run ExtractionHealth.test.tsx && npm run type-check
