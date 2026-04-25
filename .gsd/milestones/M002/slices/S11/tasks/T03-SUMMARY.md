---
id: T03
parent: S11
milestone: M002
key_files:
  - frontend/src/pages/admin/ExtractionHealth.tsx
  - frontend/src/pages/admin/ExtractionHealth.test.tsx
key_decisions:
  - Used a literal-union `TIER_ORDER = ['http','tls','browser']` constant + `TierKey` type alias for the compliance pills loop so per-tier rendering is compile-time exhaustive and the iteration order is deterministic — matches T01's `Record<'http'|'tls'|'browser', string>` typing without re-declaring the union inline.
  - Implemented the data-fetch effect with a local `cancelled` flag rather than AbortController — the existing apiClient/Axios mock surface does not propagate signals, and the cancel flag both lets unmount race-protection work and lets the effect re-run via a `reloadTick` state counter (Refresh button increments it). Avoids the AccountAlerts self-cancel race (MEM097/MEM102) by NOT listing any state we set inside the effect in the deps array.
  - Failure-rate table sorting uses `useMemo` over `[...data.failure_rate_7d].sort((a,b) => b.rate - a.rate)` so the sort is computed once per data update, not on every render. Test (a) asserts the sort by reading `tbody tr` document order rather than scraping rate text, which keeps the assertion robust against later cosmetic changes.
  - Wrapped the Refresh button at the top of the Compliance Card (variant='secondary' per MEM116, no bespoke color overrides) — the only ui/Button usage on the page. All other interactive-vs-inert decisions defer to the slice plan's MEM107/MEM115 scope (interactive primitives only; layout chrome stays for S12).
duration: 
verification_result: passed
completed_at: 2026-04-26T00:12:30.448Z
blocker_discovered: false
---

# T03: Build ExtractionHealth admin page rendering compliance, per-tier coverage heatmap, and 7d failure-rate table

**Build ExtractionHealth admin page rendering compliance, per-tier coverage heatmap, and 7d failure-rate table**

## What Happened

Replaced the T02 placeholder `frontend/src/pages/admin/ExtractionHealth.tsx` with the full admin page. The page mirrors `AdminDashboard.tsx`'s auth-guard idioms (null user → "please log in" ErrorAlert; non-admin → permission-denied ErrorAlert + `useEffect`-driven `navigate('/')`), then on mount calls `adminApi.getExtractionHealth()` (T01) with a `cancelled` flag to guard against unmount races. The data effect tracks `data | null`, `error | null`, `loading: boolean`, and a `reloadTick` counter so the Refresh button can re-run the fetch.

Rendering follows the task plan layout exactly: a Compliance Card with the `compliant / total` hero figure plus three per-tier pills (`http`/`tls`/`browser` rendered from the literal-union TIER_ORDER constant for compile-time exhaustiveness, matching the `Record<'http'|'tls'|'browser', string>` shape exported by T01); a Coverage Card iterating `Object.entries(data?.coverage?.per_tier ?? {})` per the Q5 safe-guard, with each tier showing `parts_with_specs / parts_total` and a sortable-by-field table (alphabetical for deterministic snapshots) where presence is `(ratio*100).toFixed(1) + '%'` — except when `parts_total === 0` we render '—' to avoid NaN; and a Failure-Rate Card with a 5-column table (Adapter / Tier / Parsed / Failed / Rate) sorted by rate desc via `useMemo`, falling back to "No failures in window" when the array is empty.

Layout chrome is intentionally untouched per MEM107/MEM115: `PageHeader`, `Card`, `SectionHeader`, `ErrorAlert`, `LoadingSpinner` from `components/common` + `components/layout` carry over for the S12 ripple sweep. The only ui/Button usage is the Refresh button (variant='secondary' per MEM116, no bespoke className color override). Window subtitle comes from `data.window.{days, since}` and falls back to a static description before the first response arrives. Errors are formatted via a small `formatErrorMessage` helper that surfaces `HTTP <status>` (or `Network error` if absent) plus the message and the slice-plan hint to check `crawled_pages.parse_status`, satisfying the slice's failure-visibility verification.

Test file `ExtractionHealth.test.tsx` uses the MEM094 pattern: declares `vi.mock('../../hooks/useAuth')` per-file (the hoisted-per-file rule means the test-utils mirror does not auto-apply), constructs the non-admin scenario from canonical `mockUser` per MEM093, and routes `apiClient.get` through the global setup.ts mock (D-18). Three tests cover: (a) admin happy path — renders 108/108, all three per-tier pills, the windowed subtitle, the documented endpoint URL, and verifies failure-rate ordering by rate desc (adapter-b 0.09 before adapter-a 0.02); (b) error path — when `apiClient.get` rejects with `{response: {status: 500}, message: '...'}`, the inline ErrorAlert surfaces with the documented HTTP-status + parse_status hint, and the compliance hero is absent; (c) non-admin redirect — `useNavigate` mock asserts `navigate('/')` was called and the data fetch did NOT fire for the non-admin caller. `useNavigate` is mocked via `importOriginal` to keep BrowserRouter intact (PriceAlertSubscribeButton.test.tsx pattern).

Captured MEM119 documenting the admin sub-page structure idiom (container wrapper, mt-6-spaced Cards, PageHeader/SectionHeader/auth-guard pattern) so future S12 ripple work and any new admin sub-pages can mirror it without re-deriving.

## Verification

Ran the task plan's two verification commands:

1. `cd frontend && npm test -- --run ExtractionHealth.test.tsx` → 1 file, 3 tests, all passed (67ms test runtime).
2. `cd frontend && npm run type-check` → tsc -b --noEmit, exit 0 (no diagnostics).

Also re-ran the adjacent test suites that touched the same surface to confirm no regression: `npm test -- --run AdminDashboard.test.tsx App.coverage.test.tsx admin.test.ts ExtractionHealth.test.tsx CrawlerAdmin.test.tsx` → 6 files, 105 tests, all passed in 1.77s. The pre-existing CrawlerAdmin act() warnings are unrelated noise (no test failures).

Verified slice-level signals against the slice plan's Verification section:
- Runtime signal: ExtractionHealth surfaces a network failure inline via `ErrorAlert` (covered by test (b) — HTTP 500 → inline alert with parse_status hint, no compliance hero).
- Inspection surface: page itself renders compliance/coverage/failure-rate at a glance for the operator.
- Failure visibility: error message includes `HTTP <status>` (or `Network error`) plus the explicit "Check crawled_pages.parse_status" hint per the slice plan.
- Redaction: response shape (per T01 types) is adapter slugs + counts only; no PII or tokens propagate to the DOM.

The failure-rate ordering invariant (sorted by rate desc) is asserted in test (a) by reading `tbody tr` document order. The Q5 safe-guard against missing `coverage.per_tier.<tier>` is implemented via `Object.entries(data?.coverage?.per_tier ?? {})` so an absent tier key cannot crash the render.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run ExtractionHealth.test.tsx` | 0 | ✅ pass | 753ms |
| 2 | `cd frontend && npm run type-check` | 0 | ✅ pass | 6000ms |
| 3 | `cd frontend && npm test -- --run AdminDashboard.test.tsx App.coverage.test.tsx admin.test.ts ExtractionHealth.test.tsx CrawlerAdmin.test.tsx` | 0 | ✅ pass | 1770ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/admin/ExtractionHealth.tsx`
- `frontend/src/pages/admin/ExtractionHealth.test.tsx`
