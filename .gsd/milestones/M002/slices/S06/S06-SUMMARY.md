---
id: S06
parent: M002
milestone: M002
provides:
  - ["frontend/src/components/charts/Sparkline.tsx :: pure-SVG inline sparkline (zero/single/multi)", "frontend/src/components/parts/PriceDeltaLine.tsx :: trend arrow + min/max range", "frontend/src/hooks/usePartPriceSummaries.ts :: parent-level batch fetch hook with anti-loop guard", "frontend/src/components/parts/SparklineCell.tsx :: lazy per-row sparkline (IntersectionObserver + 5-min TTL cache + in-flight dedupe)", "frontend/src/components/parts/PartList.tsx :: catalog rows render sparkline + delta line", "frontend/src/pages/builder/ViewPart.tsx :: 'Price summary (90 days)' block + 60-day stale 'as of' caveat", "frontend/e2e/price-history.spec.ts :: Playwright contract for catalog batch + detail breakdown + stale caveat at 3 viewports", "STALE_LISTING_THRESHOLD_DAYS=60 convention reusable by S07 alert evaluation"]
requires:
  - slice: S05
    provides: partsApi.getBatchPriceHistorySummary + partsApi.getPartPriceHistorySummary + PriceHistoryBatchResponse / PriceHistorySinglePartResponse / RetailerPriceBreakdown types
  - slice: S08
    provides: frontend/src/components/ui/tabs.tsx Tabs primitive (used for >3-retailer breakdown)
affects:
  - ["S07: alert threshold evaluation can reuse STALE_LISTING_THRESHOLD_DAYS const + the per-retailer aggregation summary shape", "S10: parts-catalog redesign will swap PartList rendering onto S08 primitives but the sparkline/delta-line integration travels with whatever PartList becomes — keep the parent-level batch hook + lazy SparklineCell pattern", "S13: milestone-verification owns the live end-to-end UAT (this slice's UAT is mocked-API; the real-backend flow falls to S13)"]
key_files:
  - ["frontend/src/components/charts/Sparkline.tsx", "frontend/src/components/parts/PriceDeltaLine.tsx", "frontend/src/hooks/usePartPriceSummaries.ts", "frontend/src/components/parts/SparklineCell.tsx", "frontend/src/components/parts/PartList.tsx", "frontend/src/pages/builder/ViewPart.tsx", "frontend/e2e/price-history.spec.ts"]
key_decisions:
  - ["Two-tier price-history rendering — parent-level batch fetch via usePartPriceSummaries + lazy per-row SparklineCell only on IntersectionObserver intersection. Single-observation rows synthesize a one-element history from the batch summary alone (no fetch), keeping the catalog request count to exactly one batch POST plus per-multi-row GETs only when scrolled into view.", "Hook anti-loop primitive — usePartPriceSummaries memoizes on a primitive sorted-joined string key (not the raw array), gates setState behind a useRef-cached lastKey, and returns a frozen EMPTY_SUMMARIES singleton for the empty branch. Without this combo callers passing fresh array references each render put the test runner into an infinite loop and OOM'd the worker.", "Legacy chart retention on /parts/:id — kept the existing PriceHistoryLineChart untouched and added the new 'Price summary (90 days)' block as a sibling above it. The legacy fetch (getPartPriceHistory with legacy=true axios param) and the new fetch (getPartPriceHistorySummary) hit the same URL but feed different shapes to different UI; do NOT collapse them in S07/S10/S13.", "Sparkline implemented as pure SVG (no recharts/visx dep) — viewBox + preserveAspectRatio='none' + 1.5px hsl(var(--primary)) stroke. Polyline normalization handles flat series (zero price-range) by centering at y=height/2.", "PriceDeltaLine 'over N days' suffix collapsed to bare min→max — PriceHistorySummary has no earliest-observed timestamp so the calendar-day span isn't computable from the summary alone. The plan explicitly anticipated this fallback ('without the duration when both bounds aren't knowable'). If the backend later exposes earliest-observed, the suffix can be added without API churn.", "60-day staleness threshold hoisted to STALE_LISTING_THRESHOLD_DAYS module-level const in ViewPart.tsx — pin behavior in one place; reuse if S07 alerts need a similar threshold.", "Tabs vs flat list switch on >3 retailers (literal greater-than, not greater-than-or-equal) — 4-retailer parts activate Tabs; 3-retailer parts render the flat list. Plan said 'retailer count > 3' explicitly.", "page.route() matcher in Playwright e2e MUST exclude Vite source-module URLs at /src/api/*.ts — use /\\/api\\/(?!.*\\.ts)/ to scope to backend prefix only. Intercepting source modules with JSON crashes the bundle.", "Date.now() pinning via page.addInitScript for stale-caveat e2e math — keeps the 60-day threshold deterministic across CI runs without affecting React/Playwright internals that use the Date constructor."]
