# M002: Data Enrichment + Frontend Design Reset

**Vision:** CarModPicker graduates from bare-catalog MVP to a structured, comparative, designed product. All 111 adapters conform to a new per-category Pydantic extraction pattern with a universal-field floor; price history becomes a first-class user surface (sparkline + detail view + drop alerts); and the entire frontend gets a coherent design-language reset on shadcn+Tailwind tokens, retiring the hand-rolled components/common/ across all ~20 pages.

## Success Criteria

- All 111 adapters compliant with new extraction pattern (T0+T1+T2 declare category targets and inherit base-class universal extraction)
- 30-50 of T0+T1 adapters surface meaningful structured fields where HTML cooperates
- Every part card with observations shows sparkline + price-delta line; per-part detail view shows retailer breakdowns and listing-level history
- Price-drop alerts subscription works end-to-end with email firing on threshold breach
- shadcn primitives committed under components/ui/ replace hand-rolled components/common/ across all ~20 pages
- Playwright screenshot tests green at three breakpoints for kitchen-sink + build-list view + parts catalog + admin
- Re-extraction backfill against S3 self-archive started (idempotent, resumable, can finish post-merge)
- Price-history list-endpoint p95 inside budget at 10x current traffic in load test
- Admin extraction-health view distinguishes compliance (binary, 111/111) from coverage (per-tier gradient)

## Slices

- [x] **S01: S01** `risk:high` `depends:[]`
  > After this: Run pytest backend/app/crawlers/ — universal-extractor fixture stubs and 3 category-schema contract tests pass. SpecRegistry.resolve('coilover') returns the CoiloverSpec model. Ingest accepts a valid spec block, ingests it; ingest rejects a malformed spec block, ingests the part with specifications=null, and increments extraction_failure_rate.

- [x] **S02: S02** `risk:high` `depends:[]`
  > After this: Run a CLI one-liner against 5 archived HTML samples drawn from 5 different adapters: each result's specifications dict is populated with universal fields at appropriate confidence levels. Verify suppression: an adapter declares suppress_universal=['weight'] and that field is not auto-extracted for that adapter.

- [x] **S03: S03** `risk:high` `depends:[]`
  > After this: Run python -m app.crawlers.compliance_audit. Output prints 111/111 compliant with per-tier breakdown (T0: 84/84, T1: 16/16, T2: 11/11). Each adapter declares at least one category_target. Spot-check 3 T0, 2 T1, 1 T2 adapter — verify category_targets attribute present and base-class universal extraction inherited.

- [x] **S04: S04** `risk:medium` `depends:[]`
  > After this: Kick off the backfill: python -m app.crawlers.backfill --batch-size 100. Job is idempotent (re-running on the same parts produces no duplicates), resumable (Ctrl-C and resume picks up where it left off), and logs progress with per-batch counts. Hit GET /api/admin/extraction-health — JSON returns compliance: 111/111, per-tier coverage gradient, per-adapter failure-rate over 7d window.

- [x] **S05: S05** `risk:medium` `depends:[]`
  > After this: Call GET /api/parts/{id}/price-history?window=90d — returns retailer breakdowns and listing-level history. Call POST /api/parts/price-history with [part_id_1..part_id_50] — returns min/max/last/trend per part. Run load test (k6 or locust) at 10x current traffic on current catalog size — p95 inside budget.

- [ ] **S06: Price-history frontend surfaces (sparkline + detail view)** `risk:medium` `depends:[S05,S08]`
  > After this: Visit /parts in dev — every part card with observations shows a sparkline + delta line. Click a card to drill into the per-part detail view — retailer breakdowns and listing-level history visible, with stale-observation 'as of' caveat where relevant. Inspect a part with zero observations: no sparkline rendered, just current price.

- [ ] **S07: Price-drop alerts (subscription, threshold, email)** `risk:medium` `depends:[S05,S06]`
  > After this: Subscribe to a part with threshold $X on the part detail page. Trigger an observation below threshold (via test endpoint or manual scrape replay). Email arrives with part details, current price, and unsubscribe link. Visit /account/alerts — subscription listed; click unsubscribe; subscription removed and confirmed by reloading.

