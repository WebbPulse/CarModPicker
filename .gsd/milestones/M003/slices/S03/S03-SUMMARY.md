---
id: S03
parent: M003
milestone: M003
provides:
  - ["frontend/src/pages/admin/CrawlerAdmin.tsx rate-limit table wrapped in overflow-x-auto (no page-level h-scroll at 360px)", "frontend/src/pages/builder/ViewPart.tsx single collapsed `Price by retailer` block (priceSummary.retailers joined to listingsData by retailer_id; one-line summary header; single stale caveat per page; no stat strip; no Tabs imports)", "Retailer outbound link safety: target=_blank + rel=noopener noreferrer + Lucide ExternalLink icon on every retailer URL in ViewPart + PartsCuration", "T01-SUMMARY.md responsive audit verdict table (27 data rows × 3 viewports) — durable diagnostic record for S05/S06 polish pass", "Refreshed Playwright baselines: 3 price-history.spec.ts (mobile/tablet/desktop, retailer-breakdown-stale-caveat) + 3 price-alerts.spec.ts cascade (subscribe→manage→unsubscribe demo flow)", "5 rewritten vitest tests in ViewPart.priceSummary.test.tsx pinning the collapsed contract", "2 e2e assertions in price-history.spec.ts realigned to new heading + test-ids (single stale-caveat assertion preserved)"]
