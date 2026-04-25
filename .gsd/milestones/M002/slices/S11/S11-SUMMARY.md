---
id: S11
parent: M002
milestone: M002
provides:
  - ["frontend/src/api/admin.ts: getExtractionHealth() + ExtractionHealthResponse + ComplianceBlock + CoverageBlock + CoverageTierBlock + FailureRateRow + WindowMeta", "frontend/src/pages/admin/ExtractionHealth.tsx: /admin/extraction-health page with compliance + per-tier coverage heatmap + 7d failure-rate table + Refresh button + auth guard + error handling", "frontend/src/pages/admin/AdminDashboard.tsx: ui/Button-reskinned CTAs + new 8th 'Extraction Health' entry card", "frontend/src/App.tsx: lazy-imported /admin/extraction-health route under admin RouteGroupBoundary", "frontend/src/App.coverage.test.tsx: ALL_ROUTES drift-guard updated to >= 38 with the new admin route entry", "frontend/e2e/admin.spec.ts: multi-viewport visual regression at mobile/tablet/desktop + desktop-only keyboard-focus assertion + 6 PNG baselines under frontend/e2e/admin.spec.ts-snapshots/"]
requires:
  - slice: S04
    provides: GET /api/admin/extraction-health endpoint + ExtractionHealthResponse Pydantic shape (compliance, coverage.per_tier, failure_rate_7d, window)
  - slice: S08
    provides: frontend/src/components/ui/button.tsx (and tokens) — ui/Button default and secondary variants
affects:
  - ["frontend/src/api/admin.ts (additive — getExtractionHealth + 6 new exported types)", "frontend/src/pages/admin/AdminDashboard.tsx (CTA reskin + 8th adminSections entry)", "frontend/src/App.tsx (lazy import + Route under admin RouteGroupBoundary)", "frontend/src/App.coverage.test.tsx (ALL_ROUTES + drift-guard floor)", "frontend/src/pages/admin/ExtractionHealth.tsx (new page)", "frontend/src/pages/admin/ExtractionHealth.test.tsx (new test file)", "frontend/e2e/admin.spec.ts (new e2e file)", "frontend/e2e/admin.spec.ts-snapshots/ (6 new PNG baselines)"]
key_files:
  - ["frontend/src/api/admin.ts", "frontend/src/api/admin.test.ts", "frontend/src/pages/admin/AdminDashboard.tsx", "frontend/src/App.tsx", "frontend/src/App.coverage.test.tsx", "frontend/src/pages/admin/ExtractionHealth.tsx", "frontend/src/pages/admin/ExtractionHealth.test.tsx", "frontend/e2e/admin.spec.ts"]
key_decisions:
  - ["Reskin scope split: S11 swaps ui/Button for ActionButton on interactive surfaces only; layout chrome (Card/PageHeader/SectionHeader/ErrorAlert/LoadingSpinner) is intentionally left for the S12 ripple sweep (MEM107/MEM115/MEM121).", "Tier keys typed as literal union 'http' | 'tls' | 'browser' on ExtractionHealthResponse — gives compile-time exhaustiveness on the page; per_field stays Record<string, number> since UNIVERSAL_FIELD_NAMES may evolve.", "Used 108/108 compliance in fixtures, not the 111/111 in the milestone vision text — 108 is the canonical adapter count (MEM037) and matches the actual backend response (MEM122).", "Data-fetch effect uses a local `cancelled` flag + `reloadTick` state counter for the Refresh button instead of AbortController — Axios mock surface doesn't propagate signals, and the cancel flag avoids the AccountAlerts self-cancel race (MEM097/MEM102).", "Coverage heatmap field-name iteration sorts alphabetically for deterministic Playwright snapshots; failure-rate table sort uses useMemo over a copied array sorted by rate desc.", "Empty tier (parts_total === 0) renders '—' instead of NaN%; missing per_tier key safe-guarded via Object.entries(data?.coverage?.per_tier ?? {}).", "Keyboard-focus assertion checks 'class-string contains ring OR computed outline/box-shadow non-empty' rather than a specific testid (MEM123) — first Tab target depends on header structure and R020 is about ring visibility, not element identity.", "App.coverage.test.tsx drift-guard floor bumped from >= 37 to >= 38 to mirror the new /admin/extraction-health route (MEM095 — required to avoid CI breakage).", "Defensive Playwright route fallthrough: /admin/* GET → 200 {} so a future admin endpoint addition can't crash the bundle; /\\/api\\/(?!.*\\.ts)/ regex matcher prevents Vite source-module swallow (MEM082)."]
