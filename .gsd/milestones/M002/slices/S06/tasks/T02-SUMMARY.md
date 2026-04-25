---
id: T02
parent: S06
milestone: M002
key_files:
  - frontend/src/components/parts/PartList.tsx
  - frontend/src/components/parts/SparklineCell.tsx
  - frontend/src/components/parts/SparklineCell.test.tsx
  - frontend/src/components/parts/PartList.priceHistory.test.tsx
key_decisions:
  - SparklineCell uses IntersectionObserver lazy-load (rootMargin '100px') + module-level 5-min TTL cache + in-flight Promise dedupe — keeps the catalog batch fast and only fetches per-part history for rows the user actually scrolls to. Captured as MEM076.
  - Single-observation rows render the centered dot from the batch summary alone (synthesizing a one-element history) — no per-part fetch needed, keeping the request count to exactly the one batch POST when no multi-obs row is in view.
  - Test stubs IntersectionObserver and ResizeObserver via vi.stubGlobal because jsdom ships neither; the fake IntersectionObserver pushes its trigger callback into a per-test array so tests can simulate intersection on demand.
duration: 
verification_result: passed
completed_at: 2026-04-25T21:31:33.221Z
blocker_discovered: false
---

# T02: Wire price-history sparkline + delta line into PartList catalog rows with lazy per-part SparklineCell

**Wire price-history sparkline + delta line into PartList catalog rows with lazy per-part SparklineCell**

## What Happened

Integrated the T01 primitives into the live catalog surface. PartList now calls `usePartPriceSummaries` once at the parent level after `parts` is computed (line ~510), batching every visible part's id into a single POST `/parts/price-history`. The hook's empty-IDs short-circuit + stable-sorted-key debounce (T01) carries through unchanged.

In the **table layout** price column (around line ~822), the price cell is now a flex container: the existing `$X.XX` best-price stays as the top line, `<PriceDeltaLine summary={priceSummaries[part.id]} />` renders below it (renders nothing when no summary or zero observations — additive, not a replacement), and a 60×16 `<SparklineCell />` sits to the right.

In the **card layout** (around line ~952), I added a third row under the description rendering `<PriceDeltaLine />` followed by a 120×24 `<SparklineCell />`. The existing `best_price_cents` block is untouched.

`SparklineCell` is the new piece. It reads the summary directly: zero observations → renders nothing; single observation → synthesizes a one-element history from `summary.last_cents` + `last_observed_at` and shows the centered dot from the existing Sparkline (no fetch); multi observation → reserves the slot, sets up an IntersectionObserver with `rootMargin: '100px'`, and only on intersection fetches `partsApi.getPartPriceHistorySummary(partId, { window: '90d' })` and feeds the returned `history` array into Sparkline. A module-level `Map<partId, {history, cachedAt}>` provides a 5-minute TTL cache; a parallel `Map<partId, Promise>` dedupes in-flight requests so a remount during the same render doesn't double-fetch. Failures are caught and logged via `console.warn('[SparklineCell]', partId, err)` then resolve to `[]` — the slot stays blank rather than throwing.

Tests: SparklineCell has 6 unit tests (null/zero/single/lazy-load gate, cross-mount cache hit, fetch-failure swallow). PartList.priceHistory has 3 integration tests asserting (a) exactly ONE POST per displayed page, (b) multi-obs card renders a `[data-testid="sparkline-cell"]` for the multi part and zero-obs card renders none, (c) single-observation cards render the synchronous dot from the summary alone with no per-part GET. Both files stub IntersectionObserver via `vi.stubGlobal` (jsdom doesn't ship one); the SparklineCell unit tests expose a controllable trigger so intersection can be simulated on demand. ResizeObserver is also stubbed for PartList so `useContainerWidth` doesn't blow up. The `__resetSparklineCellCache()` test seam is exported from SparklineCell so each test runs against a fresh module-level cache.

One implementation choice worth flagging: the sparkline data source. The plan correctly notes that the batch summary doesn't carry per-listing history, so the catalog needs the per-part endpoint. Rather than triggering that fetch eagerly for every visible row (which would defeat the batch's purpose), SparklineCell only fires when the row scrolls into view — and only when `observation_count >= 2`. Single-observation rows are served entirely from the batch summary using a synthesized one-element history fed into the existing Sparkline single-dot branch.

## Verification

Ran the slice-plan task verification command exactly as specified:

`cd frontend && npm run type-check && npm test -- --run src/components/parts/SparklineCell.test.tsx src/components/parts/PartList.priceHistory.test.tsx`

- `npm run type-check` → exit 0 (`tsc -b --noEmit` clean).
- `npm test` → exit 0; 2 test files, 9 tests passed (SparklineCell 6, PartList.priceHistory 3).
- Spot-check on dependent existing tests: `npm test -- --run src/pages/parts/PartsCatalog.test.tsx src/pages/parts/UserParts.test.tsx` → 6 tests passed (no regressions from PartList changes; the act() warnings in those files are pre-existing and unrelated).

Slice-level verification status (intermediate task; full-slice gates land on T04):
- Runtime signals: backend `price_history_aggregation:` INFO will fire on each catalog page (S05); frontend logs the batch via apiClient interceptor as planned. Asserted indirectly through the integration test's POST count.
- Inspection surfaces: `<svg role="img">` on sparklines + `data-testid="sparkline-cell"` on the wrapper give devtools/e2e selectors.
- Failure visibility: SparklineCell logs `console.warn('[SparklineCell]', partId, err)` on per-row fetch failure; usePartPriceSummaries logs `console.warn('[usePartPriceSummaries]', err)` on batch failure (T01). Both paths exercised by tests.
- Redaction: n/a — no PII or auth in these surfaces.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | pass | 1500ms |
| 2 | `cd frontend && npm test -- --run src/components/parts/SparklineCell.test.tsx src/components/parts/PartList.priceHistory.test.tsx` | 0 | pass | 763ms |
| 3 | `cd frontend && npm test -- --run src/pages/parts/PartsCatalog.test.tsx src/pages/parts/UserParts.test.tsx` | 0 | pass | 797ms |

## Deviations

None of substance. The plan suggested passing the summary into a SparklineCell that "fetches the per-part history lazily IF observation_count >= 2"; implementation matches that exactly, with the addition that single-observation cells render directly from the summary without any fetch (the plan's text is consistent with this — it only requires fetching for the multi-obs case). Otherwise the wiring matches the plan's table-layout (line ~813) and card-layout (line ~933) targets verbatim.

## Known Issues

None blocking. The IntersectionObserver fallback (older environments without it) eager-fetches; not exercised by tests because jsdom always gets the stub, but the branch exists for production safety. The synthesized one-element history for single-obs rows uses placeholder `retailer_id: 'synthetic'` strings — not exposed to the user, and Sparkline only renders the centered dot which doesn't read those fields, but worth noting if anyone later inspects those values.

## Files Created/Modified

- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/parts/SparklineCell.tsx`
- `frontend/src/components/parts/SparklineCell.test.tsx`
- `frontend/src/components/parts/PartList.priceHistory.test.tsx`
