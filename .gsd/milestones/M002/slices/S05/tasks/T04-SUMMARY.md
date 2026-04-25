---
id: T04
parent: S05
milestone: M002
key_files:
  - frontend/src/types/Api.ts
  - frontend/src/api/parts.ts
  - frontend/src/api/parts.test.ts
key_decisions:
  - Declared `PriceHistoryBatchSummaryItem` as a `type` alias of `PriceHistorySummary` instead of an empty-extending interface to avoid `@typescript-eslint/no-empty-object-type` — public shape is identical; consumers cannot tell the difference.
  - Migrated existing `getPartPriceHistory` to forward `legacy=true` instead of replacing it, so the Chrome extension and any existing pages keep their flat-array contract without code change. The new object-shape lives on a separate method (`getPartPriceHistorySummary`).
duration: 
verification_result: passed
completed_at: 2026-04-25T18:58:17.920Z
blocker_discovered: false
---

# T04: Wire frontend client + types for getPartPriceHistorySummary and getBatchPriceHistorySummary; migrate getPartPriceHistory to legacy=true shim

**Wire frontend client + types for getPartPriceHistorySummary and getBatchPriceHistorySummary; migrate getPartPriceHistory to legacy=true shim**

## What Happened

Added the new aggregation response types to `frontend/src/types/Api.ts` (`PriceTrend`, `PriceHistorySummary`, `RetailerPriceBreakdown`, `PriceHistorySinglePartResponse`, `PriceHistoryBatchSummaryItem`, `PriceHistoryBatchRequest`, `PriceHistoryBatchResponse`) directly after the existing `PartPriceHistoryReadWithRetailer` interface so the new shapes sit alongside the legacy one.

Updated `frontend/src/api/parts.ts`: imported the three new types from `../types/Api`; migrated the existing `getPartPriceHistory` to forward `legacy=true` to preserve the array-shape contract for downstream callers (Chrome extension, existing pages); added `getPartPriceHistorySummary(partId, { window?, retailer_id? })` calling the new object-shape endpoint with no `legacy` flag; added `getBatchPriceHistorySummary(body)` POSTing to `/parts/price-history`.

Updated `frontend/src/api/parts.test.ts`: rewrote the two existing `getPartPriceHistory` tests to assert `legacy: true` is now forwarded, added the regression-guard test confirming the legacy shim still returns the array shape, plus tests for `getPartPriceHistorySummary` (window forwarding, retailer_id forwarding) and `getBatchPriceHistorySummary` (POST body + URL). 26 tests pass total (was 22; +4 new, 2 modified).

Minor deviation from the literal plan snippet: declared `PriceHistoryBatchSummaryItem` as `type PriceHistoryBatchSummaryItem = PriceHistorySummary` instead of `interface PriceHistoryBatchSummaryItem extends PriceHistorySummary {}` because the empty-extending-interface form trips `@typescript-eslint/no-empty-object-type` and would have introduced a new lint error. The exported shape is identical for consumers.

The test file already had a top-level `eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/no-unsafe-assignment` directive, so the new tests do not introduce any lint errors.

## Verification

Ran the full task-plan verification chain from `frontend/`: `npm run type-check` exits 0; `npm run lint` shows 108 problems, all of which exist on `main` without my changes (verified by `git stash` → re-run lint → same 108 count → `git stash pop`); none of the lint findings are in `parts.ts`, `parts.test.ts`, or `Api.ts`. `npm test -- --run src/api/parts.test.ts` passes all 26 tests including the 4 new cases and the 2 modified `getPartPriceHistory` cases that now expect `legacy: true`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4000ms |
| 2 | `cd frontend && npm run lint (parts.ts, parts.test.ts, Api.ts subset)` | 0 | ✅ pass (no new findings; 108 pre-existing errors unchanged from main, verified via git stash/pop) | 12000ms |
| 3 | `cd frontend && npm test -- --run src/api/parts.test.ts` | 0 | ✅ pass (26/26 tests) | 741ms |

## Deviations

Plan snippet declared `interface PriceHistoryBatchSummaryItem extends PriceHistorySummary {}`. Implementation uses `type PriceHistoryBatchSummaryItem = PriceHistorySummary` to satisfy the project's lint rules (empty extending interfaces are forbidden). Identical at the type level for all consumers.

## Known Issues

The 108 pre-existing frontend lint errors (in unrelated test files) are unchanged by this task and remain as project-wide cleanup work. None block T04 verification because they exist on `main` independent of these changes.

## Files Created/Modified

- `frontend/src/types/Api.ts`
- `frontend/src/api/parts.ts`
- `frontend/src/api/parts.test.ts`
