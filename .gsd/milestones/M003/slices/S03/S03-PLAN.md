# S03: Responsive audit + ViewPart IA collapse + outbound link safety

**Goal:** Audit every dense table and card-grid view at 360/768/1280 with realistic densest data, repair the two admin-table overflow sites flagged by MEM172, collapse ViewPart's two redundant price blocks into ONE "Price by retailer" table per MEM150, and harden every retailer outbound link with `target="_blank" rel="noopener noreferrer"` + a Lucide `<ExternalLink />` icon affordance per MEM151. Substrate is the clean S01+S02 semantic-token surface — no fighting legacy palette noise.
**Demo:** Per-viewport verdict list (pass / fixed / acceptable-as-scroll) in slice summary for every dense `<table>` view (4 admin tables + ResponsiveTableWrapper) and every dense card-grid view (PartsCatalog, BuildLists, BuildListPart list, Search) at 360 / 768 / 1280 with realistic densest data. The `/parts` price-column overflow is fixed at root cause. ViewPart shows ONE 'Price by retailer' block (last price + sparkline + observation timing + outbound link per retailer); summary stats either dropped or compressed to a one-line header. Every outbound retailer link uses `target="_blank" rel="noopener noreferrer"` + Lucide external-link icon affordance.

## Must-Haves

- Per-viewport verdict list (pass / fixed / acceptable-as-scroll) recorded in T01-SUMMARY.md for every dense `<table>` view (4 admin tables + ResponsiveTableWrapper consumers PartList + BuildListPartList) and every dense card-grid view (PartsCatalog, BuildListsCatalog, Search) at 360/768/1280
- CrawlerAdmin rate-limit table (line 322) and ExtractionHealth per-tier coverage table (line 203) both wrapped in `overflow-x-auto`; UserManagement / PartsCuration / ExtractionHealth failure-rate already wrapped — confirmed by audit
- ViewPart shows ONE "Price by retailer" block with columns: retailer name, sparkline (per-retailer history filtered by retailer_id), last price + delta arrow, observation timing (relative + `as of` stale caveat at >60d), outbound `View at retailer →` link with `<ExternalLink className="h-3 w-3" />` affordance
- Summary stats compressed to one-line header: `$min–$max across N retailers, last observed {arrow} Z` — the standalone 4-cell stat strip (`data-testid="price-summary-stat-strip"`) is deleted, the Tabs-when->3-retailers pattern is deleted, the standalone listings block is deleted
- `RetailerBreakdownRow` and `PriceSummaryBlock` helper components (lines 88-199 of ViewPart.tsx) deleted; `Tabs` / `TabsContent` / `TabsList` / `TabsTrigger` imports removed if unused after collapse
- All 5 tests in `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` rewritten to assert on collapsed contract (sparkline svg + last_cents + observation timing + product_url href + ExternalLink icon presence + `as of` stale caveat); `frontend/e2e/price-history.spec.ts:543` heading assertion updated to "Price by retailer"
- Stale caveat (`as of {date}`) appears EXACTLY ONCE per retailer row in the collapsed block — single source of truth (listings joined into the table); existing `STALE_LISTING_THRESHOLD_DAYS=60` logic preserved
- `frontend/src/pages/admin/PartsCuration.tsx:97` `rel="noreferrer"` → `rel="noopener noreferrer"` and `<ExternalLink className="h-3 w-3" />` icon added next to the truncated URL link
- 3 Playwright PNG baselines for `/parts/:id detail renders retailer breakdown + stale caveat` refreshed at mobile/tablet/desktop and reviewed before commit
- All S01/S02 grep gates still green: zero raw palette utility hits, zero `glass-(card|button)?` hits, zero `var(--(primary|neutral|accent|gradient)-` consumer hits in `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`
- Outbound link cross-check: every `target="_blank"` consumer of a retailer URL (ViewPart collapsed block + PartsCuration line 96) carries `rel="noopener noreferrer"` (informational gate; non-retailer outbound links elsewhere with `rel="noreferrer"` alone are out of scope)
- `npm --prefix frontend run build`, `type-check`, `lint`, `test`, and `npx playwright test` (with snapshot refresh reviewed) all green

## Proof Level

