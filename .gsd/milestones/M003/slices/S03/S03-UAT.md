# S03: Responsive audit + ViewPart IA collapse + outbound link safety — UAT

**Milestone:** M003
**Written:** 2026-04-26T22:37:41.920Z

# S03 UAT — Responsive audit + ViewPart IA collapse + outbound link safety

**Scope.** Manual verification of the slice's three deliverables against the running stack: (1) the responsive audit verdict table is the diagnostic record (no manual UAT — already a static record), (2) CrawlerAdmin rate-limit table at 360px, and (3) ViewPart's collapsed `Price by retailer` block + retailer outbound link safety on a real `/parts/:id` page. UAT for this slice is OPTIONAL — slice closes against mechanical gates per the slice plan ("Human/UAT required: no — slice closes against mechanical gates; manual UAT happens at S06"). This script exists for operator spot-checking and is the seed for the M003 close-gauntlet UAT in S06.

## Preconditions

- Local stack running: `docker-compose up -d` (Postgres) + `uvicorn app.main:app --reload` (backend) + `npm --prefix frontend run dev` (frontend on port 4000).
- Sample data populated: `python scripts/populate_sample_data.py` from `backend/` if the local DB is empty (seeds parts with multiple retailers + price history + listings with `product_url`).
- Chrome browser with DevTools available; tester is authenticated (any verified user).
- A part ID with at least 2 retailers, observable price history within 90 days, and at least one stale (>60d) observation. The `MULTI_PART_ID` test fixture documented in T03-SUMMARY.md (RetailerOne fresh + RetailerTwo at 90d) is the canonical UAT target if running against test fixtures.

## Test Cases

### TC1 — CrawlerAdmin rate-limit table no longer overflows page at 360px

1. As an admin user, navigate to `/admin/crawlers`.
2. Open Chrome DevTools → Toggle device toolbar → set viewport to 360 × 800 (responsive mode, no device preset).
3. Scroll to the "Rate-limited adapters" section (the 5-col table with `adapter` / `rate-limit window` / `requests` / `last hit` / `next reset` columns).
4. **Expected:** The page itself does NOT scroll horizontally (no body-level h-scroll). The rate-limit table scrolls horizontally **inside** its rounded-border wrapper. The "Rate-limited @ N/M" badge in the adapter cell is still visible by scrolling the table horizontally; it does not push the page off-screen.
5. Resize to 768 (tablet) — the table may still scroll horizontally inside its wrapper; the page does not.
6. Resize to 1280 (desktop) — the table renders all 5 columns without horizontal scroll.

### TC2 — ViewPart shows ONE `Price by retailer` block (collapsed IA)

1. Navigate to `/parts/<MULTI_PART_ID>` (a part with at least 2 retailers + history + listings).
2. **Expected (visual structure check):** ONE section heading `Price by retailer` is present. Below it: a one-line summary header in muted gray text with the format `$X–$Y across N retailers, last observed [arrow] Z`. Below the header: a list (`<ul>`) with one row per retailer.
3. **Each row contains, in order:** retailer name, an inline sparkline (SVG, ~80×24), `formatCents(last_cents)` text, observation timing as `(N obs, last MM/DD/YYYY)`, and (when applicable) a `View at retailer` link.
4. **Crucially absent:** the prior 4-cell stat strip (`min` / `max` / `last` / `count`) is GONE. The `<TabsList>` for >3 retailers is GONE. The standalone listings-driven block under the heading is GONE. There is no duplicate stale caveat anywhere on the page — at most ONE `(as of ...)` warning span renders, and only if a retailer's `last_observed_at` is older than 60 days.
5. Open DevTools → Elements; confirm `data-testid="retailer-row"` count matches the number of unique retailers in `priceSummary.retailers`. Confirm `data-testid="price-summary-stat-strip"` is absent.

### TC3 — `View at retailer` link is safe and signals external navigation

1. On the same `/parts/<MULTI_PART_ID>` page from TC2, hover the `View at retailer` link in any retailer row that has a matching `listingsData` entry with `product_url`.
2. **Expected (DevTools Elements panel):** the `<a>` element has `target="_blank"`, `rel="noopener noreferrer"`, and contains a `<svg>` Lucide `ExternalLink` icon at the end (16px, `h-3 w-3`).
3. Click the link. **Expected:** opens in a new tab; the new tab cannot navigate the original tab via `window.opener` (verifiable in console of the new tab: `window.opener === null`).
4. Retailers with no matching listing or no `product_url` should render the row WITHOUT a `View at retailer` link (no placeholder, no broken `#` href).

### TC4 — Stale caveat appears EXACTLY ONCE on the page

1. Use a fixture or seeded part where one retailer's `last_observed_at` is older than 60 days (the `MULTI_PART_ID` fixture's `RetailerTwo` at 90 days is the canonical case).
2. **Expected:** the row for that retailer shows a `(as of MM/DD/YYYY)` warning span with `text-warning` styling. Other retailers' rows do not show the caveat.
3. Open DevTools → Elements → search the rendered DOM for `as of` (case-insensitive). **Expected:** exactly ONE match in the rendered DOM (single source of truth — the prior listings-block dual caveat is gone).

### TC5 — Empty-state when no retailer pricing observed

1. Navigate to a part with `priceSummary.observation_count === 0` AND `listingsData.length === 0` (a freshly inserted part with no price history and no listings).
2. **Expected:** the `Price by retailer` section heading renders. Below it, the empty-state copy `No retailer pricing observed yet.` renders. NO retailer rows render. NO summary header renders. NO stat strip or tabs.

### TC6 — PartsCuration outbound link hardening

1. As an admin user, navigate to `/admin/parts-curation` and view any scan-diff entry that includes a `crawled_pages.url` link.
2. Hover or right-click the truncated URL link.
3. **Expected:** the `<a>` element has `target="_blank"`, `rel="noopener noreferrer"` (NOT `rel="noreferrer"` alone), and a `<svg>` Lucide `ExternalLink` icon next to the truncated URL.

## Edge cases

- **History present, listings empty:** retailer rows render with sparklines + `last_cents` + observation timing, NO `View at retailer` link (no `product_url` available). Page does not error.
- **Listings present, history empty for a retailer:** that retailer's row renders without a sparkline, with `last_known_price_cents` from the listing as the displayed price. Stale caveat applies based on listing's last observation date.
- **Single retailer (no >3 trigger for tabs):** UI looks identical to the 2-retailer case — no tabs, no flat-list distinction. Single source of truth: the collapsed `<ul>`.
- **Single-page reflow at 360 viewport:** none of the dense tables (UserManagement, ExtractionHealth failure-rate, PartsCuration scan-diff) introduce page-level h-scroll — they all scroll inside their `overflow-x-auto` wrappers.

## Sign-off

When TC1–TC6 all pass and edge cases hold, S03 manual-UAT spot-check is complete. UAT is operator-optional for slice close — the slice's primary verification is the 10-step T04 mechanical gauntlet (already green per T04-SUMMARY.md). This UAT script feeds into S06's full close-gauntlet UAT.