patterns_established:
  - ["Catalog batch + lazy per-row primitive — when a list view needs both summary data (cheap, batched) AND per-row history (expensive), use a parent-level batch hook + a lazy IntersectionObserver-gated row component with a module-level TTL Map cache + in-flight Promise dedupe. Single-observation rows render synchronously from the batch summary by synthesizing a one-element history.", "Hook stable-key memoization with frozen empty singleton — useMemo a primitive sorted-joined string key from array props, derive the sorted array from the key (also memoized), gate empty-branch setState behind a useRef-cached lastKey, and return a frozen EMPTY singleton for the empty case. Pattern prevents fresh-reference render loops when callers don't memoize their array.", "Test seam for module-level caches — export a __reset<Name>Cache() function from the cache-owning module so each test runs against a fresh state. Used by SparklineCell's TTL cache.", "Playwright spec contract — module-level fixtures + page.route mockApi helper + Date.now pinning + dual network counter (route handler + page.on('request')) for batch-endpoint contract assertions. Excludes /src/api/*.ts via lookahead in the URL regex.", "Lint-clean act(async) — when a sync trigger inside `await act(async () => ...)` doesn't await anything, the require-await rule fires. Add `await Promise.resolve()` inside the block to preserve microtask flush semantics while satisfying the rule. (Alternative: drop async if no real flush is needed.)"]