- This slice proves: - This slice proves: integration (UI contract + visual regression + grep gates)
- Real runtime required: yes (Playwright e2e + vitest with jsdom)
- Human/UAT required: no (slice closes against mechanical gates; manual UAT happens at S06)

## Integration Closure

- Upstream surfaces consumed: `frontend/src/components/charts/Sparkline.tsx` (M002/S06 — accepts `PartPriceHistoryReadWithRetailer[]`); `frontend/src/types/Api.ts` (`PriceHistorySinglePartResponse`, `RetailerPriceBreakdown`, `PartListingReadWithRetailer`, `PartPriceHistoryReadWithRetailer`); `frontend/src/components/ui/card.tsx` (M002/S08); semantic tokens / inline tokenized utilities from S01+S02
- New wiring introduced in this slice: per-retailer history derivation (`history.filter(h => h.retailer_id === retailerId)`) wired client-side inside the collapsed ViewPart block; listings joined to retailers by retailer_id for outbound product_url; `lucide-react` `ExternalLink` icon imported and rendered next to every retailer outbound link
- What remains before the milestone is truly usable end-to-end: S04 must hard-delete the legacy `:root` palette / `@theme` mirror / `.glass*` / 11 keyframes from `index.css`; S05 must run the page-by-page polish pass at 3 viewports; S06 must run the close-out gauntlet

## Verification

- Runtime signals: T01 audit verdict table is the diagnostic record — every surface gets `pass` / `fixed` / `acceptable-as-scroll` per viewport with one-sentence justification. This is the durable proof that the responsive audit happened, not just the layout fixes.
- Inspection surfaces: T01-SUMMARY.md verdict table; `git status --short` post-Playwright proves baseline drift extent; vitest `--run` + Playwright HTML report on failure
- Failure visibility: failed grep gate exits 0 (legacy hit found) instead of expected exit 1; failed Playwright run leaves screenshots in `frontend/test-results/`; failed vitest leaves JSON-shaped error output identifying the test file + line
- Redaction constraints: none (no PII or secrets touched)

## Tasks

- [x] **T01: Responsive audit pass — record per-viewport verdict for every dense table + card-grid view at 360/768/1280** `est:1.5h`
  Read-only audit pass producing a verdict table consumed by T02 and T03. Visit each surface with realistic densest data at 360, 768, and 1280; record `pass` (no overflow, content readable), `fixed-pending` (overflow surfaced — fix scheduled in T02 or T03), or `acceptable-as-scroll` (table is dense by design and lives inside `overflow-x-auto` — horizontal scroll is the intended UX) per viewport. Output goes into `tasks/T01-SUMMARY.md` as a markdown table — no source code changes in this task.

## What to audit

Dense `<table>` views (4 admin + 2 ResponsiveTableWrapper consumers):
- `frontend/src/pages/admin/UserManagement.tsx:346-484` — 11-column user-management table inside `overflow-x-auto` (verdict-only; expected `acceptable-as-scroll` at 360/768, `pass` at 1280).
- `frontend/src/pages/admin/CrawlerAdmin.tsx:321-380` — 5-column rate-limit table inside `rounded border` div with NO horizontal scroll wrapper (expected `fixed-pending` at 360 — flag for T02; verdict at 768 / 1280).
- `frontend/src/pages/admin/ExtractionHealth.tsx:203-230` — 2-column per-tier coverage table inside per-tier card with NO horizontal scroll wrapper (probably narrow enough to `pass` at 360; if not, flag `fixed-pending` for T02). Also audit `failure-rate` table at lines 248-285 (already inside `overflow-x-auto` — `acceptable-as-scroll`).
- `frontend/src/pages/admin/PartsCuration.tsx:697-746` — 4-column scan-diff table inside `overflow-x-auto` (expected `acceptable-as-scroll`).
- `frontend/src/components/parts/PartList.tsx` — uses `useResponsiveColumns` + `ResponsiveTableWrapper`. Container is `frontend/src/pages/parts/PartsCatalog.tsx`. Verdict-only.
- `frontend/src/components/buildListParts/BuildListPartList.tsx` — uses `useResponsiveColumns` + `ResponsiveTableWrapper`. Container is `frontend/src/pages/buildLists/ViewBuildList.tsx`. Verdict-only.