- [ ] **S08: S08** `risk:high` `depends:[]`
  > After this: Open the kitchen-sink page in dev — every primitive (Button, Dialog, DropdownMenu, Combobox, Toast, Tabs, Input, Select, Sheet) renders in every state (default, hover, focus, disabled, loading, error) under the new tokens. Run npm run test:e2e — components.spec.ts kitchen-sink screenshots green at mobile/tablet/desktop. playwright.config.ts and frontend/e2e/smoke.spec.ts committed.

- [ ] **S09: Build-list view redesign** `risk:medium` `depends:[S08]`
  > After this: Visit /build-lists/{id} in dev — page is on the new design system, all interactions use S08 primitives. Run npm run test:e2e -- build-list.spec.ts — green at mobile/tablet/desktop. Tab through the page — focus indicators visible, escape on dialogs works.

- [ ] **S10: Parts catalog redesign** `risk:medium` `depends:[S08,S06]`
  > After this: Visit /parts in dev — page on new design system; each part card shows the S06 sparkline + delta where observations exist. Run npm run test:e2e -- parts-catalog.spec.ts — green at mobile/tablet/desktop. Tab through the page; keyboard nav works.

- [ ] **S11: Admin shell redesign + extraction-health UI** `risk:medium` `depends:[S08,S04]`
  > After this: Visit /admin in dev — shell on new design system. Click into Extraction Health — page shows 111/111 compliance, per-tier coverage gradient (T0/T1/T2 with field-presence heatmap), per-adapter failure rates over 7d window. Run npm run test:e2e -- admin.spec.ts — green at three breakpoints.

- [ ] **S12: Repo-wide ripple reskin** `risk:medium` `depends:[S08,S09,S10,S11]`
  > After this: Walk every page in dev — all on the new design system, all interactions use S08 primitives. Run npm run lint — passes. Run grep -r 'from .*components/common' frontend/src/ — returns nothing. components/common/ directory removed.

- [ ] **S13: Final integration + milestone verification** `risk:low` `depends:[S03,S04,S06,S07,S09,S10,S11,S12]`
  > After this: Pick a real coilover product URL. Run a live scrape. Observe in logs: universal extraction → category extraction → Pydantic validation → ingest → Part.specifications populated. Visit /parts and find the part — sparkline renders. Click into detail view — retailer breakdowns visible. Subscribe with threshold above current price; trigger observation; email arrives. Confirm backfill job running (admin extraction-health shows progress). Re-run S05 load test — p95 still inside budget.

## Boundary Map

### S01 → S02

Produces:
- backend/app/crawlers/specs/registry.py → SpecRegistry with resolve(category_id) → CategorySpec subclass
- backend/app/crawlers/specs/base.py → CategorySpec(BaseModel) with confidence-flag conventions
- backend/app/crawlers/specs/{coilover,brake,turbo}.py → 3+ initial category models
- backend/app/crawlers/base.py extension point → category_targets: list[str] class attribute on RetailerCrawlerAdapter
- backend/tests/crawlers/conftest.py + fixtures → S3-archived HTML test fixture infrastructure
- Ingest validation hook in part ingest path → drops invalid spec block, ingests part, increments extraction_failure_rate

Consumes: nothing (foundation)

### S02 → S03

Produces:
- backend/app/crawlers/parsing.py extensions → extract_weight, extract_material, extract_finish, extract_warranty, extract_fitment_notes (each returning value + confidence)
- RetailerCrawlerAdapter post-hook in base.py → auto-merges universal-field extraction into ScrapedPayload.specifications
- Suppression mechanism → adapters can opt out per field via class attribute

Consumes from S01:
- SpecRegistry, CategorySpec base — universal fields land alongside category-specific fields in same specifications dict.

### S03 → S04

Produces:
- All 111 adapter files in tier0_http/, tier1_tls/, browser-tier declare category_targets attribute
- backend/app/crawlers/compliance_audit.py → script-as-test, prints 111/111 with per-tier breakdown
- Per-tier coverage data structure (binary compliance + gradient field-presence)

Consumes from S01: SpecRegistry, category_targets convention.
Consumes from S02: base-class universal extraction (inherited automatically).

### S04 → S11