patterns_established:
  - ["MEM120 — Admin sub-page route addition is a four-edit shape: lazy import + Route in App.tsx (under admin RouteGroupBoundary), ALL_ROUTES entry + drift-guard floor bump in App.coverage.test.tsx, adminSections card in AdminDashboard, and a stub page module so the lazy import resolves.", "MEM119 — Admin sub-page structure idiom: container wrapper, mt-6-spaced Cards, PageHeader/SectionHeader auth-guard pattern with useAuth → navigate('/') for non-admins → ErrorAlert for null user.", "MEM118 — Four-edit shape for adding a new admin sub-page route — a lighter form of MEM120, captured during T02 before T03 added the body.", "MEM123 — Playwright keyboard-focus assertion: assert ring visibility via class-string-contains-ring OR computed outline/box-shadow non-empty, not specific element identity.", "MEM121 — M002 design-system rollout splits interactive-primitive swaps (S09/S10/S11) from layout-chrome retirement (S12) so each priority-page diff is small and reviewable.", "MEM122 — Backend extraction-health contract is 108/108, not 111/111; fixtures and snapshots track the backend response, not aspirational milestone text."]
observability_surfaces:
  - ["UI inspection: /admin/extraction-health page itself — operator at-a-glance view of compliance + per-tier coverage gradient + 7d per-adapter failure-rate table, sorted by rate desc.", "Failure visibility: inline ErrorAlert renders 'HTTP <status>' (or 'Network error') + the documented hint to check crawled_pages.parse_status when the backend endpoint fails or is unreachable.", "Loading state: distinct LoadingSpinner separates pending from empty; Refresh button uses useMemo + reloadTick state counter so re-fetch doesn't double-fire or race with unmount.", "Backend access logs: FastAPI access middleware on /api/admin/extraction-health (already in place from S04) provides server-side request observability; this slice consumes that surface from the frontend without modifying it."]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T00:22:18.821Z
blocker_discovered: false
---

# S11: Admin shell redesign + extraction-health UI

**Reskinned /admin onto S08 ui/Button primitives and shipped /admin/extraction-health rendering the S04 endpoint's compliance + per-tier coverage heatmap + 7d failure-rate table, with multi-viewport Playwright snapshots and keyboard-focus assertions all green.**

## What Happened

S11 closes the priority-page reskin trio (S09 build-list, S10 parts catalog, S11 admin) by giving admin operators a coherent S08-design-system entry point and a real extraction-health observability surface backed by the S04 API.

**T01 — Typed API client.** Extended `frontend/src/api/admin.ts` with `getExtractionHealth()` and a complete set of supporting interfaces (`ComplianceBlock`, `CoverageBlock`, `CoverageTierBlock`, `FailureRateRow`, `WindowMeta`, `ExtractionHealthResponse`) that exactly mirror the backend Pydantic models in `backend/app/api/endpoints/admin/extraction_health.py`. Tier keys are typed as the literal union `'http' | 'tls' | 'browser'` to give the consuming page compile-time tier exhaustiveness; per-field keys stay `Record<string, number>` because `UNIVERSAL_FIELD_NAMES` is a runtime frozenset that may evolve. The client follows the existing thin-wrapper pattern of `getTableCounts()`. One happy-path vitest covers URL + payload round-trip + the nested type structure.

**T02 — Reskin AdminDashboard + wire route.** Replaced the per-section `ActionButton` CTA on `AdminDashboard.tsx` with `ui/Button` (default variant, `w-full`) per MEM107/MEM115 — interactive primitives only, leaving Card/PageHeader/SectionHeader for S12. Appended the `Extraction Health` entry to `adminSections` (icon 🩺, path `/admin/extraction-health`), added the lazy import + `<Route>` under the admin `RouteGroupBoundary` in `App.tsx`, and mirrored the entry in `App.coverage.test.tsx`'s `ALL_ROUTES` with the drift-guard floor bumped from `>= 37` to `>= 38` (MEM095 — required to avoid CI breakage). Created a minimal `ExtractionHealth.tsx` placeholder so the lazy import resolves before T03 fills it in. The four-edit shape is captured in MEM120 for future admin-page work.