observability_surfaces:
  - ["console.warn '[usePartPriceSummaries]' on batch fetch failure (exercised by T01 hook tests)", "console.warn '[SparklineCell]' on per-row fetch failure (exercised by T02 SparklineCell tests)", "Inline 'Price summary unavailable' on /parts/:id when getPartPriceHistorySummary errors (replaces throwing)", "Backend INFO log 'price_history_aggregation:' fires on every catalog batch fetch via S05 service (no new frontend logging needed — apiClient interceptor logs the request)", "Browser devtools Network panel — exactly one POST /parts/price-history per displayed catalog page (asserted by T02 integration test + T04 e2e dual counter)", "data-testid markers ('sparkline', 'sparkline-polyline', 'sparkline-dot', 'sparkline-cell', 'price-delta-line', 'price-delta-arrow', 'price-summary-stat-strip', 'retailer-breakdown-flat', 'retailer-breakdown-row') for devtools/e2e selectors"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T22:03:46.897Z
blocker_discovered: false
---

# S06: Price-history frontend surfaces (sparkline + detail view)

**Shipped the user-visible price-history loop on top of S05's read seam: every part-list card with observations renders a sparkline + delta line, and /parts/:id shows a per-retailer aggregation block with a 60-day "as of" stale caveat — exactly one batch POST per catalog page, lazy per-row history fetches only on scroll-into-view.**

## What Happened

S06 turned the S05 backend aggregation API into the user-visible catalog and detail surfaces, end-to-end against deterministic mocked data. The slice produced four artifacts in sequence (T01 → T04) with no blockers and no scope deviations.

**T01 — primitives.** Built three reusable client surfaces: (1) `frontend/src/components/charts/Sparkline.tsx`, a pure-SVG inline sparkline with a normalized polyline (1.5px `hsl(var(--primary))` stroke, `preserveAspectRatio='none'`) for multi-observation series, a centered `<circle>` for the single-observation case, and renders nothing for zero observations. Sorts points by `observed_at` ascending and gracefully handles flat series. (2) `frontend/src/components/parts/PriceDeltaLine.tsx`, which renders `↑/↓/·` trend glyph + `Tracked since <date>` for one observation, or `↑/↓/· $<min> → $<max>` for two-or-more. The plan-anticipated fallback (no "over N days" suffix) applies because `PriceHistorySummary` has no earliest-observed timestamp — the calendar-day span isn't computable from the summary alone. (3) `frontend/src/hooks/usePartPriceSummaries.ts`, a sorted-key memoized batch fetch hitting `partsApi.getBatchPriceHistorySummary`. The hook uses a primitive `sortedKey` (string), a `useRef`-cached `lastKeyRef` to gate duplicate setStates, and a frozen `EMPTY_SUMMARIES` singleton for the empty branch — without this trifecta callers passing fresh array references each render combined with always-fresh `{}` setStates put the test runner into an infinite render loop and OOM'd the worker (captured as MEM081). On error the hook logs `console.warn('[usePartPriceSummaries]', err)` and returns `{ summaries: {}, error, isLoading: false }` without throwing. 22 vitest unit tests cover the cardinalities + every trend arrow + the hook's debounce/error/empty paths.

**T02 — catalog wiring.** Integrated the primitives into `frontend/src/components/parts/PartList.tsx`. The hook is called once at the parent level after `parts` is computed — never per row. The price column in the table layout adds a `PriceDeltaLine` below the existing `$X.XX` cell and a 60×16 `<SparklineCell />` to its right; the card layout adds a third row under the description with `PriceDeltaLine` + a 120×24 `SparklineCell`. The new `frontend/src/components/parts/SparklineCell.tsx` is the load-management primitive: zero observations → render nothing; single observation → synthesize a one-element history from `summary.last_cents`+`last_observed_at` and feed it to Sparkline's existing dot branch (no fetch); multi observation → set up an IntersectionObserver with `rootMargin: '100px'` and only on intersection call `partsApi.getPartPriceHistorySummary(partId, { window: '90d' })`. A module-level `Map<partId, {history, cachedAt}>` provides a 5-minute TTL cache; a parallel `Map<partId, Promise>` dedupes in-flight requests so a remount during the same render doesn't double-fetch. Failures resolve to `[]` after `console.warn('[SparklineCell]', partId, err)` — the slot stays blank rather than throwing. Captured as pattern MEM080. The integration test asserts exactly ONE POST to `/parts/price-history` for the visible page.

**T03 — detail view.** Extended `frontend/src/pages/builder/ViewPart.tsx` to consume both the legacy `getPartPriceHistory` AND the new `getPartPriceHistorySummary` in parallel. Inserted a new "Price summary (90 days)" block ABOVE the existing two-column "Price history / Price by retailer" grid; the block renders only when `priceSummary?.summary?.observation_count > 0` and shows a 4-cell stat strip (min/max/last/trend) + per-retailer breakdown that auto-switches between a flat `<ul>` (≤3 retailers) and the S08 Radix `Tabs` primitive (>3 retailers, one trigger per retailer + an "All" tab). For the existing listings list, added a 60-day stale caveat keyed off `last_price_updated_at` (`STALE_LISTING_THRESHOLD_DAYS = 60` constant at the top of the file) — listings older than that get an amber `(as of <localized date>)` span appended to the existing "updated <date>" line. Because both `getPartPriceHistory` and `getPartPriceHistorySummary` hit the same `/parts/{id}/price-history` URL and only differ by axios `params`, the existing ViewPart test mock (which returned `{data: []}` for that URL) was crashing the new render path — hardened the guard to `priceSummary?.summary?.observation_count > 0` so a malformed shape skips the block silently. Footgun captured as MEM084. Tests cover all five plan-mandated cases (zero observations hides block; ≤3 retailers flat list; >3 retailers tablist; 90-day-stale shows caveat; 5-day-fresh hides caveat).

**T04 — Playwright e2e.** Added `frontend/e2e/price-history.spec.ts` with module-level fixtures for three parts (multi/single/zero observation), a `mockApi(page)` router, and three tests at three viewports (mobile/tablet/desktop). Two key gotchas surfaced and were captured: (1) the page.route() URL matcher MUST exclude Vite's `/src/api/*.ts` source-module paths — `/\/api\/(?!.*\.ts)/` is the correct shape (MEM082); intercepting source modules with JSON crashes the bundle. (2) The responsive table layout scrolls horizontally on tablet/mobile, so the multi-observation row's `[data-part-id]` must be `scrollIntoViewIfNeeded()`-ed before asserting `[role=img]` — IntersectionObserver-driven SparklineCell only fires its lazy fetch when the row is in view (MEM083). Pinned `Date.now()` via `page.addInitScript` so the 60-day stale-caveat threshold is deterministic. Used a dual network-counter (route handler + `page.on('request')` listener) for the 1-batch-POST contract assertion — belt-and-braces witness that survives even if the route mock is bypassed. Six baseline screenshots committed under `frontend/e2e/price-history.spec.ts-snapshots/` (3 viewports × 2 screenshot tests).

The slice consumed exactly the surfaces declared in Integration Closure (S05 batch + single endpoints, S08 Tabs primitive, existing PartList/ViewPart) and produced the new wiring promised (parent-level batch hook in PartList, lazy SparklineCell, ViewPart aggregation block). The legacy `getPartPriceHistory` chart in ViewPart is intentionally retained side-by-side with the new aggregation block — the plan called this out and the existing detail-page line chart stays untouched.

**Lint must-have closure.** End-of-slice lint pass surfaced 5 new errors in T02's test files (4 `require-await` violations on `act(async () => ...)` blocks that didn't await, 1 `no-unsafe-assignment` from a vitest matcher type leak). Fixed in this closing pass: added `await Promise.resolve()` inside each `act(async)` block to preserve microtask flush semantics while satisfying the rule, dropped `async` from the one test that didn't need it, and extended the existing eslint-disable header on `PartList.priceHistory.test.tsx` to also cover `no-unsafe-assignment` for vitest matcher composition. Re-lint of the four touched files: 0 errors, 1 pre-existing fast-refresh warning matching the S08 baseline (MEM061). Re-ran the affected vitest suites — all 9 tests still green.

