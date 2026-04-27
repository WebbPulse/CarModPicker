# S03 Research — Responsive audit + ViewPart IA collapse + outbound link safety

## Summary

S03 is a **targeted** slice (known stack, known patterns from M002, in-place refactor) with one **deep unknown**: how aggressively to collapse the ViewPart price blocks while preserving outbound link information. The core work splits into three independent task tracks:

1. **Cross-class responsive audit + targeted overflow fixes** at 360 / 768 / 1280 (R054 + R055 + R056). 4 `<table>` admin surfaces + 2 `ResponsiveTableWrapper` consumers (PartList, BuildListPartList) + 2 raw card-grid surfaces (BuildListsCatalog, Search). Card-grid surfaces already use Tailwind responsive grid — the audit confirms with realistic densest data; admin tables need overflow-wrapper repair on at least 2 of the 4.
2. **ViewPart IA collapse** (R057). In-place refactor of `frontend/src/pages/builder/ViewPart.tsx` lines 752-871. Collapse `PriceSummaryBlock` (lines 126-199, retailer breakdown over `RetailerPriceBreakdown`) + the listings-driven "Price by retailer" block (lines 781-871) into ONE table that joins `priceSummary.retailers[]` (last/min/max/observation_count/last_observed_at) + `priceSummary.history[]` (per-retailer Sparkline source) + `listingsData[]` (product_url for outbound link).
3. **Outbound link safety + Lucide affordance** (R058). Touches every existing outbound retailer link AND the new collapsed block. Existing audit: `target="_blank"` appears at 14 sites in `frontend/src/`; only the **collapsed** ViewPart block + PartsCuration.tsx admin link consume retailer URLs and need the `noopener noreferrer` + `<ExternalLink />` affordance.

The data substrate already supports the IA collapse — no new API needed. The only "research" worth flagging: per-retailer mini-sparkline data is derived client-side by `history.filter(h => h.retailer_id === retailerId)`. This is a free derivation; the existing `Sparkline` component already accepts `PartPriceHistoryReadWithRetailer[]`.

The slice is **risk:high** in the roadmap, but the risk is concentrated: ViewPart's existing test surface (`ViewPart.priceSummary.test.tsx`) asserts on testids that this slice intentionally removes (`price-summary-stat-strip`, `retailer-breakdown-flat`, tablist for >3 retailers). The collapse changes 5 of 5 tests in that file. Plan must call this out so executor doesn't dodge by keeping the old testids alive.

## Recommendation

Order tasks **audit-first, IA-collapse-second, link-safety-third**, then close gauntlet:

