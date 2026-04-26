# S11: Admin shell redesign + extraction-health UI

**Goal:** Reskin the admin shell entry point (`/admin` AdminDashboard) onto the S08 design-system primitives (interactive elements only — buttons; layout chrome stays for S12) and ship a new `/admin/extraction-health` page that consumes `GET /api/admin/extraction-health` to render compliance counts (108/108), per-tier coverage gradient (T0/T1/T2 with per-field heatmap over `UNIVERSAL_FIELD_NAMES`), and 7d per-adapter failure-rate. Wire the route into `App.tsx` + `App.coverage.test.tsx` (per MEM095) and add an entry card to AdminDashboard. Verify with a new `frontend/e2e/admin.spec.ts` Playwright spec running at mobile/tablet/desktop, mocking `/users/me` (admin user), `/admin/extraction-health` payload, and asserting full-page screenshots + keyboard focus visibility + Escape on the cookie-consent / no-modal flow.
**Demo:** Visit /admin in dev — shell on new design system. Click into Extraction Health — page shows 111/111 compliance, per-tier coverage gradient (T0/T1/T2 with field-presence heatmap), per-adapter failure rates over 7d window. Run npm run test:e2e -- admin.spec.ts — green at three breakpoints.

## Must-Haves

- `frontend/src/api/admin.ts` exports `getExtractionHealth()` with a typed `ExtractionHealthResponse` matching the backend Pydantic shape (compliance, coverage.per_tier.<tier>.{parts_with_specs,parts_total,per_field}, failure_rate_7d[], window).
- `frontend/src/pages/admin/AdminDashboard.tsx` renders its primary CTA buttons via `ui/Button` (replacing `ActionButton` for interactive surfaces); legacy `Card`, `PageHeader`, `SectionHeader` are intentionally left for S12.
- `frontend/src/pages/admin/ExtractionHealth.tsx` mounts at `/admin/extraction-health`, redirects non-admins to `/`, fetches the endpoint on mount, renders compliance summary, per-tier coverage with per-field presence as a simple ratio table/heatmap, and a sortable failure-rate table; loading + error states use existing common alerts/spinner.
- `/admin/extraction-health` registered in `App.tsx` under the admin `RouteGroupBoundary`; the new route is mirrored in `frontend/src/App.coverage.test.tsx`'s `ALL_ROUTES` with `group: 'admin'` (MEM095).
- `frontend/e2e/admin.spec.ts` is committed with mobile/tablet/desktop visual snapshots of `/admin` (post-reskin) and `/admin/extraction-health` (mock payload), `npm run test:e2e -- admin.spec.ts` exits 0, baselines committed under `frontend/e2e/admin.spec.ts-snapshots/`.
- Tab traversal on `/admin/extraction-health` lands a visible focus ring on the first interactive element (R020).
- `npm run type-check` exit 0; existing `npm run test:e2e` suite (components.spec, smoke.spec, build-list.spec, parts-catalog.spec, price-history.spec, price-alerts.spec) still green at all viewports.

## Proof Level

- This slice proves: - This slice proves: integration (frontend page consumes the S04 endpoint contract end-to-end against a mocked payload that matches the real Pydantic schema)
- Real runtime required: no (mocked API + Vite dev server inside Playwright webServer)
- Human/UAT required: no (Playwright multi-viewport snapshots + ALL_ROUTES drift guard cover the must-haves)

## Integration Closure

