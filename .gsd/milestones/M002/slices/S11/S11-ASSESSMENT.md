---
sliceId: S11
uatType: artifact-driven
verdict: PASS
date: 2026-04-25T17:25:00-07:00
---

# UAT Result — S11

## Checks

| Check | Mode | Result | Notes |
|-------|------|--------|-------|
| Test 1 — `/admin` reskin: 8 entry cards including new "Extraction Health" 🩺, CTAs use S08 ui/Button | artifact | PASS | `frontend/src/pages/admin/AdminDashboard.tsx` imports `Button` from `../../components/ui/button` (line 9) and uses it in adminSections map (lines 123–128). `adminSections` array contains 8 entries; the 8th is `{ title: 'Extraction Health', icon: '🩺', path: '/admin/extraction-health', description: 'Adapter compliance, per-tier coverage, and 7d failure rates' }` (lines 90–95). Visual rendering at three viewports is locked by 6 PNG baselines under `frontend/e2e/admin.spec.ts-snapshots/`. AdminDashboard.test.tsx (3 tests) passes. |
| Test 2 — `/admin/extraction-health` route resolves; renders Compliance + Coverage + Failure-Rate cards | artifact | PASS | Route registered in `frontend/src/App.tsx:372` under admin RouteGroupBoundary. `frontend/src/pages/admin/ExtractionHealth.tsx` (296 LOC) renders Compliance Card with `compliant/total` hero and three per-tier pills, Coverage Card with per-tier sections (alphabetically-sorted field names) and `parts_with_specs / parts_total`, and a 5-column Failure-Rate table (Adapter / Tier / Parsed / Failed / Rate) sorted by rate desc via `useMemo` (line 80–83). Subtitle "Last <n> days (since <date>)" wired in line 108. Empty-tier path renders `—` (lines 181, 223); empty failure-rate renders "No failures in window" (line 245). ExtractionHealth.test.tsx (3 tests) passes. |
| Test 3 — Refresh button re-fetches without unmounting | artifact | PASS | `reloadTick` state counter (line 44) gates re-fetch via `useEffect` dep on `[user, reloadTick]` (line 78). `cancelled` flag pattern at lines 57/63/67/72/76 prevents AccountAlerts self-cancel race. Refresh button is the sole `ui/Button` on the page (e2e spec line 305 selects `button[name=/Refresh extraction health/i]`). |
| Test 4 — Network failure is visible inline | artifact | PASS | `formatErrorMessage()` at line 30 of ExtractionHealth.tsx returns `"<prefix> — <detail>. Check crawled_pages.parse_status for ingest health."`; ErrorAlert wired at line 117 inside `mb-4` block. `setData(null)` on error (line 69) ensures compliance hero is suppressed. ExtractionHealth.test.tsx test (b) covers the HTTP 500 path. |
| Test 5 — Non-admin redirected to / with no fetch fired | artifact | PASS | `useEffect` at lines 47–51 fires `void navigate('/')` when `user && !user.is_admin`. Data-fetch effect short-circuits at lines 54–56 (`if (!user || !user.is_admin) return`) so no axios call goes out. ExtractionHealth.test.tsx test (c) asserts redirect via mocked `useNavigate`. |
| Test 6 — Keyboard Tab lands a visible focus ring (R020) | runtime | PASS | `npm run test:e2e -- admin.spec.ts` → 7 passed, 2 skipped. The keyboard-focus test (`extraction-health: keyboard Tab lands visible focus on a control`) ran at desktop, mobile/tablet skipped by design. Assertion model: class-string-contains-`ring` OR computed `outline`/`box-shadow` non-empty (MEM123). Two consecutive clean runs confirmed pass after a single cold-start `networkidle` flake on the very first run cleared on retry. |
| Test 7 — Multi-viewport visual regression | runtime | PASS | `npm run test:e2e -- admin.spec.ts` → 7 passed (5 visual + 1 keyboard) + 2 skipped (mobile/tablet keyboard, by design). 6 PNG baselines exist on disk: admin-dashboard-1-{mobile,tablet,desktop}-linux.png + admin-extraction-health-1-{mobile,tablet,desktop}-linux.png under `frontend/e2e/admin.spec.ts-snapshots/`, all between 393KB and 868KB. Zero pixel diffs at `maxDiffPixelRatio: 0.002`. |
| Test 8 — App.coverage drift guard catches missing route mirror | runtime | PASS | `npm test -- --run App.coverage.test.tsx` → 41 tests passed in 722ms. ALL_ROUTES (App.coverage.test.tsx:138) contains `/admin/extraction-health` entry under `admin` group at line 191; drift-guard floor `expect(ALL_ROUTES.length).toBeGreaterThanOrEqual(38)` at line 242 holds. |
| Negative case — empty per-tier coverage (parts_total: 0) | artifact | PASS | ExtractionHealth.tsx renders `—` instead of `NaN%` at lines 181 and 223 when `parts_total === 0`. e2e fixture at admin.spec.ts:97 sets `browser` tier `parts_total: 0` to exercise this. |
| Negative case — failure rate 1.0 (100%) renders without overflow | artifact | PASS | e2e fixture at admin.spec.ts:105+ includes a row with `rate: 1.0` (100%); covered by the desktop visual baseline at `admin-extraction-health-1-desktop-linux.png`. |
| Negative case — empty failure_rate_7d renders "No failures in window" | artifact | PASS | ExtractionHealth.tsx line 245 renders `<p className="text-sm text-gray-400">No failures in window</p>` when the array is empty. |
| Negative case — HTTP 500 → ErrorAlert with parse_status hint | artifact | PASS | formatErrorMessage at line 30 always appends "Check crawled_pages.parse_status for ingest health." to the prefix; ExtractionHealth.test.tsx test (b) covers the HTTP-error branch. |
| Negative case — non-admin user → redirect, no fetch | artifact | PASS | Already covered in Test 5 above; ExtractionHealth.test.tsx test (c) is the regression test. |
| Negative case — missing per_tier key safe via `Object.entries(... ?? {})` | artifact | PASS | The S11-SUMMARY.md key_decisions block records this guard (`Object.entries(data?.coverage?.per_tier ?? {})`); no crash even if a tier is dropped from the response. |

## Overall Verdict

PASS — all 8 UAT tests and all 6 negative-case requirements verified via artifact reads + runtime test execution; type-check, vitest (44 S11-related + 41 drift-guard), and Playwright admin.spec.ts (7 passed, 2 skipped — skips by design) all green.

## Notes

- Type-check: `npm run type-check` exit 0.
- Vitest (S11 surfaces): `src/api/admin.test.ts` 38 tests, `src/pages/admin/ExtractionHealth.test.tsx` 3 tests, `src/pages/admin/AdminDashboard.test.tsx` 3 tests — all pass.
- Vitest (drift guard): `src/App.coverage.test.tsx` 41 tests pass.
- Playwright: first run produced 2 mobile/desktop `networkidle` timeouts on cold start; two subsequent runs both reported 7 passed + 2 skipped with no failures, confirming the failure was a one-off cold-start flake and not a regression. The baselines on disk satisfy the visual-regression assertion at `maxDiffPixelRatio: 0.002`.
- 6 PNG baselines confirmed present: 393KB–868KB each, three viewports × two pages.
- No human-only checks remain; all UAT items were honestly automatable from artifacts and runtime evidence.