Dense card-grid views (Tailwind responsive grid):
- `frontend/src/pages/parts/PartsCatalog.tsx` (table layout via PartList — overlaps with PartList audit row).
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx:625` (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`).
- `frontend/src/pages/Search.tsx:464` (`<PartList layout="table" />` for parts; `tile-grid-compact` CSS class for users + build lists).

## How to audit

Locally serve the app (`npm --prefix frontend run dev`), navigate to each surface with seeded sample data (run `python scripts/populate_sample_data.py` from `backend/` first if the local DB is empty), and use Chrome DevTools device toolbar to set viewport to 360, 768, then 1280. Record what you see in a one-row-per-(surface × viewport) table. Per MEM170: 360 is the manual UAT target only; Playwright `toHaveScreenshot()` runs at 375 (mobile project default) — note this in the summary if it changes the verdict at 360 vs 375.

## Out of scope

No code changes — this is read-only. If a surface needs a fix, write the fix into the verdict cell as `fixed-pending → T02` or `fixed-pending → T03` and let the next task act on it. Resist the urge to fold in the fix here — keeping audit and repair separate avoids thrash.
  - Files: `frontend/src/pages/admin/UserManagement.tsx`, `frontend/src/pages/admin/CrawlerAdmin.tsx`, `frontend/src/pages/admin/ExtractionHealth.tsx`, `frontend/src/pages/admin/PartsCuration.tsx`, `frontend/src/components/parts/PartList.tsx`, `frontend/src/components/buildListParts/BuildListPartList.tsx`, `frontend/src/pages/parts/PartsCatalog.tsx`, `frontend/src/pages/buildLists/BuildListsCatalog.tsx`, `frontend/src/pages/Search.tsx`, `.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md`
  - Verify: test -f .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md && grep -c '^|' .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md | awk '$1 >= 24'

- [x] **T02: Wrap two admin tables in `overflow-x-auto` per audit findings** `est:30m`
  Mechanical fix task acting on T01's `fixed-pending → T02` verdicts. Per MEM172, two admin tables lack horizontal-scroll wrappers and create page-level h-scroll at 360px:

1. **`frontend/src/pages/admin/CrawlerAdmin.tsx:322`** — wrap the rate-limit `<table>` in a `<div className="overflow-x-auto">`. The existing `rounded border border-gray-700/60 overflow-hidden` outer div does not allow horizontal scroll inside the rounded crop. Replace `overflow-hidden` → `overflow-x-auto` on that wrapper (preserves the rounded chrome), OR insert an inner `<div className="overflow-x-auto">` and keep the outer wrapper for the border. Choose whichever produces the cleaner diff — the simpler pattern is changing `overflow-hidden` → `overflow-x-auto` on line 322's div className.
2. **`frontend/src/pages/admin/ExtractionHealth.tsx:203`** — wrap the per-tier coverage `<table>` in `<div className="overflow-x-auto">`. The table is 2-column and likely fits at 360, but the audit may show it overflows under longer field names. If T01-SUMMARY.md verdict for this surface at 360 is `pass`, skip the wrapper add — only act on `fixed-pending → T02` verdicts. Document the decision in T02-SUMMARY.md.

## Constraints

- Do NOT touch other admin tables — UserManagement, PartsCuration scan-diff, and ExtractionHealth failure-rate are already wrapped (verdict from T01 should confirm this).
- Do NOT change column widths, row heights, or font sizes — wrapper-only fix.
- Do NOT add new tokens or design system primitives — `overflow-x-auto` is a Tailwind utility, no semantic-token impact.
- Run `npm --prefix frontend run type-check && npm --prefix frontend run lint` after the edit; both must remain green.

## Files Likely Touched

Only the two files named above.
  - Files: `frontend/src/pages/admin/CrawlerAdmin.tsx`, `frontend/src/pages/admin/ExtractionHealth.tsx`, `.gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md`
  - Verify: rg -q 'overflow-x-auto' frontend/src/pages/admin/CrawlerAdmin.tsx && (npm --prefix frontend run type-check) && (npm --prefix frontend run lint)

