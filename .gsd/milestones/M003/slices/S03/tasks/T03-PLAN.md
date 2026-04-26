---
estimated_steps: 52
estimated_files: 5
skills_used: []
---

# T03: Collapse ViewPart price blocks into one 'Price by retailer' table + harden retailer outbound links with rel/icon affordance

The structural heart of S03. Single atomic refactor of `frontend/src/pages/builder/ViewPart.tsx` per MEM150 + MEM151 + MEM171.

## What to delete

- `RetailerBreakdownRow` helper component (ViewPart.tsx lines 94-124).
- `PriceSummaryBlock` helper component (lines 126-199).
- The standalone `PriceSummaryBlock` invocation at lines 752-778 (the 4-cell stat strip + Tabs/flat list).
- The standalone listings-driven `Price by retailer` block at lines 780-871.
- `Tabs`, `TabsContent`, `TabsList`, `TabsTrigger` imports (lines 54-59) IF no other call site survives in this file. Verify by grep before committing.
- `RetailerPriceBreakdown` import alone (line 29) survives because the collapsed block still uses it.

## What to add

One new collapsed `Price by retailer` block at the deleted blocks' position (replaces both, single sibling under `Card`). Structure:

```
<div className="mb-6">
  <div className="flex items-center justify-between mb-2">
    <SectionHeader title="Price by retailer" />
    <PriceAlertSubscribeButton ... />  {/* unchanged — sibling of the new block */}
  </div>
  {/* one-line summary header — only renders when observation_count > 0 */}
  {priceSummary?.summary?.observation_count > 0 && (
    <p data-testid="price-summary-header" className="text-sm text-gray-400 mb-3">
      {formatCents(priceSummary.summary.min_cents)}–{formatCents(priceSummary.summary.max_cents)} across {priceSummary.retailers?.length ?? 0} retailers, last observed {trendArrow(priceSummary.summary.trend)} {new Date(priceSummary.summary.last_observed_at).toLocaleDateString()}
    </p>
  )}
  {/* error states + collapsed table */}
</div>
```

The collapsed table is a `<ul>` with one `<li data-testid="retailer-row">` per retailer (sourced from `priceSummary.retailers ?? []`, joined to `listingsData ?? []` by `retailer_id` for `product_url`). Each row contains:

- Retailer name (`retailer.retailer_name`).
- `<Sparkline history={priceSummary.history.filter(h => h.retailer_id === retailer.retailer_id)} width={80} height={24} />` — empty render if filter result is empty (the Sparkline component handles `length === 0` already by returning null).
- `formatCents(retailer.last_cents)` + delta arrow (reuse `trendArrow` for direction — derive direction from min/max relative to last, or drop the per-row arrow and keep only the header arrow if simpler).
- Observation timing: `(${observation_count} obs, last ${new Date(retailer.last_observed_at).toLocaleDateString()})`. Add the existing `STALE_LISTING_THRESHOLD_DAYS=60` warning span (`(as of ${date})` with `text-warning`) when `last_observed_at` is older than 60 days. This is the SINGLE source of truth — the prior listings-block stale caveat is gone, so the e2e assertion `getByText(staleCaveat)).toHaveCount(1)` continues to pass.
- `View at retailer` link IF a matching listing has `product_url`: `<a href={listing.product_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/90 text-sm underline inline-flex items-center gap-1">View at retailer <ExternalLink className="h-3 w-3" /></a>`. If no listing or no `product_url`, omit the link entirely (no placeholder).

Edge cases:
- `priceSummary.observation_count === 0` AND `listingsData.length === 0` → render section heading + empty-state copy `"No retailer pricing observed yet."`.
- History present but `listingsData` empty → render rows from `priceSummary.retailers` with sparklines + last_cents + observation timing, NO outbound link (no product_url available).
- Listings present but no history for a retailer → render row with no sparkline, last_known_price_cents from listing.

## Imports

- Add `import { ExternalLink } from 'lucide-react';` at the top (lucide-react is already a dependency — used elsewhere in the codebase).
- Add `import Sparkline from '../../components/charts/Sparkline';`.
- Remove unused Tabs imports if no surviving call site.