Produces:
- backend/app/api/endpoints/admin/extraction_health.py → GET /api/admin/extraction-health returns compliance + per-tier coverage + per-adapter failure rates
- backend/app/crawlers/backfill.py → idempotent, resumable backfill job over S3 crawl_html/by_url/
- CloudWatch EMF metric extraction_failure_rate per adapter

Consumes from S01: SpecRegistry, ingest validation.
Consumes from S02: universal extraction.
Consumes from S03: compliance audit data.

### S05 → S06, S07

Produces:
- backend/app/api/endpoints/parts.py → GET /api/parts/{id}/price-history (retailer + listing breakdowns, windowed)
- backend/app/api/endpoints/parts.py → POST /api/parts/price-history (batch min/max/last/trend for N part IDs)
- Aggregation logic in part_listing_service or new part_price_aggregation_service
- frontend/src/api/parts.ts → typed client functions for both endpoints

Consumes from existing: PartPriceHistory, PartListing, Retailer models (M001 schema).

### S06 → S10

Produces:
- frontend/src/components/charts/Sparkline.tsx → reusable sparkline component (zero/single/multi-observation rendering)
- frontend/src/components/parts/PriceDeltaLine.tsx → "$X → $Y over N days" formatting
- frontend/src/pages/PartDetail.tsx → per-part price-history detail view with retailer breakdowns

Consumes from S05: aggregation API client.
Consumes from S08: Tabs, Card, Tooltip primitives for detail view.

### S07 → (M002 close)

Produces:
- backend/app/api/models/part_price_alert.py → new SQLAlchemy model (user_id, part_id, threshold_cents, active, created_at)
- Alembic migration for part_price_alert
- backend/app/api/endpoints/part_price_alerts.py → CRUD endpoints
- backend/app/core/email_templates/price_drop_alert.html → React Email template
- Alert evaluation hook in part_listing_service observation-write path
- frontend subscription-management page

Consumes from S05: threshold-evaluation primitives.
Consumes from S08: form primitives for subscribe + management UI.
Consumes from existing: SES email path (core/email.py), user auth.

### S08 → S09, S10, S11, S12

Produces:
- frontend/src/styles/tokens.css → CSS variable tokens (color, spacing, type, radii, shadows) — dark palette locked
- frontend/src/components/ui/{button,dialog,dropdown-menu,combobox,toast,tabs,input,select,sheet}.tsx → 9+ Radix-based primitives
- frontend/src/pages/_KitchenSink.tsx → dev-only kitchen-sink page rendering every primitive in every state
- frontend/playwright.config.ts → committed
- frontend/e2e/components.spec.ts → kitchen-sink screenshot tests at three breakpoints
- frontend/e2e/smoke.spec.ts → committed (existing uncommitted file)

Consumes: nothing (design substrate).

### S09 → S12, S13

Produces:
- frontend/src/pages/BuildListDetail.tsx → reskinned build-list view consuming S08 primitives
- frontend/e2e/build-list.spec.ts → Playwright screenshot tests at three breakpoints

Consumes from S08: tokens, primitives.

### S10 → S12, S13

Produces:
- frontend/src/pages/PartsCatalog.tsx → reskinned with sparklines integrated into part cards (S06)
- frontend/e2e/parts-catalog.spec.ts → Playwright screenshot tests at three breakpoints

Consumes from S08: tokens, primitives.
Consumes from S06: Sparkline, PriceDeltaLine components.

### S11 → S12, S13

Produces:
- frontend/src/pages/AdminDashboard.tsx → reskinned admin shell on new system
- frontend/src/pages/admin/ExtractionHealth.tsx → consumes S04 admin endpoint
- frontend/e2e/admin.spec.ts → Playwright screenshot tests at three breakpoints

Consumes from S08: tokens, primitives.
Consumes from S04: extraction-health API.

### S12 → S13

Produces:
- All ~17 remaining pages reskinned on new component library
- Lint rule or grep CI check enforcing no imports from components/common/
- frontend/src/components/common/ removed or stubbed-as-deprecated

Consumes from S08: tokens, primitives.
Consumes from S09, S10, S11: established patterns from priority-page redesigns.

### S13 (final integration)

Consumes everything. Produces:
- E2E Playwright spec exercising the full live flow (real product → spec extraction → ingest → aggregation → UI → alert email)
- Updated milestone summary, validation, and verification artifacts.