- Upstream surfaces consumed: `GET /api/admin/extraction-health` (S04, `backend/app/api/endpoints/admin/extraction_health.py`) — typed against `ExtractionHealthResponse`; `frontend/src/components/ui/button.tsx` (S08); existing `common/Card`, `common/PageHeader`, `common/SectionHeader`, `common/Alerts`, `common/LoadingSpinner` (left intact per MEM107).
- New wiring introduced in this slice: new lazy import + `<Route path="/admin/extraction-health">` in `App.tsx`, mirror in `App.coverage.test.tsx` ALL_ROUTES, and a new entry card on AdminDashboard linking to it.
- What remains before the milestone is truly usable end-to-end: S12 ripple (other admin sub-pages, common/* retirement) and S13 final integration verification.

## Verification

- Runtime signals: ExtractionHealth surfaces a network failure inline via `ErrorAlert` so an admin operator sees the failure mode in the UI (not just devtools).
- Inspection surfaces: the `/admin/extraction-health` page itself is the operator inspection surface (compliance/coverage/failure-rate at a glance); the underlying endpoint already logs via FastAPI access middleware.
- Failure visibility: error message renders the response status + a hint to check `crawled_pages.parse_status`; loading state distinguishes pending from empty.
- Redaction constraints: response contains adapter slugs and counts only — no PII, no tokens.

## Tasks

- [x] **T01: Add typed admin extraction-health API client** `est:20m`
  Extend `frontend/src/api/admin.ts` with `getExtractionHealth()` returning a typed `ExtractionHealthResponse` whose shape exactly mirrors the backend Pydantic model in `backend/app/api/endpoints/admin/extraction_health.py` (`ComplianceBlock`, `CoverageBlock` with `per_tier: Record<'http'|'tls'|'browser', CoverageTierBlock>`, `FailureRateRow[]`, `WindowMeta`). Also export the supporting interfaces so the page component can import them. Add a vitest unit test in `frontend/src/api/admin.test.ts` covering the new function: hits `GET /admin/extraction-health` and resolves with the typed response (use the existing axios-mock pattern already in that file).

This task is purely additive — do not touch existing exports. Do not import the `Part` type or any non-admin types. Mirror `getTableCounts()` style: thin axios call returning the typed response.

No failure modes / load profile / negative tests block here — the function is a 1-line wrapper; coverage is satisfied by the happy-path unit test plus the e2e mock in T04.
  - Files: `frontend/src/api/admin.ts`, `frontend/src/api/admin.test.ts`
  - Verify: cd frontend && npm test -- --run admin.test.ts && npm run type-check

- [x] **T02: Reskin AdminDashboard interactive primitives + add Extraction Health entry + wire route** `est:30m`
  Replace `ActionButton` with `ui/Button` (default variant, full width via `className="w-full"`) on `AdminDashboard.tsx` for the per-section CTA. Leave `Card`, `PageHeader`, `SectionHeader`, `ErrorAlert` untouched per MEM107/MEM115 (they belong to S12). Append a new entry to the `adminSections` array: `{ title: 'Extraction Health', description: 'Adapter compliance, per-tier coverage, and 7d failure rates', icon: '🩺', path: '/admin/extraction-health' }`.

Wire the new route in `frontend/src/App.tsx`: add `const ExtractionHealth = lazy(() => import('./pages/admin/ExtractionHealth.tsx'));` near the other admin lazy imports, and `<Route path="/admin/extraction-health" element={<ExtractionHealth />} />` inside the existing admin `RouteGroupBoundary` block.

Mirror in `frontend/src/App.coverage.test.tsx`: add `{ path: '/admin/extraction-health', group: 'admin' }` to `ALL_ROUTES` (or whatever shape the existing entries use — copy the closest existing admin entry verbatim and change path). MEM095 — the drift-guard test fails CI otherwise.

The `ExtractionHealth.tsx` page itself is built in T03; for this task, a minimal placeholder export so the lazy import resolves is acceptable: `export default function ExtractionHealth() { return null; }`. T03 will overwrite the body.

**Failure modes (Q5):** lazy import path mismatch → runtime error at route boundary (caught by Suspense + RouteGroupBoundary). **Negative tests (Q7):** App.coverage.test.tsx already enforces ALL_ROUTES count >= N; if you forget to add the entry, that test fails. No load-profile concerns (Q6 N/A).
  - Files: `frontend/src/pages/admin/AdminDashboard.tsx`, `frontend/src/App.tsx`, `frontend/src/App.coverage.test.tsx`, `frontend/src/pages/admin/ExtractionHealth.tsx`
  - Verify: cd frontend && npm test -- --run App.coverage.test.tsx AdminDashboard.test.tsx && npm run type-check

- [x] **T03: Build ExtractionHealth page rendering compliance + coverage + failure-rate** `est:1h30m`
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
  - Files: `frontend/src/pages/admin/ExtractionHealth.tsx`, `frontend/src/pages/admin/ExtractionHealth.test.tsx`
  - Verify: cd frontend && npm test -- --run ExtractionHealth.test.tsx && npm run type-check

- [x] **T04: Playwright admin.spec.ts — multi-viewport visual regression + keyboard focus** `est:1h30m`
  Create `frontend/e2e/admin.spec.ts` modelled on `frontend/e2e/parts-catalog.spec.ts`:

1. **Mock fixtures** — define `MOCK_ADMIN_USER` (same shape as MOCK_USER in parts-catalog.spec.ts but `is_admin: true, email_verified: true, subscription_tier: 'free'`), `MOCK_EXTRACTION_HEALTH` matching the backend `ExtractionHealthResponse` exactly: `compliance: { compliant: 108, total: 108, per_tier: { http: '83/83', tls: '15/15', browser: '10/10' } }`, `coverage.per_tier.{http,tls,browser}` with 2-3 sample fields each (e.g. `weight_grams: 0.42, material: 0.18`), `failure_rate_7d` with 3 sample rows across tiers, `window: { days: 7, since: FIXED_NOW_ISO_MINUS_7D }`. Pin `Date.now()` to `FIXED_NOW_ISO`.
2. **Setup helper** — `setupPage(page)`: `page.addInitScript` to pre-accept cookie consent (MEM098) AND pre-dismiss chrome-extension promo (MEM108 / parts-catalog.spec.ts:30 pattern); `page.route` matcher MUST be `/\/api\/(?!.*\.ts)/` (MEM082); handle paths `/users/me` (return MOCK_ADMIN_USER), `/app-settings` (existing pattern from other specs), `/admin/extraction-health` (return MOCK_EXTRACTION_HEALTH), and a fallthrough that fulfils 200 with `{}` for any unexpected admin endpoint hit (defensive). `page.on('pageerror')` re-throw.
3. **Test 1: `/admin` visual regression** — navigate, await networkidle + fonts.ready + 300ms, `expect(page).toHaveScreenshot({ fullPage: true })`. Will produce one baseline per viewport project (3 PNGs). Use `testInfo.project.name` in the snapshot identifier (auto-handled by `toHaveScreenshot`).
4. **Test 2: `/admin/extraction-health` visual regression** — same shape as Test 1 but on `/admin/extraction-health`. 3 more baseline PNGs.
5. **Test 3: keyboard focus on `/admin/extraction-health`** — `await page.keyboard.press('Tab')` once, assert focused element has a visible focus ring via `expect(page.locator(':focus')).toBeVisible()` and `expect(await page.locator(':focus').getAttribute('class')).toContain('ring')` (or use `evaluate` to read computed `outline`/`box-shadow`). Run on `desktop` project only (gate via `test.skip(testInfo.project.name !== 'desktop', 'keyboard test desktop-only')`).

**Generate baselines** — run `cd frontend && npx playwright test admin.spec.ts --update-snapshots` once, then `npm run test:e2e -- admin.spec.ts` to confirm green. Commit baselines under `frontend/e2e/admin.spec.ts-snapshots/`.

Mirror parts-catalog.spec.ts conventions: spread of MOCK_USER admin variant, animations:disabled (already in playwright.config.ts), no DB.

**Failure modes (Q5):** mock route swallowing /src/api/*.ts (MEM082) → page bundle crash; cookie banner overlay (MEM098); chrome-extension promo race (MEM108). All mitigated in setupPage. **Load profile (Q6):** N/A — fully mocked. **Negative tests (Q7):** the MOCK_EXTRACTION_HEALTH includes an empty-coverage tier and an adapter with rate=1.0 to exercise the empty/full ratio rendering paths.
  - Files: `frontend/e2e/admin.spec.ts`, `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-mobile-linux.png`, `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-tablet-linux.png`, `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-desktop-linux.png`, `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-mobile-linux.png`, `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-tablet-linux.png`, `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-desktop-linux.png`
  - Verify: cd frontend && npm run test:e2e -- admin.spec.ts

## Files Likely Touched

- frontend/src/api/admin.ts
- frontend/src/api/admin.test.ts
- frontend/src/pages/admin/AdminDashboard.tsx
- frontend/src/App.tsx
- frontend/src/App.coverage.test.tsx
- frontend/src/pages/admin/ExtractionHealth.tsx
- frontend/src/pages/admin/ExtractionHealth.test.tsx
- frontend/e2e/admin.spec.ts
- frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-mobile-linux.png
- frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-tablet-linux.png
- frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-desktop-linux.png
- frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-mobile-linux.png
- frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-tablet-linux.png
- frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-desktop-linux.png