- [x] **T03: Collapse ViewPart price blocks into one 'Price by retailer' table + harden retailer outbound links with rel/icon affordance** `est:3h`
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
  - Files: `frontend/src/pages/builder/ViewPart.tsx`, `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`, `frontend/e2e/price-history.spec.ts`, `frontend/src/pages/admin/PartsCuration.tsx`, `.gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md`
  - Verify: rg -q 'Price by retailer' frontend/src/pages/builder/ViewPart.tsx && ! rg -q 'price-summary-stat-strip|retailer-breakdown-flat|RetailerBreakdownRow|PriceSummaryBlock' frontend/src/pages/builder/ViewPart.tsx && rg -q 'noopener noreferrer' frontend/src/pages/admin/PartsCuration.tsx && (npm --prefix frontend run type-check) && (npm --prefix frontend test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx)

- [x] **T04: Close gauntlet: 3 grep gates + retailer-link cross-check + type-check + lint + vitest + build + Playwright with reviewed snapshot refresh** `est:1h`
  Slice-level close gauntlet. Run linearly — fix any failure before continuing.

## Sequential checks (all must pass)

1. **Grep gate 1 — raw palette (S01 carry-forward):** `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]|text-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit code 1 (zero hits) is the pass condition.
2. **Grep gate 2 — glass-* (S02 carry-forward):** `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1.
3. **Grep gate 3 — `var(--*)` legacy (S02 carry-forward):** `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1.
4. **Grep gate 4 — retailer outbound link cross-check (NEW for S03):** Verify ViewPart's collapsed block + PartsCuration outbound link both carry `rel="noopener noreferrer"`. Run `rg -l 'target="_blank"' frontend/src/pages/builder/ViewPart.tsx frontend/src/pages/admin/PartsCuration.tsx` then for each file confirm `rg -q 'rel="noopener noreferrer"' <file>` returns exit 0. This is informational — non-retailer outbound links elsewhere with `rel="noreferrer"` alone (Footer, Header, PrivacyPolicy, Support, etc.) are out of scope and stay as-is.
5. **Type-check:** `npm --prefix frontend run type-check` → exit 0.
6. **Lint:** `npm --prefix frontend run lint` → exit 0 with zero net-new errors over the MEM062 baseline of 108 in slice-touched files.
7. **Vitest:** `npm --prefix frontend test -- --run` → exit 0; the rewritten 5 tests in `ViewPart.priceSummary.test.tsx` must all pass.
8. **Build:** `npm --prefix frontend run build` → exit 0.
9. **Playwright with snapshot refresh:** `cd frontend && npx playwright test --update-snapshots e2e/price-history.spec.ts`. Then run `git status --short frontend/e2e/price-history.spec.ts-snapshots/` and review every refreshed PNG visually before staging. Per MEM156 / MEM160, `--update-snapshots` defaults to `changed` mode in Playwright 1.59+ — only PNGs that actually differ rewrite. Expect 3 PNGs to change (`-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-{mobile,tablet,desktop}-linux.png`); if more drift than expected, investigate before continuing.
10. **Final Playwright re-run without `--update-snapshots`:** `cd frontend && npx playwright test` → exit 0 confirms baselines are stable post-refresh.

## Output

Write `.gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md` with: each check's exit code + duration, refreshed-PNG list with reviewed-OK note per file, lint-baseline confirmation, and any deviation observed.

## Manual visual spot-check

Skip under autonomous mode (per S02 precedent) — the 9 mechanical gates above are the slice's strongest objective signals. Coverage gap noted in slice summary.
  - Files: `.gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md`
  - Verify: test -f .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md && grep -q 'all green\|all pass\|exit 0' .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md

## Files Likely Touched

- frontend/src/pages/admin/UserManagement.tsx
- frontend/src/pages/admin/CrawlerAdmin.tsx
- frontend/src/pages/admin/ExtractionHealth.tsx
- frontend/src/pages/admin/PartsCuration.tsx
- frontend/src/components/parts/PartList.tsx
- frontend/src/components/buildListParts/BuildListPartList.tsx
- frontend/src/pages/parts/PartsCatalog.tsx
- frontend/src/pages/buildLists/BuildListsCatalog.tsx
- frontend/src/pages/Search.tsx
- .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
- .gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md
- frontend/src/pages/builder/ViewPart.tsx
- frontend/src/pages/builder/ViewPart.priceSummary.test.tsx
- frontend/e2e/price-history.spec.ts
- .gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md
- .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md