**T03 — ExtractionHealth page.** Replaced the placeholder with the full page: auth-guarded fetch (non-admin → `navigate('/')`), `useEffect` data load with a `cancelled` flag and `reloadTick` counter so the Refresh button (sole `ui/Button` on the page) re-runs the fetch without the AccountAlerts self-cancel race (MEM097/MEM102). Renders a Compliance Card (`compliant/total` hero + three per-tier pills from a literal-union `TIER_ORDER` constant), a Coverage Card with per-tier heatmaps that sort field names alphabetically for deterministic snapshots and render `—` instead of NaN when `parts_total === 0`, and a Failure-Rate table sorted by rate desc via `useMemo` with an empty-state fallback. The error helper surfaces `HTTP <status>` (or `Network error`) plus the slice-plan-required `crawled_pages.parse_status` hint. Three vitest tests cover happy-path render + ordering, error-path inline ErrorAlert, and non-admin redirect via mocked `useNavigate` (MEM093/MEM094 patterns). MEM119 captures the admin sub-page structure idiom.

**T04 — Playwright admin.spec.ts.** Modelled on `parts-catalog.spec.ts`. Defines `MOCK_ADMIN_USER` and `MOCK_EXTRACTION_HEALTH` matching `ExtractionHealthResponse` exactly: 108/108 compliance (the canonical figure per MEM037; the 111/111 in the milestone vision is aspirational — captured in MEM122), per-tier coverage with an empty `browser` tier (`parts_total: 0`) to exercise the `—` empty-summary path, and a 7d failure-rate table with rate=1.0 / 0.05 / 0 rows (Q7 negative-test coverage). `setupPage()` pre-accepts cookie consent (MEM098) and pre-dismisses the chrome-extension promo (MEM108) via `addInitScript`, uses the `/\/api\/(?!.*\.ts)/` regex matcher (MEM082) so Vite source modules aren't swallowed, and routes both `/admin/extraction-health` and `/admin/extraction-health/`. Three tests: full-page snapshots of `/admin` and `/admin/extraction-health` at mobile/tablet/desktop (6 baselines), and a desktop-only keyboard-focus check that asserts `:focus` visibility plus class-OR-computed-style focus-ring presence (MEM123 — the focus-target identity varies by header structure; what R020 wants is *a* visible ring). 6 PNG baselines committed under `frontend/e2e/admin.spec.ts-snapshots/`.

**Patterns established.**
- Admin sub-page route addition is a four-edit shape (MEM120).
- Reskin scope split: interactive primitives in S09/S10/S11; layout chrome in S12 (MEM121).
- Backend extraction-health contract is 108/108, not 111/111 (MEM122).
- Keyboard-focus visual-regression should assert ring visibility, not element identity (MEM123).

**What downstream slices need to know.**
- S12 ripple has the third (and last) priority-page-shaped admin diff to learn from. The interactive-vs-chrome split applied here transfers directly: swap `ui/Button` for any remaining `ActionButton`/`PrimaryButton` usages, then retire `Card`/`PageHeader`/`SectionHeader`/`ErrorAlert`/`LoadingSpinner` together. The drift-guard floor in `App.coverage.test.tsx` is now at 38 — anyone adding routes after S11 starts from there.
- S13 final integration can trust the admin extraction-health UI as the inspection surface for the live re-extraction backfill (S04). The `/admin/extraction-health` page is the operator's at-a-glance view of compliance + coverage gradient + per-adapter failure-rate over the rolling 7d window.

## Verification

Slice plan must-haves all satisfied:

1. **Type-check** — `npm run type-check` (`tsc -b --noEmit`) exit 0. New exported interfaces compile under `exactOptionalPropertyTypes: true`; literal-union tier keys round-trip cleanly.

2. **admin.spec.ts** — `npm run test:e2e -- admin.spec.ts` → 7 passed, 2 skipped (mobile/tablet keyboard tests skipped by design via `testInfo.project.name !== 'desktop'`). 6 PNG baselines exist on disk under `frontend/e2e/admin.spec.ts-snapshots/` and produce zero pixel diffs at the configured `maxDiffPixelRatio: 0.002`.