## Verification

All slice-plan verification gates passed in this closing session.

1. `cd frontend && npm run type-check` → exit 0 (`tsc -b --noEmit` clean).
2. `cd frontend && npm test -- --run <all 7 S06 vitest files>` → exit 0; 7 files, 39 tests passed.
3. `cd frontend && npm run test:e2e` → exit 0; 15/15 Playwright tests passed across 3 viewports. Catalog test's network-counter confirms exactly ONE POST `/parts/price-history` per page.
4. End-of-slice lint pass on the four S06-touched files: 0 errors, 1 pre-existing fast-refresh warning matching the S08 baseline (MEM061). Five new lint errors introduced during T02 were fixed in this closing pass without behavior change — re-ran affected vitest suites and all 9 tests stayed green.

Slice plan demo gates:
- Catalog cards with observations → sparkline + delta line: covered by T02 integration tests + T04 e2e screenshot tests at 3 viewports.
- Detail view retailer breakdowns + listing-level history: covered by T03 ViewPart.priceSummary tests (5/5).
- Stale-observation "as of" caveat: covered by T03 (90-day-stale visible, 5-day-fresh absent) + T04 e2e.
- Zero-observation parts → no sparkline: covered by T01 unit + T02 integration + T04 e2e.
- Exactly ONE batch POST per displayed catalog page: covered by T02 integration test + T04 dual-counter e2e assertion.

Failure visibility: SparklineCell + usePartPriceSummaries log via console.warn on fetch failure; ViewPart shows inline "Price summary unavailable" rather than throwing.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None of substance. The plan's PriceDeltaLine "over N days" suffix correctly anticipated the fallback when an earliest-observed timestamp isn't available — implementation matches that fallback exactly. Playwright snapshot filenames diverge from the plan's heuristic Expected Output names (the plan listed `price-history-catalog-sparklines-1-mobile-linux.png` etc., but Playwright slugs from the actual test title producing `-parts-catalog-renders-sparklines-delta-lines-1-mobile-linux.png`); functionally equivalent — same 6 files, same coverage. End-of-slice lint cleanup: 5 new errors introduced during T02 (4 require-await on act-async blocks, 1 no-unsafe-assignment on a vitest matcher) were fixed in this closing pass without behavior change — `await Promise.resolve()` inside the act blocks + extending an existing eslint-disable header. Tests still 9/9 green after the cleanup.

## Known Limitations

PriceDeltaLine multi-observation branch renders the bare '$<min> → $<max>' fallback (no 'over N days' suffix) because PriceHistorySummary has no earliest-observed timestamp. The plan anticipated this. If the backend summary later exposes earliest-observed (or the hook starts pulling per-part history at the parent level), the suffix can be added without API churn.

The IntersectionObserver fallback in SparklineCell (older environments without IO) eager-fetches; not exercised by tests because jsdom always gets the stub, but the branch exists for production safety.