1. **T01 — Responsive audit pass** (read-only): Visit each surface at 360 / 768 / 1280 with realistic densest data; record per-viewport verdict (`pass` / `fixed-pending` / `acceptable-as-scroll`). Output a verdict table that T02–T04 act on. *No code changes in this task.*
2. **T02 — Admin table overflow repair**: Add `overflow-x-auto` wrapper where missing (CrawlerAdmin rate-limit table line 322, ExtractionHealth per-tier coverage table line 203 inside the per-tier card). UserManagement + ExtractionHealth failure-rate + PartsCuration already wrap correctly — verdict only. **This is the only mechanical "fix" expected from the audit**; the dense card-grid surfaces are already responsive (S01/S02 didn't regress them).
3. **T03 — ViewPart IA collapse + outbound link safety**: Single in-place refactor. Replace `PriceSummaryBlock` + listings block with one collapsed table. Compress summary stats to a one-line header (`$min–$max across N retailers, last observed Z`). Use `<ExternalLink className="h-3 w-3" />` from `lucide-react` next to each `View at retailer` link. Update the 5 tests in `ViewPart.priceSummary.test.tsx` to assert on the collapsed shape. PartsCuration line 96 fix-up (`rel="noreferrer"` → `rel="noopener noreferrer"`) folds in here as a one-liner.
4. **T04 — Close gauntlet**: 8 sequential checks per S02 pattern (3 grep gates from S01/S02 still green + type-check + lint + vitest + build + Playwright with `--update-snapshots` for affected specs reviewed before commit). New grep gate to add: `rg 'target="_blank"' frontend/src/` × `rg -L 'rel="noopener noreferrer"'` cross-check on retailer-link consumer files (informational; not a hard exit-1 gate, since the project has many non-retailer outbound links that are fine with `rel="noreferrer"` alone).

This ordering keeps the audit's findings as a static input to T02/T03 (no thrash), and lets the IA collapse run as one atomic refactor (cleaner diff than splitting collapse and link-safety).

## Implementation Landscape

### Files definitely touched (T03 IA collapse)

- `frontend/src/pages/builder/ViewPart.tsx` (979 lines) — the in-place refactor target. Lines 88-199 (`trendArrow`, `RetailerBreakdownRow`, `PriceSummaryBlock`) **deleted/replaced**. Lines 752-871 (the two sibling blocks under `Card`) **collapsed into one**. The collapsed block consumes `priceSummary.retailers[]`, `priceSummary.history[]`, and `listingsData[]` joined by `retailer_id`. The "From: $X" CardInfoItem at lines 675-685 stays (it's a different IA layer — header-level "from price").
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` (327 lines, 5 tests) — every test asserts on testids that go away (`price-summary-stat-strip`, `retailer-breakdown-flat`, tablist for >3 retailers). Tests rewrite onto the collapsed contract: assert on the joined retailer row (last_cents + sparkline svg + observation_count + outbound link href + external-link icon), not on the now-deleted summary strip. Stale-caveat tests (lines 274-326) survive almost as-is since the listing layer (last_price_updated_at) is preserved.
- `frontend/src/pages/builder/ViewPart.test.tsx` — review for any incidental references; mostly auth/permission flows, low risk.
- `frontend/src/pages/admin/PartsCuration.tsx:97` — one-line `rel="noreferrer"` → `rel="noopener noreferrer"`.

### Files definitely touched (T02 overflow repair)

- `frontend/src/pages/admin/CrawlerAdmin.tsx:321-380` — rate-limit results table. Wrap `<table>` in `<div className="overflow-x-auto">` (or apply to existing `rounded border` wrapper). 5-column dense numeric layout at 360px = page-level h-scroll today.
- `frontend/src/pages/admin/ExtractionHealth.tsx:203-230` — per-tier coverage table (2-column, fits in 360 already because it's narrow) — verdict only, **probably no fix**. Confirm at audit.

### Files audited (T01, no changes expected)

- `frontend/src/components/parts/PartList.tsx` (1037 lines) — already uses `useResponsiveColumns` + `ResponsiveTableWrapper`; the price column is **pinned** (priority 1, never drops), with min-width 100px and `whitespace-nowrap` on the cell (line 822). Sparkline width is 60px, `flex-col` text + sparkline gap-2 = ~80px content + padding ≈ 96px effective, well under 100px min. **Reported `/parts` overflow is likely about the 1280-desktop case where the sidebar (`lg:w-64`) + container caps push effective width below the actions/rating cumulative min-width** — see MEM112 (Playwright sets viewport to 2400×900 to keep `actions` column visible). The audit confirms the price column itself doesn't overflow at any of the three Playwright viewports; what users see at 360 (mobile) is columns dropping cleanly via priority logic. If a real overflow surfaces in the audit, the fix is either bumping `COLUMN_MIN_WIDTH.price` to 110-120 (sparkline + delta line + price tag at fonts/locale extremes) OR clamping the sparkline width with `flex-shrink-0`.
- `frontend/src/components/buildListParts/BuildListPartList.tsx` (792 lines) — already uses `useResponsiveColumns`. Verdict-only. Containing page is `/build-lists/:id`.
- `frontend/src/pages/parts/PartsCatalog.tsx` (164 lines) — page chrome around `<PartList layout="table">`. No overflow risk in the page itself; sidebar at `lg:flex-row` collapses to stacked at <lg.
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx` (660 lines) — uses `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4` (line 625) for `<BuildListCard />`. Standard responsive grid; verdict-only.
- `frontend/src/pages/Search.tsx` (525 lines) — `<PartList layout="table" />` (line 464) for parts; `tile-grid-compact` (CSS class, defined in tokens.css) for users + build lists. Verdict-only.
- `frontend/src/pages/admin/UserManagement.tsx:346-484` — 11-column user-management table inside `overflow-x-auto`. Acceptable-as-scroll verdict.
- `frontend/src/pages/admin/PartsCuration.tsx:697-746` — scan-diff table inside `overflow-x-auto`. Acceptable-as-scroll verdict.
- `frontend/src/pages/admin/ExtractionHealth.tsx:248-285` — failure-rate table inside `overflow-x-auto`. Acceptable-as-scroll verdict.

### Visual-regression baselines that will refresh (T03/T04)

Per MEM148 + R060: maximum coverage. Playwright projects: `mobile` (375×667), `tablet` (768×1024), `desktop` (1280×800).

- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-{mobile,tablet,desktop}-linux.png` — **definitely refresh**. The collapsed block IS the breakdown view; the heading "Price summary (90 days)" stays at line 543 of the spec (rename if heading text changes; spec assertion may need update).
- `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-{mobile,tablet,desktop}-linux.png` — **only if T02 changes ResponsiveTableWrapper or PartList** (audit-only; default is no refresh).
- `frontend/e2e/admin.spec.ts-snapshots/admin-{dashboard,extraction-health}-1-{mobile,tablet,desktop}-linux.png` — **refresh ExtractionHealth** if T02 wraps the per-tier coverage table; CrawlerAdmin has no current snapshot.
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-{...}-linux.png` — kitchen-sink doesn't render ViewPart or admin tables; **no refresh expected**.

### Critical e2e behavior to preserve

- `frontend/e2e/price-history.spec.ts:533-557` — the existing test asserts:
  - `getByRole('heading', { name: 'Price summary (90 days)' })` is visible. **Decision needed**: keep the heading "Price summary (90 days)" on the collapsed block, OR rename to "Price by retailer" (the canonical name from MEM150 / R057) and update the spec. The locked decision in MEM150 is "ONE 'Price by retailer' table" — heading should be **"Price by retailer"** and the spec line 543 must change.
  - Stale-caveat assertion `(as of ${STALE_LISTING_LOCAL_DATE})` survives — the collapsed block must preserve `STALE_LISTING_THRESHOLD_DAYS` logic (lines 815-822 in current ViewPart) on each retailer row.
  - `staleCaveat` count is exactly 1. The collapsed block must not duplicate this caveat across the per-retailer breakdown vs the listings rows; with the collapse, there's only one source of truth (listings joined into the collapsed table).

### IA collapse contract (locked)

Single block titled **"Price by retailer"** under `Card`. One row per retailer. Columns:

| Retailer | Sparkline | Last price | Observed | Link |
|---|---|---|---|---|
| `retailer.retailer_name` | `<Sparkline history={historyForRetailer} width={80} height={24} />` | `formatCents(retailer.last_cents)` + delta arrow | relative time of `last_observed_at` (existing `STALE_LISTING_THRESHOLD_DAYS=60` triggers `as of` warning) | `<a href={listing.product_url} target="_blank" rel="noopener noreferrer">View <ExternalLink className="h-3 w-3 inline" /></a>` |

Above the table, optional one-line header: `$min – $max across N retailers, last observed {trend arrow} Z`. Use the existing `priceSummary.summary` for the aggregate. Drop the 4-column `min/max/last/trend` stat strip (currently `data-testid="price-summary-stat-strip"`) and the Tabs-when->3-retailers pattern entirely — the collapsed table replaces both.

If `priceSummary.observation_count === 0` AND `listingsData.length === 0`: section header + empty-state copy "No retailer pricing observed yet." If history is present but listings array is empty: render rows from `priceSummary.retailers` with sparklines + last price + observation timing, but **no `View at retailer` link** (no `product_url` available). If a listing exists but no history: render row with no sparkline, just last_known_price_cents from listing.

### Joining `priceSummary.retailers` ↔ `listingsData` ↔ `priceSummary.history`

```
const historyByRetailer = new Map<string, PartPriceHistoryReadWithRetailer[]>();
for (const h of priceSummary?.history ?? []) {
  if (!historyByRetailer.has(h.retailer_id)) historyByRetailer.set(h.retailer_id, []);
  historyByRetailer.get(h.retailer_id)!.push(h);
}
const listingByRetailer = new Map<string, PartListingReadWithRetailer>();
for (const l of listingsData ?? []) {
  listingByRetailer.set(l.retailer_id, l); // last-write-wins; if multiple listings per retailer exist the join needs disambiguation
}
// Render row per retailer in priceSummary.retailers (canonical ordering: by last_cents asc, matching existing line 805 sort).
```

**Disambiguation gotcha:** `RetailerPriceBreakdown` has retailer_id as primary key. `PartListingReadWithRetailer` has retailer_id but the same retailer could theoretically have multiple listings (different SKUs/URLs). Today's data appears to be 1:1 in production, but the join must be deterministic — either pick the first listing per retailer ordered by id, or pick the cheapest by last_known_price_cents. Recommend cheapest, matches the existing line 805-812 sort.

## Don't Hand-Roll

- **External-link icon**: import `ExternalLink` from `lucide-react` (already a project dependency per MEM060). Don't draw an SVG inline. Sizes: `h-3 w-3` for inline-with-text, `h-4 w-4` for standalone. Add `aria-hidden="true"` since the link text "View at retailer" already conveys the action.
- **Sparkline**: reuse `frontend/src/components/charts/Sparkline.tsx` directly — accepts `history: PartPriceHistoryReadWithRetailer[]`, internally sorts by `observed_at`, handles 0/1/multi observations, uses `hsl(var(--primary))`. No new chart component.
- **Stale logic**: reuse the existing `STALE_LISTING_THRESHOLD_DAYS = 60` constant + per-listing `last_price_updated_at` comparison from lines 814-822. No new threshold.
- **Cents formatting**: reuse the existing `formatCents` helper (line 83) — a `null` guard with `'—'` fallback. The existing pattern at lines 678-684 (`(part.best_price_cents / 100).toLocaleString(...)` for the "From:" header) is fine for that header; the collapsed block uses `formatCents`.
- **Responsive table**: do NOT wire up `useResponsiveColumns` for the collapsed block. The collapsed table has 5 columns max with low minimum widths; standard mobile-first stacking via `flex flex-wrap` + `md:grid` mirrors the existing line 823-825 row pattern. Reaching for the responsive-priority machinery here is over-engineering for a non-paginated, typically-≤5-row table.

## Pitfalls

- **`<table>` regex blindspot.** During audit-only phase: `rg '<table'` returned no matches in this session (escaping artifact in some grep tools). Always cross-check with `</table>` or `<thead>` / `<tbody>` to enumerate real `<table>` surfaces. The 4 admin tables are: UserManagement (line 346), CrawlerAdmin (line 323), ExtractionHealth × 2 (line 203, line 248), PartsCuration (line 698). PartList + BuildListPartList render `<table>` *inside* ResponsiveTableWrapper.
- **Viewport mismatch (MEM170 just captured).** Roadmap says "360 / 768 / 1280"; Playwright config says **375 / 768 / 1280**. The mobile project at 375 is what `--update-snapshots` produces. Manual UAT at 360 is what humans verify in DevTools. S03 slice summary should record both numbers per-viewport.
- **MEM112 / MEM114 / MEM079 / MEM083 viewport gotchas** — these are fixed-cost knowns that re-apply if any e2e test gets edited:
  - Playwright tests that need PartList action column visible must `setViewportSize({ width: 2400, height: 900 })` before goto.
  - SparklineCell rows in tablet/mobile horizontal scroll past the IO root — use `scrollIntoViewIfNeeded()` before assertions.
- **5-test rewrite in `ViewPart.priceSummary.test.tsx`.** Existing testids (`price-summary-stat-strip`, `retailer-breakdown-flat`) AND the >3-retailer Tabs assertion all become non-applicable after the collapse. The plan must rewrite all 5 tests onto the collapsed contract. Don't preserve the legacy testids "for compat" — that defeats the IA collapse.
- **PriceAlertSubscribeButton placement.** Currently sibling of the "Price summary (90 days)" SectionHeader (line 761). After the collapse, it must move to sibling of the new "Price by retailer" SectionHeader. Simple move; don't drop the button.
- **`isUserContributed` warning banner + `isDuplicateAdminView` admin banner** (lines 513-540) are unrelated to the IA collapse — don't touch.
- **`PriceHistoryLineChart`-style legacy line chart**: per MEM085, "/parts/:id detail still uses the legacy getPartPriceHistory line chart side-by-side with the new aggregation summary block". Cross-check ViewPart.tsx — the current file does NOT contain a separate line-chart import or usage; the only chart consumer is the per-row Sparkline (proposed for the collapsed block). MEM085 may describe a state that S03 (or earlier slices) eliminated; **flag during T01 audit** that no line-chart component is rendered today, and confirm S03 doesn't need to remove one.
- **PartsCuration external link.** Line 96 has `rel="noreferrer"` (missing `noopener`). Modern browsers infer noopener from noreferrer per HTML spec, so this is more defensive than essential — but R058 explicitly says `rel="noopener noreferrer"`. One-line fix.
- **Outbound link affordance breadth.** R058 is scoped to "outbound retailer links" — i.e. ViewPart's `View at retailer` + PartsCuration's product URL link. The 14 other `target="_blank"` consumers (Header GitHub link, Footer social links, PrivacyPolicy/Support/SocialLinks) are **out of scope** for S03; they're polish-pass material in S05. The plan should state this scope explicitly so executor doesn't over-reach.

## Sources

- `.gsd/REQUIREMENTS.md` R054 (admin tables), R055 (card-grids), R056 (no page-level h-scroll), R057 (ViewPart IA collapse), R058 (outbound link safety), R060 (per-slice baselines).
- `.gsd/milestones/M003/M003-CONTEXT.md` — In Scope (line 167-169), Acceptance Criteria S03 (lines 227-232).
- `.gsd/milestones/M003/slices/S02/S02-SUMMARY.md` — gauntlet pattern (3 grep gates + 5 quality gates + Playwright). Substrate confirmation: zero glass / zero `var(--*)` consumers in `frontend/src/`.
- `frontend/playwright.config.ts` — viewports `mobile=375×667`, `tablet=768×1024`, `desktop=1280×800`. `maxDiffPixelRatio: 0.002`.
- `frontend/e2e/price-history.spec.ts:533-557` — existing assertions on the ViewPart price-summary heading + stale caveat that the IA collapse must keep functionally green (via spec edit + baseline refresh).
- MEM150 (locked decision: aggressive collapse to ONE table), MEM151 (locked decision: `target="_blank" rel="noopener noreferrer"` + Lucide affordance), MEM146 (medium-impact IA on judgment, surface high-impact), MEM148 (per-slice maximum-coverage baseline refresh), MEM170 (viewport 360 vs 375 discrepancy), MEM171 (data substrate already sufficient), MEM172 (admin table overflow audit findings), MEM112 / MEM114 / MEM079 / MEM083 (Playwright responsive gotchas), MEM075 / MEM080 / MEM085 (Sparkline + per-row history pattern), MEM060 (lucide-react 1.x), MEM166 / MEM167 / MEM168 (S02 patterns inherited).

## Skills Discovered

None installed. The work is plain TS/React + Tailwind v4 + Radix primitives + Playwright (already a project dependency). No new framework or service.