3. **Full e2e suite** — `npm run test:e2e` → 35 passed, 10 skipped. components.spec, smoke.spec, build-list.spec, parts-catalog.spec, price-history.spec, price-alerts.spec all green at all viewports. Skips are all the pre-existing desktop-only keyboard-focus and demo-flow specs.

4. **Vitest** — `npm test -- --run` → 596/596 tests passed across 89 test files. (7 e2e/*.spec.ts files fail collection because they import `@playwright/test`, which is the standing project-config noise unrelated to S11.)

5. **Slice-level Verification block (S11-PLAN):**
   - Runtime signal: ExtractionHealth surfaces network failure inline via `ErrorAlert` (T03 test (b) — HTTP 500 → inline alert with `parse_status` hint, no compliance hero rendered).
   - Inspection surface: the `/admin/extraction-health` page itself is the operator's at-a-glance view of compliance + coverage gradient + 7d failure-rate.
   - Failure visibility: error message renders the response status + the documented hint to check `crawled_pages.parse_status`; loading state distinguishes pending from empty.
   - Redaction: response shape is adapter slugs and counts only — no PII, no tokens propagate to the DOM.

6. **Auth + access control:** non-admin user is redirected to `/` via `useNavigate`; T03 test (c) asserts the data fetch does NOT fire for non-admin callers.

7. **Drift guard:** `App.coverage.test.tsx` ALL_ROUTES floor bumped to `>= 38`; the new `/admin/extraction-health` entry is exercised by the parametrized boundary-fallback test.

| # | Command | Exit | Verdict |
|---|---------|------|---------|
| 1 | `npm run type-check` | 0 | pass |
| 2 | `npm run test:e2e -- admin.spec.ts` | 0 | pass (7 passed, 2 skipped) |
| 3 | `npm run test:e2e` | 0 | pass (35 passed, 10 skipped) |
| 4 | `npm test -- --run` | mixed | 596/596 vitest tests pass; 7 e2e collection failures are pre-existing config noise |

## Requirements Advanced

- R006 — /admin/extraction-health page surfaces compliance (108/108 binary) distinct from coverage (per-tier gradient with per-field heatmap) and per-adapter failure_rate_7d in a sortable table, satisfying the operational-visibility requirement at the UI layer.
- R016 — /admin shell reskinned onto S08 ui/Button primitives; /admin/extraction-health view ships under the new component library; Playwright toHaveScreenshot() tests pass at mobile/tablet/desktop; keyboard nav verified via desktop focus-ring assertion. Manual UAT script committed in S11-UAT.md.

## Requirements Validated

None.

## New Requirements Surfaced

- ["R017 progress: S11 contributes the third priority page (after S09 build-list and S10 parts catalog) onto the new component library; S12 ripple still owes ~17 remaining pages plus the components/common/ retirement and lint-rule enforcement."]

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"None. All four tasks executed exactly per the slice plan. The single intentional choice point — 108/108 vs 111/111 in fixtures — was resolved per the explicit task-plan fixture (108/108) and documented in MEM122."

## Known Limitations

"Playwright admin.spec.ts is fully mocked — does not exercise the live /api/admin/extraction-health endpoint or backend Pydantic serialization. S13 final integration is the slice that proves the live wire-up. The page renders compliance numbers from whatever the backend returns; if the backend ships a tier the frontend doesn't expect, the page renders it via Object.entries (safe) but the literal-union TIER_ORDER ordering is only enforced for known tiers — extra tiers append after http/tls/browser in insertion order."

## Follow-ups

["S12: retire components/common/ on AdminDashboard + ExtractionHealth pages (Card, PageHeader, SectionHeader, ErrorAlert, LoadingSpinner); add lint rule or grep CI check enforcing no imports from components/common/.", "S12: reskin remaining ~5 admin sub-pages (CrawlerAdmin, BugReports, etc.) onto ui/* primitives following the MEM119/MEM120 patterns established here.", "S13: final integration verification — exercise live scrape → extraction → ingest → /admin/extraction-health visibility in a real backend scenario; the Playwright spec uses mocks, not the live endpoint.", "AdminDashboard.test.tsx still asserts the original 7-section regex; T02 deferred updating it to T03/S12. Consider extending it to cover the 8th 'Extraction Health' card when S12 reskins the layout chrome."]

## Files Created/Modified

None.