Single-observation cells use a synthesized one-element history with a placeholder `retailer_id: 'synthetic'` — not exposed to the user, and Sparkline's dot branch doesn't read those fields. Worth noting if anyone later inspects those values.

The slice's UAT bar is mocked-API (vitest + Playwright with page.route). Live-backend end-to-end (real product → spec extraction → ingest → aggregation → UI → alert email) lives with S13 milestone-verification by design.

## Follow-ups

S07 (alerts) should reuse the per-retailer aggregation primitives + STALE_LISTING_THRESHOLD_DAYS const for threshold evaluation. S10 (parts-catalog redesign) will swap PartList rendering onto S08 primitives but the parent-level batch hook + lazy SparklineCell pattern travels — preserve the one-batch-POST-per-page contract. S13 owns the real-backend UAT. If the M002 design system later moves to React Query, usePartPriceSummaries should be migrated as a thin adapter over a useQuery instead of the current useState/useEffect implementation. The pre-existing fast-refresh warning on SparklineCell.tsx (the __resetSparklineCellCache export sharing a file with a component) matches the S08 baseline — non-blocking, but a future cleanup pass could move the test seam to a sibling file if the React 19 fast-refresh ergonomics get stricter.

## Files Created/Modified

- `frontend/src/components/charts/Sparkline.tsx` — T01 — pure-SVG inline sparkline (zero/single/multi rendering, no recharts dep, viewBox + preserveAspectRatio='none')
- `frontend/src/components/charts/Sparkline.test.tsx` — T01 — 6 vitest cases covering zero/single/multi/sort/aria/flat-series rendering
- `frontend/src/components/parts/PriceDeltaLine.tsx` — T01 — trend arrow + min/max range; null/undefined/zero-observation null render
- `frontend/src/components/parts/PriceDeltaLine.test.tsx` — T01 — 10 cases covering null/zero/single/multi cardinalities + each trend arrow + rounding
- `frontend/src/hooks/usePartPriceSummaries.ts` — T01 — sorted-key memoized batch fetch hook with frozen-empty-singleton anti-loop guard
- `frontend/src/hooks/usePartPriceSummaries.test.ts` — T01 — 6 cases covering empty-IDs short-circuit, batch fetch, debounce, error path, refetch on key change
- `frontend/src/components/parts/PartList.tsx` — T02 — wired parent-level usePartPriceSummaries hook + integrated PriceDeltaLine + SparklineCell into table and card layouts (additive, no replacement of existing best-price rendering)
- `frontend/src/components/parts/SparklineCell.tsx` — T02 — lazy per-row sparkline primitive: IntersectionObserver gating (rootMargin '100px') + module-level 5-min TTL cache + in-flight Promise dedupe; single-obs synthesized history; failure-resilient via console.warn + empty array
- `frontend/src/components/parts/SparklineCell.test.tsx` — T02 — 6 cases covering null/zero/single/lazy-load gate, cross-mount cache hit, fetch-failure swallow; later cleaned for require-await rule
- `frontend/src/components/parts/PartList.priceHistory.test.tsx` — T02 — 3 integration cases asserting exactly ONE POST per page + sparkline-svg presence on multi-obs + absence on zero-obs; later cleaned with extended eslint-disable header
- `frontend/src/pages/builder/ViewPart.tsx` — T03 — added third useApiRequest over getPartPriceHistorySummary; new 'Price summary (90 days)' block above the legacy two-column grid; flat-list-or-Tabs switch on >3 retailers; STALE_LISTING_THRESHOLD_DAYS=60 const; amber 'as of' caveat on stale listings; hardened guard for malformed shapes
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — T03 — 5 cases covering zero-obs hides block, ≤3 retailers flat list, >3 retailers tablist, 90-day-stale shows caveat, 5-day-fresh hides caveat
- `frontend/e2e/price-history.spec.ts` — T04 — Playwright spec with module-level fixtures, mockApi helper (excludes /src/api/*.ts), Date.now pinning, dual network counter, 3 tests at 3 viewports
- `frontend/e2e/price-history.spec.ts-snapshots/` — T04 — 6 baseline screenshots (2 screenshot tests × 3 viewports: mobile/tablet/desktop on Linux)
- `.gsd/PROJECT.md` — Slice closure — added S06 entry to M002 milestone status with summary of artifacts and test counts