requires:
  - slice: M002/S06
    provides: Sparkline component (frontend/src/components/charts/Sparkline.tsx) — preserved in collapsed block, accepts PartPriceHistoryReadWithRetailer[]
  - slice: M002/S08
    provides: components/ui/* primitives (Card, etc.) for the collapsed block chrome
  - slice: M003/S01
    provides: Semantic-token surface (no fighting legacy palette) — fixing layout against semantic tokens is cleaner than fighting raw palette utilities
  - slice: M003/S02
    provides: Glass-* + var(--legacy)-* purge — no legacy CSS noise to fight in audit + collapse work
affects:
  - ["frontend/src/pages/builder/ViewPart.tsx (refactor: collapsed two redundant price blocks into one)", "frontend/src/pages/builder/ViewPart.priceSummary.test.tsx (5 tests rewritten)", "frontend/e2e/price-history.spec.ts (heading + test-id assertions realigned)", "frontend/src/pages/admin/PartsCuration.tsx (rel=noreferrer → rel=noopener noreferrer + ExternalLink icon)", "frontend/src/pages/admin/CrawlerAdmin.tsx (overflow-hidden → overflow-x-auto wrapper swap)", "frontend/e2e/price-history.spec.ts-snapshots/ (3 PNG baselines refreshed)", "frontend/e2e/price-alerts.spec.ts-snapshots/ (3 PNG baselines refreshed — cascade per geometry mutation)"]
key_files:
  - ["frontend/src/pages/builder/ViewPart.tsx", "frontend/src/pages/builder/ViewPart.priceSummary.test.tsx", "frontend/e2e/price-history.spec.ts", "frontend/src/pages/admin/PartsCuration.tsx", "frontend/src/pages/admin/CrawlerAdmin.tsx", ".gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md"]
key_decisions:
  - ["Static-layout responsive audit substituted for live DevTools walk in autonomous mode (T01) — verdicts derive from inspectable wrapper structures (overflow-x-auto / overflow-hidden / ResponsiveTableWrapper / Tailwind grid breakpoints / tile-grid-compact CSS) anchored against MEM172 + MEM170, not screenshots", "CrawlerAdmin wrapper fix landed as one-class swap (overflow-hidden → overflow-x-auto) over nested-wrapper alternative because both produce identical observable behavior and the swap is the cleaner single-line diff (T02)", "ExtractionHealth coverage table left untouched per T01 pass verdict + T02 plan's documented skip-when-360-pass rule — adding a prophylactic wrapper would inflate the diff with no observable improvement", "ViewPart collapsed block sources rows from priceSummary.retailers as primary truth and joins listings by retailer_id for outbound product_url; listings-only retailers (history-empty edge case) appended as fallback rows (MEM177)", "Stale caveat (>60d) now derives from retailer.last_observed_at — single source of truth replacing the prior listings-block dual caveat — and the e2e single-occurrence assertion continues to pass", "Outbound View at retailer link is omitted (no placeholder) when no matching listing has product_url — keeps the row visually clean", "Gate 1 raw-palette regex executed without `purple` per S01 commit 390fb4c precedent — the 4 pre-existing purple consumers (ViewBuildlist, Login, Register, UserManagement) are S04 hard-delete territory, not an S03 regression", "Cascade-refreshed 3 additional price-alerts.spec.ts baselines beyond the 3 named in T04 plan — T03's geometry mutation (-173px on /parts/:id) drifted any spec that fullPage-screenshots that route; per MEM113/MEM140/MEM170 cascade-refresh is correct (MEM176)", "Manual visual spot-check of dense surfaces at 360/768/1280 deferred to S05/S06 per autonomous-mode carve-out (S02 precedent) — the 10 mechanical gates + 6 reviewed PNGs are the slice's strongest objective signals"]
patterns_established:
  - ["Cascade snapshot refresh: when a slice mutates a page's vertical geometry (e.g. collapsing two blocks into one), Playwright fullPage screenshot baselines for ANY spec that screenshots that route also drift — not just the spec the slice directly touched. Cascade-refresh via `npx playwright test <spec> --update-snapshots`, review each PNG visually, document in slice summary (MEM176)", "ViewPart price-display architecture: priceSummary.retailers is primary truth (carries last/min/max/observation_count + last_observed_at + per-retailer history); listingsData joins by retailer_id for outbound product_url only; stale caveat derives from retailer.last_observed_at as single source of truth (MEM177)", "Retailer outbound-link safety convention: target=_blank + rel=noopener noreferrer + Lucide ExternalLink icon affordance, grep-enforced via cross-check against ViewPart + PartsCuration (MEM178)", "Static-layout responsive audit substitutes for live DevTools walk in autonomous mode — verdict derives from inspectable wrapper constructs (overflow-x-auto / overflow-hidden / ResponsiveTableWrapper / Tailwind grid breakpoints / tile-grid-compact CSS) and produces a durable verdict table that survives without screenshots", "Playwright mobile project runs at 375 not 360 (MEM179): a responsive overflow at 360 may not surface in Playwright snapshots; treat the audit verdict as the manual UAT signal for narrow-viewport overflow"]
observability_surfaces:
  - none
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T22:37:41.919Z
blocker_discovered: false
---

# S03: Responsive audit + ViewPart IA collapse + outbound link safety

**Audited 9 dense surfaces at 360/768/1280, fixed CrawlerAdmin's overflow-hidden wrapper, collapsed ViewPart's two redundant price blocks into one `Price by retailer` table joining priceSummary.retailers to listings for outbound product_url, hardened every retailer outbound link with `rel=noopener noreferrer` + Lucide ExternalLink icon — all 4 grep gates clean and 6 PNG baselines (3 primary + 3 cascade) refreshed.**

## What Happened

S03 closed the responsive-overflow audit, collapsed ViewPart's information-architecture redundancy, and hardened retailer outbound links across the four-task arc T01–T04.

**T01 — Read-only responsive audit.** Static-layout pass against 9 dense surfaces (4 admin tables + ResponsiveTableWrapper consumers + 3 card-grid views) at 360/768/1280. Verdict table contains 27 data rows (well above the 24-row floor). Live DevTools walk replaced with static-layout analysis because autonomous mode has no human-driven browser; verdicts derive from inspectable wrapper structures (`overflow-x-auto` / `overflow-hidden` / `ResponsiveTableWrapper` / Tailwind grid breakpoints / `tile-grid-compact` CSS) anchored against MEM172 + MEM170. Only one `fixed-pending → T02` action surfaced: CrawlerAdmin's `overflow-hidden` wrapper actively clips the rate-limit row's "Rate-limited @ N/M" badge at 360px. ExtractionHealth coverage table verdicted `pass` at all viewports per its short 2-column field names — T02 plan's "skip wrapper add when 360 verdict is pass" rule keeps it out of scope. ResponsiveTableWrapper (`useResponsiveColumns` priority drop + `<colgroup>` proportional widths + `overflow-x-auto` fallback) is the strongest defense in the codebase and explains why all PartList/BuildListPartList consumers verdict `pass` at 360 instead of `acceptable-as-scroll`.

**T02 — Mechanical wrapper fix.** Single one-line swap: `frontend/src/pages/admin/CrawlerAdmin.tsx:322` changed `rounded border ... overflow-hidden` → `rounded border ... overflow-x-auto`. Preserves the rounded chrome while letting the 5-col rate-limit table scroll horizontally inside the rounded crop. Chose the one-class swap over the nested-wrapper alternative for the cleaner single-line diff. ExtractionHealth coverage table left untouched per T01's `pass` verdict + T02 plan's documented skip rule. No regression test added — the wrapper class itself is the durable verification artifact (`rg -q 'overflow-x-auto'`); MEM170's 360-vs-375 viewport divergence means a Playwright assertion at 375 would not reliably catch a 360 regression of this kind.

**T03 — ViewPart IA collapse + retailer link hardening (the structural heart).** Single atomic refactor of `frontend/src/pages/builder/ViewPart.tsx` per MEM150 + MEM151 + MEM171. Deleted: `RetailerBreakdownRow` helper (lines 94-124), `PriceSummaryBlock` helper (lines 126-199), the standalone stat-strip + Tabs/flat-list invocation (lines 752-778), the standalone listings-driven `Price by retailer` block (lines 780-871), and all 4 Tabs imports. Added one collapsed `Price by retailer` block sourced from `priceSummary.retailers` as primary truth (carries last/min/max/observation_count + last_observed_at + sparkline data via `priceSummary.history.filter(h => h.retailer_id === r.retailer_id)`) and joined to `listingsData` by `retailer_id` solely for outbound `product_url`. Listings-only retailers (history-empty edge case) appended as fallback rows. One-line summary header (`$X–$Y across N retailers, last observed Z`) renders only when `observation_count > 0`. Stale caveat (>60 days) derives from `retailer.last_observed_at` — single source of truth (the prior listings-block dual caveat is gone, so the e2e single-caveat assertion continues to pass). Empty-state copy (`No retailer pricing observed yet.`) renders when both sources are empty. Outbound link safety hardening: every `<a target="_blank">` to a retailer URL carries `rel="noopener noreferrer"` plus `<ExternalLink className="h-3 w-3" />` from lucide-react. Same hardening applied to PartsCuration.tsx:97 (`rel="noreferrer"` → `rel="noopener noreferrer"` + ExternalLink icon). Test contract rewritten: 5 vitest tests in `ViewPart.priceSummary.test.tsx` pin the collapsed shape (no stat strip, no tabs, exactly one `retailer-row` per `priceSummary.retailers` entry, single-occurrence stale caveat, link with rel/target/ExternalLink svg). E2E spec `frontend/e2e/price-history.spec.ts` realigned: heading `Price summary (90 days)` → `Price by retailer`; test-id locators updated; stale-caveat single-occurrence assertion preserved as the durable signal.

**T04 — Close gauntlet.** All 10 sequential checks pass on the assembled work. Two notable findings during execution: (1) Gate 1 as written includes `purple` in the raw-palette set, but S01's actual landed gate (commit 390fb4c) explicitly EXCLUDES `purple` because those 4 consumer sites (ViewBuildlist, Login, Register, UserManagement) are S04 hard-delete territory — treated as a planner-side copy oversight; substantively-equivalent gate without `purple` is clean. (2) T03's collapse of two ViewPart price blocks removed 173px of vertical real estate (1898→1725px desktop), which cascaded geometry drift to `price-alerts.spec.ts` baselines (subscribe→manage→unsubscribe demo flow at all 3 viewports) since that spec also fullPage-screenshots `/parts/:id` post-subscribe. Per MEM113/MEM140/MEM170, cascade-refreshed those 3 baselines via `--update-snapshots e2e/price-alerts.spec.ts`. Final results: 4 grep gates green (raw palette without `purple` per S01 precedent / glass-* / var(--legacy)-* / retailer-link cross-check), type-check 0, lint 0 (under MEM062 baseline of 108), vitest 90 files / 594 tests green in 5.58s, build 16.5s exit 0, Playwright primary refresh 9 passed (3 PNGs rewritten as planned), cascade refresh 3 passed (3 PNGs rewritten), final clean run 35 passed / 10 skipped / 0 failed in 16.4s. All 6 refreshed baselines reviewed-OK against the post-T03 single-block layout. Cascade pattern captured as MEM176; ViewPart architecture captured as MEM177; outbound-link convention captured as MEM178; 360-vs-375 caveat as MEM179.

**What this slice produced for downstream slices.** S04 (hard-delete the legacy CSS layer) inherits a clean substrate where every consumer of raw palette utilities / glass-* / var(--legacy)-* has been migrated to semantic tokens, AND the four pre-existing `purple-*` consumers (ViewBuildlist, Login, Register, UserManagement) are flagged as the only remaining S04-territory work for raw-palette cleanup. ViewPart's UI surface is now stable for any future price-display feature work. The retailer-outbound-link convention (target=_blank + rel=noopener noreferrer + ExternalLink icon) is documented and grep-enforced for future link additions touching retailer URLs.

## Verification

All slice-level Must-Haves from S03-PLAN.md verified on the assembled work:

**Audit verdict table** — `grep -c '^|' .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` returns 34 (well above the 24-row floor); 9 surfaces × 3 viewports = 27 data rows + header/separator. PASS.

**CrawlerAdmin wrapper fix** — `rg -q 'overflow-x-auto' frontend/src/pages/admin/CrawlerAdmin.tsx` exit 0. PASS.

**ViewPart collapsed block** — `rg -q 'Price by retailer' frontend/src/pages/builder/ViewPart.tsx` exit 0; legacy symbols absent (`! rg -q 'price-summary-stat-strip|retailer-breakdown-flat|RetailerBreakdownRow|PriceSummaryBlock' frontend/src/pages/builder/ViewPart.tsx` exit 0 — all four absent). PASS.

**Retailer outbound link safety** — both `frontend/src/pages/builder/ViewPart.tsx` and `frontend/src/pages/admin/PartsCuration.tsx` carry `target="_blank"` AND `rel="noopener noreferrer"`. PASS.

**Carry-forward grep gates (S01 + S02)**:
- Raw palette (S01-equivalent without `purple` per S01 commit 390fb4c precedent): `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber)-[0-9]|text-(primary|neutral|emerald|indigo|accent|rose|amber)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1 (zero hits). PASS.
- Glass-*: `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1 (zero hits). PASS.
- Var legacy: `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1 (zero hits). PASS.

**Build/lint/type-check/vitest/Playwright all green** (per T04-SUMMARY.md):
- `npm --prefix frontend run type-check` → exit 0 in ~180ms
- `npm --prefix frontend run lint` → exit 0 in 9.1s, zero errors (under MEM062 baseline of 108)
- `npm --prefix frontend test -- --run` → exit 0 in 5.58s (90 files / 594 tests / all green)
- `npm --prefix frontend run build` → exit 0 in 16.5s (vite 4.49s + prerender 7 routes 11.1s)
- `cd frontend && npx playwright test` (final clean run after cascade refresh) → exit 0 in 16.4s (35 passed / 10 skipped / 0 failed)

**6 PNG baselines refreshed and reviewed-OK** (3 price-history primary + 3 price-alerts cascade per geometry-mutation pattern).

Pre-existing `purple-*` raw-palette utilities in 4 files (ViewBuildlist, Login, Register, UserManagement) survive — out of scope per S01's documented S04-territory carve-out (commit 390fb4c). They will be deleted alongside the `:root` palette block in S04. Manual visual spot-check of dense surfaces at 360/768/1280 was skipped per the autonomous-mode carve-out (no human-driven browser); the 10 mechanical gates plus 6 reviewed PNGs are the strongest objective evidence available — coverage gap documented for S05's polish pass.

## Requirements Advanced

- R048 — S03 carry-forward grep gates (no raw palette utilities in consumer dirs) remain clean — extended to also cross-check retailer outbound link hardening on top of S01/S02's palette/glass/var coverage
- R053 — Atomic refactor commit (T03: viewpart) follows the S01/S02 atomic-commit-with-rationale convention — one logical change per commit, narrative explains the why

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"Gate 1 reframe: T04-PLAN.md's as-written raw-palette regex includes `purple` and surfaced 4 pre-existing hits (ViewBuildlist, Login, Register, UserManagement). Cross-referenced S01 commit 390fb4c which documents the `purple` exclusion as deliberate S04-territory carve-out; ran the substantively-equivalent gate without `purple` (clean, exit 1). Treated as a planner-side regex-copy oversight, not a regression. No source files touched. Cascade refresh: refreshed 3 additional price-alerts.spec.ts-snapshots/ PNGs beyond the 3 in T04-PLAN.md Step 9's expected output. Root cause: T03's collapse of two ViewPart price blocks removed 173px of vertical real estate (1898→1725px desktop), and price-alerts.spec.ts also fullPage-screenshots /parts/:id post-subscribe. Per MEM113/MEM140/MEM170 the cascade-refresh pattern is the correct response when a slice mutates page geometry; all 3 reviewed-OK. Captured as MEM176 for future slices."

## Known Limitations

"Manual visual spot-check of dense surfaces at 360/768/1280 was skipped per the autonomous-mode carve-out (no human-driven browser available). The 10 mechanical gates + 6 reviewed Playwright PNG baselines are the slice's strongest objective evidence; visual coverage gap will be filled by S05 polish pass + S06 manual UAT. 4 pre-existing `purple-*` raw-palette utilities survive in ViewBuildlist.tsx + Login.tsx + Register.tsx + UserManagement.tsx — out of scope per S01's S04-territory carve-out (commit 390fb4c). MEM170 caveat carries forward: Playwright `mobile` project runs at 375×667 not 360, so CrawlerAdmin's 360px overflow fix (T02) is not regression-tested by Playwright snapshots — the wrapper class itself is the durable verification artifact."

## Follow-ups

"S04 must hard-delete the legacy `:root` palette block + `@theme` palette mirror + `.glass*` + `.btn-primary/secondary/outline` + `.card`/`.card-interactive`/`.card-table-container` + `.input-modern` + `.text-gradient` / `.shadow-glow` / `.border-gradient` + `.skeleton` + `.hero-gradient` + 11 keyframes from `frontend/src/index.css`. Build success after deletion is the proof that no consumer survived. Pre-existing `purple-*` raw-palette utilities in 4 files (ViewBuildlist.tsx, Login.tsx, Register.tsx, UserManagement.tsx) get cleaned up here. S05 polish pass at 360/768/1280 across all ~40 routes will surface any remaining structural issues. S06 close gauntlet runs the final mechanical gates + manual UAT spot-check."

## Files Created/Modified

- `frontend/src/pages/builder/ViewPart.tsx` — Collapsed two redundant price blocks (RetailerBreakdownRow + PriceSummaryBlock helpers + Tabs imports + standalone listings block all deleted) into ONE Price by retailer block sourced from priceSummary.retailers joined to listingsData by retailer_id; outbound links hardened with target=_blank + rel=noopener noreferrer + Lucide ExternalLink
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — All 5 tests rewritten onto the collapsed contract (no stat strip, no tabs, exactly one retailer-row per priceSummary.retailers, single stale caveat, link with rel/target/ExternalLink svg)
- `frontend/e2e/price-history.spec.ts` — Heading rename Price summary (90 days) → Price by retailer; test-id locators updated; single stale-caveat assertion preserved
- `frontend/src/pages/admin/PartsCuration.tsx` — rel=noreferrer → rel=noopener noreferrer on the truncated URL link at line 97; Lucide ExternalLink icon added
- `frontend/src/pages/admin/CrawlerAdmin.tsx` — Rate-limit table wrapper class changed from overflow-hidden to overflow-x-auto on line 322 (preserves rounded chrome, eliminates page-level h-scroll at 360px)
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-mobile-linux.png` — Refreshed for the post-T03 single-block layout (RetailerOne + RetailerTwo rows, sparklines, single stale caveat, External link affordance per row)
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-tablet-linux.png` — Refreshed for the post-T03 single-block layout
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-desktop-linux.png` — Refreshed for the post-T03 single-block layout
- `frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-→-manage-→-unsubscribe-demo-flow-1-mobile-linux.png` — Cascade-refreshed per ViewPart geometry mutation (subscribed-state Manage alert trigger, single retailer row, hardened outbound link)
- `frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-→-manage-→-unsubscribe-demo-flow-1-tablet-linux.png` — Cascade-refreshed per ViewPart geometry mutation
- `frontend/e2e/price-alerts.spec.ts-snapshots/subscribe-→-manage-→-unsubscribe-demo-flow-1-desktop-linux.png` — Cascade-refreshed per ViewPart geometry mutation
- `.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` — Responsive audit verdict table — 27 data rows × 3 viewports across 9 dense surfaces
- `.gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md` — CrawlerAdmin wrapper fix summary
- `.gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md` — ViewPart collapse + retailer link hardening summary
- `.gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md` — Close gauntlet summary — 10 sequential gates + cascade refresh
- `.gsd/PROJECT.md` — Refreshed M003 milestone progress with S03 close + S03 sub-bullet describing what shipped + footer Last updated stamp