## Test rewrites

`frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — all 5 tests rewrite onto the collapsed contract. The mocks (`installGetRouting`, `makeRetailer`, `makeListing`) survive as-is. New assertions per test:

1. **`does not render the Price by retailer block when observation_count is 0 AND listings empty`** — header + empty-state copy, NO `data-testid="retailer-row"`, NO `data-testid="price-summary-header"`.
2. **`renders one retailer-row per priceSummary.retailers entry`** — assert `getAllByTestId('retailer-row').length === retailers.length`; assert each retailer name visible; assert no tablist (`queryByRole('tablist') === null`).
3. **`renders the one-line summary header above the table when observation_count > 0`** — assert `getByTestId('price-summary-header')` is in the document and text matches the format `$X–$Y across N retailers, last observed Z`.
4. **`shows the stale caveat for a retailer with last_observed_at 90 days ago`** — assert `getByText(/as of/i)` is in the document AND `getAllByText(/as of/i).length === 1` (single source of truth).
5. **`renders View at retailer link with target=_blank rel=noopener noreferrer + ExternalLink icon for retailers that have a matching listing.product_url`** — assert `getByRole('link', { name: /View at retailer/i }).getAttribute('rel') === 'noopener noreferrer'`; assert `getAttribute('target') === '_blank'`; assert at least one `<svg>` child of the link (the lucide icon renders as svg).

## E2E spec update

`frontend/e2e/price-history.spec.ts:543` — change `name: 'Price summary (90 days)'` → `name: 'Price by retailer'`. Stale caveat assertion at lines 549-554 survives unchanged (single caveat per page is preserved by the collapse).

## PartsCuration link safety fixup

`frontend/src/pages/admin/PartsCuration.tsx:97` — change `rel="noreferrer"` → `rel="noopener noreferrer"`. Add `<ExternalLink className="h-3 w-3 inline ml-1" />` after the truncated URL inside the same `<a>`. Add the import if missing.

## Out of scope

No new tokens, no new ui/* primitives, no Playwright snapshot refresh in this task — T04 owns the snapshot refresh under reviewed `--update-snapshots` semantics.

## Inputs

- ``.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` — verdict context for ViewPart surfaces`
- ``frontend/src/pages/builder/ViewPart.tsx` — refactor target (lines 88-199 helpers, lines 752-871 sibling blocks)`
- ``frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — 5 tests to rewrite`
- ``frontend/e2e/price-history.spec.ts` — heading assertion at line 543`
- ``frontend/src/pages/admin/PartsCuration.tsx` — link safety fixup at line 97`
- ``frontend/src/components/charts/Sparkline.tsx` — accepts PartPriceHistoryReadWithRetailer[]`
- ``frontend/src/types/Api.ts` — PriceHistorySinglePartResponse / RetailerPriceBreakdown / PartListingReadWithRetailer types`

## Expected Output

- ``frontend/src/pages/builder/ViewPart.tsx` — collapsed 'Price by retailer' block; helpers + Tabs imports removed; Sparkline + ExternalLink imported`
- ``frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — 5 tests rewritten on collapsed contract; all pass under vitest --run`
- ``frontend/e2e/price-history.spec.ts` — heading assertion at line 543 reads 'Price by retailer'`
- ``frontend/src/pages/admin/PartsCuration.tsx` — `rel="noopener noreferrer"` on line 97 + ExternalLink icon`
- ``.gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md` — refactor summary, deleted symbol list, joined-data wiring notes`

## Verification

rg -q 'Price by retailer' frontend/src/pages/builder/ViewPart.tsx && ! rg -q 'price-summary-stat-strip|retailer-breakdown-flat|RetailerBreakdownRow|PriceSummaryBlock' frontend/src/pages/builder/ViewPart.tsx && rg -q 'noopener noreferrer' frontend/src/pages/admin/PartsCuration.tsx && (npm --prefix frontend run type-check) && (npm --prefix frontend test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx)
