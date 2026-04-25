# S06: Price-history frontend surfaces (sparkline + detail view) — UAT

**Milestone:** M002
**Written:** 2026-04-25T22:03:46.897Z

# UAT — S06: Price-history frontend surfaces

This UAT validates the user-visible price-history loop end-to-end against the live backend and seeded sample data. S06's automated gate (vitest + Playwright with mocked API) is the objective bar; this script is the human-experience bar that travels with S13's milestone-verification flow.

## Preconditions

1. Backend running locally: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
2. Postgres up via `docker-compose up -d` (PostgreSQL 16) with at least one part that has 3+ price observations across 2+ retailers AND one part with zero observations. Seed via `python ../scripts/populate_sample_data.py` from `backend/`, then manually insert ≥3 `PartPriceHistory` rows for a chosen part if the sample doesn't already include them.
3. Frontend running: `cd frontend && npm run dev` on port 4000.
4. Logged in as any non-admin user.

## Test 1 — Catalog sparkline + delta line

**Steps**
1. Navigate to `/parts`.
2. Inspect the price column for a part you know has 3+ observations.
3. Inspect the price column for a part with zero observations.
4. Open browser devtools → Network → filter `price-history`.
5. Reload the page.

**Expected**
- Multi-observation card: shows the existing `$X.XX` best-price line, a `PriceDeltaLine` underneath rendering `↑`/`↓`/`·` + `$<min> → $<max>`, and a sparkline polyline to the right (table layout) or below (card layout).
- Zero-observation card: shows only the existing `$X.XX` best-price line — no sparkline, no delta line.
- Network panel shows exactly ONE `POST /api/parts/price-history` request for the entire page (regardless of how many cards are visible).
- Scroll a multi-observation card that is below the fold into view → exactly ONE `GET /api/parts/{id}/price-history?window=90d` fires for that part. Scroll past more multi-observation cards → one GET per part, only when scrolled into view.

## Test 2 — Detail view aggregation block

**Steps**
1. Click into a part with 3+ observations across 2+ retailers (e.g., the seed Bilstein B14 if present).
2. Scroll to the existing "Price history / Price by retailer" two-column grid.
3. Inspect the section directly above it.

**Expected**
- A new heading "Price summary (90 days)" appears above the legacy two-column grid.
- Below the heading: a 4-cell stat strip showing min / max / last / trend (with `↑`/`↓`/`·` glyph).
- A per-retailer breakdown:
  - If the part has ≤3 retailers, a flat list of retailer rows showing retailer_name, min, max, last, last_observed_at, observation_count.
  - If the part has >3 retailers, a Tabs primitive with one tab per retailer + an "All" tab.
- The legacy "Price history" line chart still renders unchanged below the new block.

## Test 3 — Stale "as of" caveat

**Steps**
1. On the same detail view, scroll to the listings list (under "Price by retailer").
2. Identify any listing whose `last_price_updated_at` is more than 60 days ago.

**Expected**
- The stale listing shows `(as of <localized date>)` in amber after the existing `updated <date>` text.
- Listings updated within the last 60 days show no caveat.

## Test 4 — Zero-observation detail view

**Steps**
1. Navigate to a part with zero observations (e.g., a freshly created part with no price-history rows).
2. Scroll the detail view.

**Expected**
- The "Price summary (90 days)" heading is absent.
- The legacy "Price history" line chart shows the existing empty state.
- No sparkline, no PriceDeltaLine, no per-retailer breakdown block.
- No console errors thrown.

## Test 5 — Failure surfaces

**Steps**
1. With devtools open, in the Network tab block `*/parts/price-history` (right-click → Block request URL).
2. Reload `/parts`.
3. Reload `/parts/{id}` for a multi-observation part.
4. Inspect the console.

**Expected**
- `/parts` still loads — every card renders the existing best-price cell unchanged. No broken cards, no React error boundary triggered. Console shows `[usePartPriceSummaries] <error>` warning(s).
- `/parts/{id}` still loads — the legacy line chart and listings list render. The new "Price summary" block is replaced by an inline "Price summary unavailable" message rather than throwing.
- Unblock the URL, reload — both surfaces recover automatically.

## Edge cases

- A part with exactly ONE observation: catalog card shows a single centered dot (no polyline), `PriceDeltaLine` shows `Tracked since <date>`, no fetch fires from SparklineCell beyond the parent batch.
- A retailer with zero observations on a part with multi-retailer history: that retailer is absent from the per-retailer breakdown (the API filters server-side).
- Resize the browser between mobile/tablet/desktop on `/parts`: layout switches between table and card automatically; both render sparklines + delta lines correctly. (Visual regression covered by Playwright at 375×667 / 768×1024 / 1280×800.)

## Sign-off criteria

- All 5 tests pass against live backend + seeded data.
- No console errors during normal use.
- Network panel confirms the batch endpoint is in use (one POST per catalog page).
- Stale-caveat math behaves correctly across DST and timezone changes (test from a non-UTC locale if possible).
