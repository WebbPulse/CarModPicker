# Requirements

This file is the explicit capability and coverage contract for the project.

## Validated

### R001 — Define a `SpecRegistry` plus base `CategorySpec(BaseModel)` and 3–5 initial concrete category models (e.g., `CoiloverSpec`, `BrakeSpec`, `TurboSpec`). Adapters declare which categories they target via class attribute; ingest validates `Part.specifications` against the resolved schema.
- Class: core-capability
- Status: validated
- Description: Define a `SpecRegistry` plus base `CategorySpec(BaseModel)` and 3–5 initial concrete category models (e.g., `CoiloverSpec`, `BrakeSpec`, `TurboSpec`). Adapters declare which categories they target via class attribute; ingest validates `Part.specifications` against the resolved schema.
- Why it matters: Schema contract that survives the M002→M003 boundary — extractor-agnostic so an LLM extractor can be dropped in later without restructuring. Errors surface at adapter boundary, not silently at ingest.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03
- Validation: M002/S01 ships SpecRegistry + CategorySpec base + 3 concrete models (CoiloverSpec, BrakeSpec, TurboSpec) under backend/app/crawlers/specs/. Adapters declare targets via category_targets ClassVar on RetailerCrawlerAdapter (validated at import time against default_registry). Ingest in app/crawlers/base.py.ingest_payload validates payload.specifications against the resolved schema. Verified by 23 contract+integration tests in backend/tests/crawlers/test_spec_registry_contract.py and test_ingest_spec_validation.py — all green; full crawler suite 1284 passed, 1 skipped.
- Notes: Spec module registration lives in __init__.py (keeps spec modules side-effect-free). Slugs (not category UUIDs) are the registry key — stable across envs. Confidence flags use paired X / X_confidence convention. Open question (deferred to S02): infer_category() returns DB category names ('suspension'), not registry slugs ('coilover') — bridge or re-key in S02.

### R002 — Shared utilities in `crawlers/parsing.py` extract universal fields (weight, material, finish, warranty, fitment notes) from product HTML. `RetailerCrawlerAdapter.parse_product_page` post-hook merges these into the `ScrapedPayload.specifications` dict for every adapter. Adapters can override or suppress per field.
- Class: core-capability
- Status: validated
- Description: Shared utilities in `crawlers/parsing.py` extract universal fields (weight, material, finish, warranty, fitment notes) from product HTML. `RetailerCrawlerAdapter.parse_product_page` post-hook merges these into the `ScrapedPayload.specifications` dict for every adapter. Adapters can override or suppress per field.
- Why it matters: Universal coverage across all 111 adapters without per-adapter retrofit. Iteration is cheap because the S3 self-archive lets us re-extract against stored HTML.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: M002/S02 shipped backend/app/crawlers/parsing.py extensions (extract_weight, extract_material, extract_finish, extract_warranty, extract_fitment_notes) plus the RetailerCrawlerAdapter post-hook that auto-merges universal-field extraction into ScrapedPayload.specifications; per-field suppression supported via class attribute. Verified live in M002/S13/T01 UAT walkthrough — backend logs surface `universal_extraction_extracted` lines during the live scrape, and M002/S13/T04's compliance audit (108/108) confirms every adapter inherits the base-class universal extractor. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt (108/108 compliance proves universal-extractor inheritance) plus existing S02 contract tests.
- Notes: Promoted at M002 close (2026-04-25). Live extraction-loop logs surfaced during T01 UAT operator walkthrough; backend compliance audit confirms every adapter inherits universal extraction.

### R003 — Every adapter in T0 (84), T1 (16), and T2 (11) declares its category-schema targets and inherits universal-field extraction via the base class. Compliance is binary and audited by `compliance_audit` script: 111/111.
- Class: core-capability
- Status: validated
- Description: Every adapter in T0 (84), T1 (16), and T2 (11) declares its category-schema targets and inherits universal-field extraction via the base class. Compliance is binary and audited by `compliance_audit` script: 111/111.
- Why it matters: Pattern compliance is uniform; coverage gradient is per-tier (T2 sparse until Cloudflare reliability lands in M003-adjacent work). Avoids two-tier code paths.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S04
- Validation: M002/S03 shipped backend/app/crawlers/compliance_audit.py and the category_targets contract on RetailerCrawlerAdapter. Re-verified live at M002 close: `cd backend && python -m app.crawlers.compliance_audit` exits 0 with `Total: 108/108 compliant — T0 (http) 83/83, T1 (tls) 15/15, T2 (browser) 10/10` (canonical 108 figure per MEM037/MEM122; the M002 vision text's '111 adapters' refers to 3 IS_FALLBACK GenericHtmlParser instances per tier excluded from the registry per D-03). Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt.
- Notes: Promoted at M002 close (2026-04-25). Vision text '111' reconciled to canonical 108/108 contract per MEM037/MEM122. Compliance binary; live audit green.

### R004 — When an adapter returns specs that fail Pydantic validation, ingest drops the spec block, ingests the part without specs, logs a structured warning, and increments a per-adapter `extraction_failure_rate` metric. Part ingest must never regress because category extraction is new.
- Class: failure-visibility
- Status: validated
- Description: When an adapter returns specs that fail Pydantic validation, ingest drops the spec block, ingests the part without specs, logs a structured warning, and increments a per-adapter `extraction_failure_rate` metric. Part ingest must never regress because category extraction is new.
- Why it matters: Extraction is new across all 111 adapters; silent regression of the existing ingest pipeline is the worst-case outcome.
- Source: inferred
- Primary owning slice: M002/S01
- Supporting slices: M002/S04
- Validation: M002/S01 wired ingest_payload to fail-soft on Pydantic ValidationError: drops the spec block (specifications=None), logs a structured WARN with adapter_name + inferred slug + e.errors()[:3], emits ExtractionFailureRate EMF metric (env-gated, same isolation pattern as emit_crawler_run_metrics — catch and log; never raise), and the Part still persists. Verified by 3 integration tests: test_invalid_specs_drop_to_none_and_part_persists, test_type_coercion_failure_drops_to_none, test_emit_extraction_failure_called_once_on_invalid_specs (caplog assertions lock in adapter_name + slug visibility). Pass-through cases (no spec block, no inferred slug, no model registered) keep all 108 legacy adapters working unchanged.
- Notes: Sensible-defaults policy applied (Layer 3 gate).

### R005 — Chunked, idempotent, resumable backfill job iterates the S3 `crawl_html/by_url/` self-archive and repopulates `Part.specifications` for existing parts using the new extraction layer. Started by milestone end; can finish post-merge.
- Class: operability
- Status: validated
- Description: Chunked, idempotent, resumable backfill job iterates the S3 `crawl_html/by_url/` self-archive and repopulates `Part.specifications` for existing parts using the new extraction layer. Started by milestone end; can finish post-merge.
- Why it matters: The 25k+ parts already scraped pre-M002 don't have structured fields. Backfill is what makes price-history + comparative-display UX feel alive on launch.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: none
- Validation: M002/S04 shipped backend/app/crawlers/backfill.py — chunked, idempotent, resumable backfill CLI iterating S3 crawl_html/by_url/. Started against the live local stack at M002 close (M002/S13/T05): dry-run + 100-part real run both green (97/100 specs repopulated, 0 failures), per-batch `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns` log lines emitted, backend/.crawler-state/backfill_cursor.json checkpoint written for operator resume. The R005 contract is 'started, not complete' — long-tail completion is post-merge. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log + backfill-cursor-snapshot.json + admin-extraction-health-post-backfill.json.
- Notes: Promoted at M002 close (2026-04-25). 'Started, not complete' contract met. Long-tail finish post-merge using committed cursor snapshot for --resume.

### R006 — Admin page distinguishes compliance (binary, 111/111 expected) from coverage (per-tier gradient — T0/T1/T2 with field-presence heatmap). Includes per-adapter `extraction_failure_rate` over a rolling window.
- Class: admin/support
- Status: validated
- Description: Admin page distinguishes compliance (binary, 111/111 expected) from coverage (per-tier gradient — T0/T1/T2 with field-presence heatmap). Includes per-adapter `extraction_failure_rate` over a rolling window.
- Why it matters: Operational visibility for the admin operator; "adapter X is silently failing" is detectable without log diving.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S11
- Validation: M002/S04 shipped backend/app/api/endpoints/admin/extraction_health.py exposing GET /api/admin/extraction-health. Live-hit at M002 close (M002/S13/T04) returned the canonical contract: compliance.compliant=108, compliance.total=108, per_tier {http:'83/83', tls:'15/15', browser:'10/10'}, coverage.per_tier with field-presence keys, failure_rate_7d list, window.days=7. M002/S11 reskinned the /admin/extraction-health UI onto the new design system; admin shell ui surface renders matching the JSON contract. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json (canonical 108/108 contract dump from live uvicorn) + admin-extraction-health-post-backfill.json (post-T05 delta dump).
- Notes: Promoted at M002 close (2026-04-25). UI screenshot pending operator review (admin-extraction-health-ui.png.OPERATOR-PENDING.md) — backend JSON contract verified.

### R007 — `GET /api/parts/{id}/price-history` returns retailer-level and listing-level history for a part with windowing. Batch endpoint `POST /api/parts/price-history` returns min/max/last/trend for N parts (used by list views).
- Class: core-capability
- Status: validated
- Description: `GET /api/parts/{id}/price-history` returns retailer-level and listing-level history for a part with windowing. Batch endpoint `POST /api/parts/price-history` returns min/max/last/trend for N parts (used by list views).
- Why it matters: The write path already exists (`part_listing_service.py`) but no read path consumes it. Surfacing it is what turns price-history from a table into a feature.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S06
- Validation: M002/S05 shipped both endpoints. GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param (30d/90d/180d/1y/all default 90d), retailer_id filter, and legacy=true list-shape shim for backward compatibility. POST /api/parts/price-history accepts 1-100 part_ids → batch min/max/last/trend with link-group dedup. Aggregation lives in app/api/services/part_price_aggregation_service.py (pure read service, canonical-coalesce expression). 18 endpoint tests + 11 service tests + OpenAPI snapshot test green. Frontend client (getPartPriceHistorySummary + getBatchPriceHistorySummary) wired with TS types; 26 vitest cases green. Verified 2026-04-25.
- Notes: Query-time aggregation per D004; perf-gate infra + gate-on-the-gate tests landed in T05; live 10× load run is R019's concern and remains active until run against a live uvicorn server with sample data. R036 (materialized part_price_summary) stays unopened unless that gate misses.

### R008 — Every part-card surface (parts catalog, build-list view, search results) shows a sparkline of recent price observations plus a "$X → $Y over N days" delta line where observations exist. No sparkline is rendered when zero observations exist; a single observation renders a dot.
- Class: primary-user-loop
- Status: validated
- Description: Every part-card surface (parts catalog, build-list view, search results) shows a sparkline of recent price observations plus a "$X → $Y over N days" delta line where observations exist. No sparkline is rendered when zero observations exist; a single observation renders a dot.
- Why it matters: First user-visible payoff of the price-history work — turns dormant data into a comparative signal at-a-glance.
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: M002/S10
- Validation: M002/S06 shipped frontend/src/components/charts/Sparkline.tsx + frontend/src/components/parts/PriceDeltaLine.tsx and integrated them into PartsCatalog rows; M002/S10 reskinned PartsCatalog onto the new design system preserving sparkline+delta surface. Verified at M002 close: M002/S13/T01 live UAT walkthrough confirms /parts catalog renders sparklines + delta lines for parts with observations (zero observations renders no sparkline; single observation renders a dot). Playwright e2e price-history.spec.ts:480 ('/parts catalog renders sparklines + delta lines') and parts-catalog visual-regression baselines green at mobile/tablet/desktop. Evidence: refreshed price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-{mobile,tablet,desktop}-linux.png + parts-catalog.spec.ts-snapshots/.
- Notes: Promoted at M002 close (2026-04-25). Sparkline rendering, delta line, and zero/single/multi-observation cases all covered by Playwright spec at 3 viewports.

### R009 — Clickable sparkline opens a per-part price-history detail view with retailer breakdowns, listing-level history, "best price seen at retailer X," and stale-observation caveats ("as of $date") for listings 60+ days old.
- Class: primary-user-loop
- Status: validated
- Description: Clickable sparkline opens a per-part price-history detail view with retailer breakdowns, listing-level history, "best price seen at retailer X," and stale-observation caveats ("as of $date") for listings 60+ days old.
- Why it matters: Drill-down for the comparative-shopping use case — "where was this cheapest, when?"
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: none
- Validation: M002/S06 shipped per-part price-history detail surface on /parts/:id with retailer breakdowns (flat list when ≤3 retailers, Tabs when >3), listing-level history rows, 'best price seen at retailer X' callout, and stale-observation 'as of $date' caveats for listings 60+ days old. Verified at M002 close: Playwright e2e price-history.spec.ts:533 ('/parts/:id detail renders retailer breakdown + stale caveat') green at mobile/tablet/desktop. M002/S13/T01 live UAT walkthrough exercised the click-through from /parts → /parts/:id and confirmed retailer breakdowns + stale caveats render. M002/S13/T03 removed the legacy=true query-param and PriceHistoryLineChart leaving the S06 'Price summary (90 days)' block as the canonical surface. Evidence: refreshed price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-{mobile,tablet,desktop}-linux.png.
- Notes: Promoted at M002 close (2026-04-25). Detail view, retailer breakdown (≤3 list / >3 Tabs), and 60d stale caveat all visible in committed Playwright baselines.

### R010 — User opts in on the part detail page with a threshold price; when any listing observation falls below threshold, an email fires via the existing SES path. Subscription-management page lists all active alerts and supports unsubscribe. Threshold evaluation is unit-tested; an integration test fires a real email to a fixture address.
- Class: primary-user-loop
- Status: validated
- Description: User opts in on the part detail page with a threshold price; when any listing observation falls below threshold, an email fires via the existing SES path. Subscription-management page lists all active alerts and supports unsubscribe. Threshold evaluation is unit-tested; an integration test fires a real email to a fixture address.
- Why it matters: Converts price-history from passive display into an active engagement loop — gives users a reason to come back.
- Source: user
- Primary owning slice: M002/S07
- Supporting slices: none
- Validation: M002/S07 shipped backend/app/api/models/part_price_alert.py + Alembic migration + part_price_alerts CRUD endpoints + price-drop alert evaluator hooked into the observation write path + SES email path + /account/alerts subscription-management page + unsubscribe-token redirect flow. Verified at M002 close (M002/S13/T01 live UAT walkthrough): subscribe → trigger observation below threshold → SES email arrives at fixture inbox `tylert2610+m002-uat@gmail.com` → click unsubscribe link → 302 redirect → /account/alerts?status=success → row removed. Backend logs surface `price_alert_evaluated: alert_id=... verdict=fired` and `price_alert_email_sent: alert_id=... success=true`. Playwright e2e price-alerts.spec.ts subscribe→manage→unsubscribe demo flow green at mobile/tablet/desktop. Evidence: T01 extraction-and-alert.log excerpts + refreshed price-alerts.spec.ts-snapshots/.
- Notes: Promoted at M002 close (2026-04-25). Live SES send + unsubscribe round-trip verified by operator. Recipient redacted from committed evidence per slice redaction constraints.

### R011 — CSS-variable-based token layer for color, spacing, type scale, radii, and shadows. Dark palette locked during the design-system slice; light mode deferred unless it falls out of token architecture naturally.
- Class: core-capability
- Status: validated
- Description: CSS-variable-based token layer for color, spacing, type scale, radii, and shadows. Dark palette locked during the design-system slice; light mode deferred unless it falls out of token architecture naturally.
- Why it matters: Substrate for the repo-wide reskin. Tokens-first means future palette adjustments don't require a code sweep.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: all subsequent UX slices
- Validation: S08/T02 — frontend/src/styles/tokens.css declares the full shadcn-standard token vocabulary on :root with HSL channels (background/foreground, card, popover, primary/secondary/accent, muted, destructive, border, input, ring + radius scale + shadow scale + z-index layers), bridges into Tailwind v4 via @theme so utilities like bg-background and border-border resolve, and is imported once from frontend/src/index.css. Production build (vite build) confirms .bg-background / --background present in dist/assets/*.css. Legacy --primary-*/--neutral-*/--accent-* blocks left intact for additive coexistence until S12 retires components/common/.
- Notes: Mockup spike at top of S08 (2–3 variants) gives user veto on direction before tokens lock.

### R012 — Restyled Radix primitives committed under `frontend/src/components/ui/`: Button, Dialog, DropdownMenu, Combobox, Toast, Tabs, Input, Select, Sheet at minimum. Each primitive supports all relevant states (default, hover, focus, disabled, loading, error). Replaces hand-rolled `components/common/` over the course of M002.
- Class: core-capability
- Status: validated
- Description: Restyled Radix primitives committed under `frontend/src/components/ui/`: Button, Dialog, DropdownMenu, Combobox, Toast, Tabs, Input, Select, Sheet at minimum. Each primitive supports all relevant states (default, hover, focus, disabled, loading, error). Replaces hand-rolled `components/common/` over the course of M002.
- Why it matters: Accessibility, keyboard nav, focus management for free; replaces accumulated hand-rolled drift in `components/common/`.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: M002/S09–S12
- Validation: S08/T03+T04 — all 9 primitives committed under frontend/src/components/ui/: button.tsx, input.tsx, select.tsx, tabs.tsx, combobox.tsx (Wave 1, T03) and dialog.tsx, dropdown-menu.tsx, sheet.tsx, toast.tsx (Wave 2, T04). Each uses cn() + cva() where applicable, consumes T02 tokens via Tailwind utilities (bg-primary, text-primary-foreground, focus-visible:ring-ring), and exposes the full state surface (default/hover/focus/disabled/loading/error). Sheet wraps Radix Dialog with a side cva variant; Toast wraps sonner. Animations land via inline @keyframes + @utility declarations in tokens.css instead of installing tailwindcss-animate (per slice plan preference).
- Notes: Deprecated `components/common/` primitives must be fully removed by S12.

### R013 — A single `e2e/components.spec.ts` mounts a kitchen-sink page rendering every primitive in every state and runs `toHaveScreenshot()` at three breakpoints (mobile/tablet/desktop). Snapshots committed; CI fails on diff with a generous-but-not-loose threshold (~0.2% pixel diff).
- Class: quality-attribute
- Status: validated
- Description: A single `e2e/components.spec.ts` mounts a kitchen-sink page rendering every primitive in every state and runs `toHaveScreenshot()` at three breakpoints (mobile/tablet/desktop). Snapshots committed; CI fails on diff with a generous-but-not-loose threshold (~0.2% pixel diff).
- Why it matters: Single spec file protects all 20+ pages from primitive-level visual drift during the ripple reskin.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: none
- Validation: S08/T05+T06 — frontend/e2e/components.spec.ts mounts /_kitchen-sink (renders all 9 primitives in every state via data-testid sections) and runs toHaveScreenshot({ fullPage: true }) at three viewport projects (mobile 375x667 / tablet 768x1024 / desktop 1280x800). playwright.config.ts sets expect.toHaveScreenshot.maxDiffPixelRatio = 0.002 (R013's 0.2% bar) and animations='disabled'. Three baseline PNGs committed under e2e/components.spec.ts-snapshots/. Fresh evidence: `npm run test:e2e` exits 0 with 6 passed (4.1s) — 3 components.spec runs + 3 smoke.spec runs across the three projects.
- Notes: Existing uncommitted `playwright.config.ts` and `smoke.spec.ts` land as part of S08.

### R014 — `/build-lists/{id}` rebuilt against new component library + tokens. Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works (tab order, focus indicators, escape on dialogs). Manual UAT checklist documented.
- Class: primary-user-loop
- Status: validated
- Description: `/build-lists/{id}` rebuilt against new component library + tokens. Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works (tab order, focus indicators, escape on dialogs). Manual UAT checklist documented.
- Why it matters: One of three explicitly user-flagged "needs love" surfaces; the canonical build-planning surface.
- Source: user
- Primary owning slice: M002/S09
- Supporting slices: none
- Validation: M002/S09 rebuilt /build-lists/{id} on the new component library + tokens. Playwright e2e build-list.spec.ts:232 (build-list detail visual regression), build-list.spec.ts:245 (edit dialog opens, focuses, and Escape closes), and build-list.spec.ts:278 (tab order surfaces visible focus on first interactive control) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. S09-UAT.md documented manual UAT checklist. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports. Evidence: refreshed build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-{mobile,tablet,desktop}-linux.png + gauntlet-evidence.json item #4.
- Notes: Promoted at M002 close (2026-04-25). Confirmed still-active per T06 plan's REQUIREMENTS.md cross-check; direct M002/S13/T06 evidence supports promotion alongside R016/R020.

### R015 — `/parts` rebuilt against new component library + tokens, with sparklines integrated into part cards (R008). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Class: primary-user-loop
- Status: validated
- Description: `/parts` rebuilt against new component library + tokens, with sparklines integrated into part cards (R008). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; the discovery entry point for the entire catalog.
- Source: user
- Primary owning slice: M002/S10
- Supporting slices: M002/S06
- Validation: M002/S10 rebuilt /parts on the new component library + tokens with S06 sparklines integrated into part cards. Playwright e2e parts-catalog.spec.ts:445 (parts catalog visual regression), parts-catalog.spec.ts:481 (add-to-build-list dialog opens, focus moves into it, Escape closes it), and parts-catalog.spec.ts:528 (tab traversal lands visible focus on search input) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. S10-UAT.md documented manual UAT checklist. price-history.spec.ts:480 (sparklines + delta lines) also green. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports. Evidence: refreshed parts-catalog.spec.ts-snapshots/ + price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-* + gauntlet-evidence.json item #4.
- Notes: Promoted at M002 close (2026-04-25). Confirmed still-active per T06 plan's REQUIREMENTS.md cross-check; direct M002/S13/T06 evidence supports promotion alongside R008/R016/R020.

### R016 — `/admin` rebuilt against new component library + tokens, including the extraction-health view (R006). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Class: admin/support
- Status: validated
- Description: `/admin` rebuilt against new component library + tokens, including the extraction-health view (R006). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; admin-as-operator efficiency surface.
- Source: user
- Primary owning slice: M002/S11
- Supporting slices: M002/S04
- Validation: M002/S11 shipped /admin shell + ExtractionHealth view rebuilt on the new component library + tokens. Playwright e2e admin.spec.ts:251 (admin dashboard visual regression) and admin.spec.ts:269 (admin extraction-health visual regression) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. Keyboard navigation, focus indicators, and Escape on dialogs validated by S09/S10/S11 desktop keyboard specs. Verified at M002 close: M002/S13/T04 live admin extraction-health JSON dump confirms backend contract still serves the canonical 108/108 shape consumed by the reskinned UI. Evidence: refreshed admin.spec.ts-snapshots/admin-{dashboard,extraction-health}-1-{mobile,tablet,desktop}-linux.png + admin-extraction-health.json.
- Notes: Promoted at M002 close (2026-04-25). Admin shell + extraction-health view both on new design system with refreshed baselines green at 3 viewports.

### R017 — All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check.
- Class: quality-attribute
- Status: validated
- Description: All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check.
- Why it matters: The cohesion goal — new visual language is the entire app, not three islands.
- Source: user
- Primary owning slice: M002/S12
- Supporting slices: M002/S09, M002/S10, M002/S11
- Validation: M002/S12 retired components/common/ + components/buttons/ across all ~17 remaining pages. Enforcement locked at M002/S12/T06 via (a) frontend/src/__tests__/no-legacy-primitives.test.ts vitest grep-guard, (b) frontend/eslint.config.js no-restricted-imports rule on **/components/common/* + **/components/buttons/*, (c) physical deletion of both directories (test ! -d frontend/src/components/buttons && test ! -d frontend/src/components/common returns 0). Verified at M002 close: gauntlet `npm test -- --run` returns 594 pass including the no-legacy-primitives.test.ts guard; `npm run lint` returns 108 errors at the MEM062 baseline with zero no-restricted-imports violations; `grep -rln 'components/common\\|components/buttons' frontend/src/` returns one self-referential match in the guard test only. Evidence: gauntlet-evidence.json items #3, #5 + frontend/src/__tests__/no-legacy-primitives.test.ts.
- Notes: Promoted at M002 close (2026-04-25). Three-layer enforcement (deleted directories + grep guard + ESLint rule) ensures the migration cannot regress.

### R018 — Build out `tests/` for the crawler subsystem: fixture-based unit tests for the universal extractor, contract tests for each Pydantic category model with 3–5 spot fixtures drawn from S3-archived HTML, smoke test on the backfill job sampling 100 parts and asserting `extraction_failure_rate` below threshold.
- Class: quality-attribute
- Status: validated
- Description: Build out `tests/` for the crawler subsystem: fixture-based unit tests for the universal extractor, contract tests for each Pydantic category model with 3–5 spot fixtures drawn from S3-archived HTML, smoke test on the backfill job sampling 100 parts and asserting `extraction_failure_rate` below threshold.
- Why it matters: Crawler subsystem currently has no tests. Building a quality bar for a new extraction layer with zero existing tests is core to making M002 verifiable.
- Source: inferred
- Primary owning slice: M002/S01
- Supporting slices: M002/S02, M002/S04
- Validation: Crawler test suite green at M002 close: `TESTING=true pytest -n auto --rootdir=backend -q --no-cov backend/tests` exits 0 with 2800 passed / 15 skipped / 0 failed in 36.34s (1075 warnings, all pre-existing). Suite includes M002/S01 SpecRegistry contract tests + ingest validation hook tests (23 in test_spec_registry_contract.py + test_ingest_spec_validation.py), M002/S02 universal-extractor fixture tests (extract_weight/material/finish/warranty/fitment_notes), M002/S03 compliance audit tests, M002/S04 backfill smoke tests sampling 100 parts and asserting extraction_failure_rate below threshold, plus per-adapter contract tests with 3-5 spot fixtures from S3-archived HTML for each Pydantic category model (CoiloverSpec, BrakeSpec, TurboSpec, UniversalSpec). Evidence: gauntlet-evidence.json item #1.
- Notes: Promoted at M002 close (2026-04-25). Universal extractor + per-category Pydantic models + backfill smoke + compliance audit all under test.

### R019 — Load test against the batch `POST /api/parts/price-history` endpoint at 10× current traffic on current catalog size. p95 latency budget enforced. If missed, the materialization fix-task (R036) opens.
- Class: quality-attribute
- Status: validated
- Description: Load test against the batch `POST /api/parts/price-history` endpoint at 10× current traffic on current catalog size. p95 latency budget enforced. If missed, the materialization fix-task (R036) opens.
- Why it matters: The user is scaling toward real users; perf gate is phrased against forward traffic, not localhost feel.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: none
- Validation: M002/S13/T02 re-ran the S05 perf gate against the live stack at the 10× config (50 users, 10 spawn-rate, 60s) on 2026-04-26 UTC. PASSED with GET p95=95ms (budget <200ms), POST p95=130ms (budget <500ms), 0 failures across 1893 requests. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json (mirrored from backend/.perf-runs/price-history-PASSED-20260426T051456Z.json). R036 (materialized part_price_summary) precondition not met — stays deferred per D004.
- Notes: Perf gate PASSED on first re-run. R036 remains deferred. See .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json for the percentile dump.

### R020 — Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass — not a full WCAG audit; baseline that Radix primitives unlock for free is preserved.
- Class: quality-attribute
- Status: validated
- Description: Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass — not a full WCAG audit; baseline that Radix primitives unlock for free is preserved.
- Why it matters: Scaling to real users includes users with assistive tech. Radix primitives cover the heavy lifting — this requirement is to not regress that for free coverage.
- Source: inferred
- Primary owning slice: M002/S09, M002/S10, M002/S11
- Supporting slices: M002/S12
- Validation: Tab order, focus indicators, Escape handling on dialogs, and screen-reader-friendly labels validated across each redesigned page during M002/S09 (build-list), M002/S10 (parts catalog), and M002/S11 (admin). Playwright e2e tests at desktop viewport assert keyboard behavior: build-list.spec.ts:245 ('edit dialog opens, focuses, and Escape closes'), build-list.spec.ts:278 ('tab order surfaces visible focus on first interactive control'), parts-catalog.spec.ts:481 ('add-to-build-list dialog opens, focus moves into it, Escape closes it'), parts-catalog.spec.ts:528 ('tab traversal lands visible focus on search input'). Radix primitives in frontend/src/components/ui/ provide built-in focus-trap behavior on Dialog/Sheet/DropdownMenu. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports including these keyboard specs. Evidence: gauntlet-evidence.json item #4.
- Notes: Promoted at M002 close (2026-04-25). Light pass — not a full WCAG audit; Radix primitive baseline preserved.

## Active

### R048 — Zero raw legacy palette utilities in `frontend/src/`.
- Class: core-capability
- Status: active
- Description: Zero raw legacy palette utilities (`bg-primary-[0-9]`, `text-primary-[0-9]`, `bg-neutral-[0-9]`, `text-neutral-[0-9]`, `bg-emerald-[0-9]`, `text-emerald-[0-9]`, `bg-indigo-[0-9]`, `text-indigo-[0-9]`, `text-accent-emerald`, `text-accent-amber`, `text-accent-rose`, `text-accent-purple`, etc.) anywhere in `frontend/src/`. Every consumer migrated to semantic tokens (`text-foreground`, `text-muted-foreground`, `bg-card`, `text-primary`, etc.) from `tokens.css`.
- Why it matters: The substrate exists but ~94 files still consume raw palette utilities. Until the consumers migrate, the legacy `@theme` palette can't be deleted and drift recurs.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S05
- Validation: unmapped
- Notes: Verified by grep at slice close. Mechanical migration — global by-token sweeps per atomic commit.

### R049 — Zero `glass-card` / `glass-button` / `glass` references in `frontend/src/`.
- Class: core-capability
- Status: active
- Description: Zero references to legacy glassmorphism utility classes (`glass-card`, `glass-button`, `glass`) anywhere in `frontend/src/` consumer code. Survives only inside `index.css` until pass 1 deletion at S04.
- Why it matters: Glass-* survives on 8 high-traffic pages including Home, Login, Register, Header. Migrating consumers is the precondition for deleting the utilities from `index.css`.
- Source: user
- Primary owning slice: M003/S02
- Supporting slices: M003/S05
- Validation: unmapped
- Notes: Each page's reskin replaces glass-* with `bg-card` / `border-border` + appropriate shadow / backdrop-blur tokens.

### R050 — Zero `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` legacy `:root` consumers.
- Class: core-capability
- Status: active
- Description: Zero consumers (in any `frontend/src/` file, including inline styles, CSS modules, and styled blocks) of the legacy `:root` palette variables (`--primary-50` through `--primary-950`, `--neutral-50` through `--neutral-950`, `--accent-emerald` / `--accent-amber` / `--accent-rose` / `--accent-purple`) or the legacy gradient vars (`--gradient-primary`, `--gradient-secondary`, `--gradient-dark`, `--gradient-glass`, `--gradient-hero`).
- Why it matters: The `:root` palette block in `index.css` can't be deleted until consumers migrate. Inline-style and css-var consumers are the second-class citizens that the global token sweep (R048) doesn't catch.
- Source: user
- Primary owning slice: M003/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Includes `body { background: var(--gradient-dark) }` and similar — body styles migrate to semantic-token equivalents in `tokens.css`.

### R051 — `@theme` palette removed from `index.css`; build fails on any surviving raw-palette utility.
- Class: quality-attribute
- Status: active
- Description: The Tailwind v4 `@theme` palette block in `index.css` (lines 7-36 — `--color-primary-50` through `--color-accent-purple`) is deleted. After deletion, `vite build` succeeds; any surviving `bg-primary-500` / `text-neutral-300` / `text-accent-emerald` / etc. is a build error.
- Why it matters: This is the load-bearing decision. Removing the palette from `@theme` makes the contract enforceable by tooling — drift can't recur because the legacy classes literally don't compile. The build is the milestone close gate.
- Source: user
- Primary owning slice: M003/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Depends on R048 + R049 + R050 landing first.

### R052 — Pass-2 decorative + animation utilities removed from `index.css`.
- Class: quality-attribute
- Status: active
- Description: After consumers migrate, `index.css` has the following deleted: `:root` palette block (lines 38-98), `.glass*` utilities (lines 295-381), `.btn-primary/secondary/outline` (lines 383-482), `.card` / `.card-interactive` / `.card-table-container` (lines 484-582), `.input-modern` (lines 584-616), `.skeleton` (line 647), `.hero-gradient` (line 660), `.text-gradient` (line 736), `.shadow-glow` (line 750), `.border-gradient` (line 745), and all 11 keyframes (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `pulse`, `shimmer`, `float`, `glow`, `gradientShift`, `borderGlow`, `progress-indeterminate`) plus their `.animate-*` consumer classes.
- Why it matters: Two-pass deletion — pass 1 (palette + glass + legacy component classes) is the high-traffic surface; pass 2 (decorative + animation) is where targeted gap-fill additions are most likely. Doing them as one slice (S04) keeps the deletion cliff bounded.
- Source: user
- Primary owning slice: M003/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Targeted token / keyframe additions land as atomic commits before the deletion (e.g. tokenized Home entrance animation, if it survives the polish pass).

### R053 — Targeted token / primitive / keyframe additions are atomic commits with rationale; bias toward consumption.
- Class: convention
- Status: active
- Description: When the migration surfaces a real gap (a missing semantic token, a missing primitive, a needed tokenized keyframe replacement), stop, add, commit with rationale, resume. Each addition is a standalone atomic commit. The bias is consumption of the existing system — gap-fills require concrete justification ("X pages need this and there's no clean way to express it with what we have"), not "this would be nice."
- Why it matters: Friction enforces the consumption bias. If additions land inline in migration commits, it's easy to keep adding "just one more"; atomic commits with rationale force the question "is this gap real?" and keep the audit trail clean for future devs.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S02, M003/S04, M003/S05
- Validation: unmapped
- Notes: Subject to R017 — additions land in `tokens.css` or `components/ui/`, never in `components/common/` or `components/buttons/`.

### R054 — Every dense `<table>` view audited at 360 / 768 / 1280 with documented per-viewport verdict.
- Class: primary-user-loop
- Status: active
- Description: The four admin `<table>` surfaces (admin extraction-health, admin parts, admin jobs, admin crawlers) plus `frontend/src/components/tables/ResponsiveTableWrapper.tsx` audited at 360 / 768 / 1280 with realistic densest data. Per-viewport verdict (`pass` / `fixed` / `acceptable-as-scroll`) documented in S03 slice summary.
- Why it matters: Real `<table>` surfaces have different overflow behavior than card-grids; admin tables in particular are wide and the responsive strategy is "table-internal horizontal scroll" which is acceptable but must be intentional.
- Source: user
- Primary owning slice: M003/S03
- Supporting slices: none
- Validation: unmapped
- Notes: "Acceptable-as-scroll" is a valid verdict for admin tables where horizontal scroll inside the table wrapper is the deliberate fallback. Page-level horizontal scroll is never acceptable.

### R055 — Every dense card-grid view audited at 360 / 768 / 1280; no column shoves into adjacent columns; root-cause fixes.
- Class: primary-user-loop
- Status: active
- Description: PartsCatalog (`/parts`), BuildListsCatalog (`/build-lists`), BuildListPart list (inside ViewBuildList), and Search results audited at 360 / 768 / 1280 with realistic densest data (longest part name, longest retailer chain, all optional columns populated). No column shoves into adjacent columns. Fixes are root-cause: min-width matches actual rendered content, OR cell content reflows / wraps cleanly, OR the column drops out of the layout via the existing responsive-priority logic.
- Why it matters: The `/parts` price-column overflow is the reported instance; the audit ensures the same class of bug isn't lurking on the other dense views. Root-cause fixes prevent regression.
- Source: user
- Primary owning slice: M003/S03
- Supporting slices: none
- Validation: unmapped
- Notes: PartsCatalog renders via card components (`PartList` / `PartListItem`), not `<table>`. Fix lives in those components or in the layout primitives they consume. Per-viewport verdict list in S03 slice summary.

### R056 — No unintended page-level horizontal scroll on any audited page at 360 / 768 / 1280.
- Class: quality-attribute
- Status: active
- Description: After S03 fixes land, no audited page produces unintended horizontal scroll at 360 / 768 / 1280. Intentional table-internal horizontal scroll (admin tables) is allowed; page-level scroll is not.
- Why it matters: Page-level horizontal scroll is the symptom users actually experience as "the layout is broken" on mobile.
- Source: inferred
- Primary owning slice: M003/S03
- Supporting slices: M003/S05
- Validation: unmapped
- Notes: Verified via Playwright at the three viewports + manual UAT. Visible to the user as the absence of a horizontal scrollbar.

### R057 — ViewPart shows ONE "Price by retailer" block; summary stats either drop or compress to a one-line header.
- Class: primary-user-loop
- Status: active
- Description: ViewPart (`/parts/:id`) shows a single "Price by retailer" block — a table with columns for retailer name, last observed price, sparkline, observation timing, and outbound `View at retailer` link. The standalone "Price summary (90 days)" stats card is either dropped or compressed to a one-line header above the table (e.g. `$X–$Y across N retailers, last observed Z`).
- Why it matters: Today the page renders two redundant blocks — both show retailer name + last price + observation timing. The unique signal in the second block is the outbound link, which is the business value. Collapsing to one block + preserving outbound links resolves the redundancy without losing information.
- Source: user
- Primary owning slice: M003/S03
- Supporting slices: none
- Validation: unmapped
- Notes: Aggressive collapse per locked decision (Layer 1). Both blocks are inline in `ViewPart.tsx` today — this is an in-place refactor, not a component swap.

### R058 — All outbound retailer links use `target="_blank" rel="noopener noreferrer"` with external-link affordance.
- Class: primary-user-loop
- Status: active
- Description: Every outbound `View at retailer` link in the collapsed ViewPart price block (and any other outbound retailer links surfaced during the polish pass) uses `target="_blank" rel="noopener noreferrer"` and renders a small external-link icon affordance to signal that clicking leaves carmodpicker.com.
- Why it matters: Outlinking is the business value of the price-by-retailer block. Standard link-safety attributes prevent reverse-tabnabbing and the affordance signals navigation intent.
- Source: user
- Primary owning slice: M003/S03
- Supporting slices: M003/S05
- Validation: unmapped
- Notes: External-link icon — use a Lucide icon (project already consumes lucide-react).

### R059 — Polish pass at 360 / 768 / 1280 across every page (~40 routes); IA judgment up to medium-impact.
- Class: primary-user-loop
- Status: active
- Description: Every route in the app visited at 360 / 768 / 1280 (~40 routes total). Structural cleanup applied where needed (layout fixes, redundant block collapses on judgment up to medium-impact, animation replacements, off-palette stat panels reskinned). High-impact IA changes (removing a feature, restructuring primary layout, navigation changes) surfaced and resolved with user approval. Per-page verdict list in S05 slice summary.
- Why it matters: This is the systematic visit that catches what global token sweeps + targeted slices miss. Without it, drift is invisible until users see it.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Medium-impact = combining adjacent cards, removing a redundant header, deduping a stats strip. ViewPart price collapse is the locked exemplar.

### R060 — Visual-regression baselines refreshed per slice for every page touched, reviewed before commit.
- Class: quality-attribute
- Status: active
- Description: Every page touched by a slice has Playwright `toHaveScreenshot()` baselines refreshed at 360 / 768 / 1280 (mobile / tablet / desktop projects). Diffs reviewed before commit — real regressions stand out against expected token-swap diffs.
- Why it matters: M002 burned on this (MEM066, MEM140) — batch baseline refresh hides regressions. Per-slice keeps reviews bounded and honest.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S02, M003/S03, M003/S04, M003/S05
- Validation: unmapped
- Notes: Maximum coverage — every page touched, no carve-out for secondary pages. Continues D006 (three-breakpoint Playwright strategy).

### R061 — Migration completion gauntlet at milestone close.
- Class: quality-attribute
- Status: active
- Description: At milestone close: zero raw palette utility hits, zero `glass-*` hits, zero legacy `:root` consumer hits in `frontend/src/` (greps from R048–R050); `vite build` succeeds with `@theme` palette removed; `npm run lint` baseline preserved (108 errors at MEM062); `npm run type-check` clean; `npm test -- --run` passes (594+ vitest); `npm run test:e2e` passes at all 3 viewports; manual UAT walkthrough at three viewports across priority pages documented.
- Why it matters: This is the close gate that proves the milestone actually shipped what it promised.
- Source: user
- Primary owning slice: M003/S06
- Supporting slices: none
- Validation: unmapped
- Notes: Optional extension — vitest grep-guard extended to also block `glass-*` / raw palette utilities re-entering, mirroring the R017 pattern.

## Deferred

### R030 — LLM extractor strategy that plugs into M002's per-category schema contract — adapter parser tries deterministic first; LLM fills missing fields against the schema; deterministic validators reject obviously wrong values.
- Class: core-capability
- Status: deferred
- Description: LLM extractor strategy that plugs into M002's per-category schema contract — adapter parser tries deterministic first; LLM fills missing fields against the schema; deterministic validators reject obviously wrong values.
- Why it matters: Coverage ceiling for category schemas on adapters with messy HTML; transformative-use positioning at scale.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped
- Notes: Cost analysis at 200k catalog × 20% × Haiku-cached ≈ $150–$200 one-time, ~$2k/year recurring. Acceptable; deferred to share LLM infrastructure (provider client, prompt mgmt, evals, cost tracking) with R031–R033 in M003.

### R031 — LLM suggests parts that fit the user's car + compatibility constraints + budget.
- Class: primary-user-loop
- Status: deferred
- Description: LLM suggests parts that fit the user's car + compatibility constraints + budget.
- Why it matters: Direct user value — turns the catalog into a guided shopping experience.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped
- Notes: Gates on R001–R009 — helpers without structured data are noise.

### R032 — LLM decomposes a goal (e.g., "daily driver → track car") into a phased parts list across multiple budget tiers.
- Class: primary-user-loop
- Status: deferred
- Description: LLM decomposes a goal (e.g., "daily driver → track car") into a phased parts list across multiple budget tiers.
- Why it matters: One step deeper than the helper — the "I don't know what I need" entry point.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped

### R033 — LLM-assisted summarization of a part page — TL;DR of specs, fit notes, and known compatibility callouts.
- Class: differentiator
- Status: deferred
- Description: LLM-assisted summarization of a part page — TL;DR of specs, fit notes, and known compatibility callouts.
- Why it matters: Lighter-weight than helper/planner; research-aid surface.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped

### R034 — Solve the Cloudflare bypass story for the 11 T2 adapters (aemelectronics, americanmuscle, apexwheels, dinan, ecstuning, fcpeuro, jegs, speedindustry, summitracing, tirerack) so they reliably produce extraction-able HTML.
- Class: operability
- Status: deferred
- Description: Solve the Cloudflare bypass story for the 11 T2 adapters (aemelectronics, americanmuscle, apexwheels, dinan, ecstuning, fcpeuro, jegs, speedindustry, summitracing, tirerack) so they reliably produce extraction-able HTML.
- Why it matters: T2 adapters are M002-compliant but coverage will be sparse; fixing reliability unlocks the rest of the catalog.
- Source: inferred
- Primary owning slice: M003-adjacent
- Supporting slices: none
- Validation: unmapped

### R035 — Light theme support across the app.
- Class: differentiator
- Status: deferred
- Description: Light theme support across the app.
- Why it matters: Scaling to a broader user base may include light-mode-preferring users.
- Source: inferred
- Primary owning slice: post-M002
- Supporting slices: none
- Validation: unmapped
- Notes: Token architecture in S08 makes light mode *possible*; whether we *ship* it in M002 is a mid-design-system-slice judgment call. Default: deferred unless it falls out for free.

### R036 — Denormalized per-part summary table (min/max/current/trend/sparkline points) refreshed on scrape. Replaces query-time aggregation if R019 perf gate misses.
- Class: quality-attribute
- Status: deferred
- Description: Denormalized per-part summary table (min/max/current/trend/sparkline points) refreshed on scrape. Replaces query-time aggregation if R019 perf gate misses.
- Why it matters: Fallback for price-history list-endpoint perf at scale.
- Source: inferred
- Primary owning slice: M002 fix-task
- Supporting slices: none
- Validation: unmapped
- Notes: Conditional — opens only if the perf gate in S05 fails.

## Out of Scope

### R040 — OpenTelemetry instrumentation with X-Ray-compatible export.
- Class: quality-attribute
- Status: out-of-scope
- Description: OpenTelemetry instrumentation with X-Ray-compatible export.
- Why it matters: At current traffic, CloudWatch Logs Insights + Sentry covers ~90% of debugging needs.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R041 — Migrate from sync SQLAlchemy to async.
- Class: quality-attribute
- Status: out-of-scope
- Description: Migrate from sync SQLAlchemy to async.
- Why it matters: Premature until traffic genuinely demands it; sync is fine at current scale.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R042 — PostgreSQL read replicas behind a routing layer.
- Class: quality-attribute
- Status: out-of-scope
- Description: PostgreSQL read replicas behind a routing layer.
- Why it matters: Admin dashboard pressure not yet a problem; primary write load is fine.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R043 — Redis cache for slow-moving reference data (cars, categories, manufacturers).
- Class: quality-attribute
- Status: out-of-scope
- Description: Redis cache for slow-moving reference data (cars, categories, manufacturers).
- Why it matters: Not the bottleneck right now; introduces operational complexity.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R044 — Replace hand-maintained `AMBIGUOUS_STANDALONE_CODES` with keyword-embedding-based disambiguation.
- Class: core-capability
- Status: out-of-scope
- Description: Replace hand-maintained `AMBIGUOUS_STANDALONE_CODES` with keyword-embedding-based disambiguation.
- Why it matters: Hand-maintained set covers known cases; ML investment doesn't pay back at current ambiguity volume.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R045 — SQLAlchemy `version_id_col` optimistic concurrency control.
- Class: quality-attribute
- Status: out-of-scope
- Description: SQLAlchemy `version_id_col` optimistic concurrency control.
- Why it matters: `SELECT FOR UPDATE` from v1.0 currently sufficient.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R046 — Scheduled canary runs of the most-stable adapter for synthetic uptime checks.
- Class: failure-visibility
- Status: out-of-scope
- Description: Scheduled canary runs of the most-stable adapter for synthetic uptime checks.
- Why it matters: Per-adapter parse-failure alarms from v1.0 already cover the gap.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R047 — User-facing announcement of M002 changes.
- Class: differentiator
- Status: out-of-scope
- Description: User-facing announcement of M002 changes.
- Why it matters: No users yet; changelog generates no value.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | validated | M002/S01 | M002/S03 | M002/S01 ships SpecRegistry + CategorySpec base + 3 concrete models (CoiloverSpec, BrakeSpec, TurboSpec) under backend/app/crawlers/specs/. Adapters declare targets via category_targets ClassVar on RetailerCrawlerAdapter (validated at import time against default_registry). Ingest in app/crawlers/base.py.ingest_payload validates payload.specifications against the resolved schema. Verified by 23 contract+integration tests in backend/tests/crawlers/test_spec_registry_contract.py and test_ingest_spec_validation.py — all green; full crawler suite 1284 passed, 1 skipped. |
| R002 | core-capability | validated | M002/S02 | M002/S03 | M002/S02 shipped backend/app/crawlers/parsing.py extensions (extract_weight, extract_material, extract_finish, extract_warranty, extract_fitment_notes) plus the RetailerCrawlerAdapter post-hook that auto-merges universal-field extraction into ScrapedPayload.specifications; per-field suppression supported via class attribute. Verified live in M002/S13/T01 UAT walkthrough — backend logs surface `universal_extraction_extracted` lines during the live scrape, and M002/S13/T04's compliance audit (108/108) confirms every adapter inherits the base-class universal extractor. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt (108/108 compliance proves universal-extractor inheritance) plus existing S02 contract tests. |
| R003 | core-capability | validated | M002/S03 | M002/S04 | M002/S03 shipped backend/app/crawlers/compliance_audit.py and the category_targets contract on RetailerCrawlerAdapter. Re-verified live at M002 close: `cd backend && python -m app.crawlers.compliance_audit` exits 0 with `Total: 108/108 compliant — T0 (http) 83/83, T1 (tls) 15/15, T2 (browser) 10/10` (canonical 108 figure per MEM037/MEM122; the M002 vision text's '111 adapters' refers to 3 IS_FALLBACK GenericHtmlParser instances per tier excluded from the registry per D-03). Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt. |
| R004 | failure-visibility | validated | M002/S01 | M002/S04 | M002/S01 wired ingest_payload to fail-soft on Pydantic ValidationError: drops the spec block (specifications=None), logs a structured WARN with adapter_name + inferred slug + e.errors()[:3], emits ExtractionFailureRate EMF metric (env-gated, same isolation pattern as emit_crawler_run_metrics — catch and log; never raise), and the Part still persists. Verified by 3 integration tests: test_invalid_specs_drop_to_none_and_part_persists, test_type_coercion_failure_drops_to_none, test_emit_extraction_failure_called_once_on_invalid_specs (caplog assertions lock in adapter_name + slug visibility). Pass-through cases (no spec block, no inferred slug, no model registered) keep all 108 legacy adapters working unchanged. |
| R005 | operability | validated | M002/S04 | none | M002/S04 shipped backend/app/crawlers/backfill.py — chunked, idempotent, resumable backfill CLI iterating S3 crawl_html/by_url/. Started against the live local stack at M002 close (M002/S13/T05): dry-run + 100-part real run both green (97/100 specs repopulated, 0 failures), per-batch `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns` log lines emitted, backend/.crawler-state/backfill_cursor.json checkpoint written for operator resume. The R005 contract is 'started, not complete' — long-tail completion is post-merge. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log + backfill-cursor-snapshot.json + admin-extraction-health-post-backfill.json. |
| R006 | admin/support | validated | M002/S04 | M002/S11 | M002/S04 shipped backend/app/api/endpoints/admin/extraction_health.py exposing GET /api/admin/extraction-health. Live-hit at M002 close (M002/S13/T04) returned the canonical contract: compliance.compliant=108, compliance.total=108, per_tier {http:'83/83', tls:'15/15', browser:'10/10'}, coverage.per_tier with field-presence keys, failure_rate_7d list, window.days=7. M002/S11 reskinned the /admin/extraction-health UI onto the new design system; admin shell ui surface renders matching the JSON contract. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json (canonical 108/108 contract dump from live uvicorn) + admin-extraction-health-post-backfill.json (post-T05 delta dump). |
| R007 | core-capability | validated | M002/S05 | M002/S06 | M002/S05 shipped both endpoints. GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param (30d/90d/180d/1y/all default 90d), retailer_id filter, and legacy=true list-shape shim for backward compatibility. POST /api/parts/price-history accepts 1-100 part_ids → batch min/max/last/trend with link-group dedup. Aggregation lives in app/api/services/part_price_aggregation_service.py (pure read service, canonical-coalesce expression). 18 endpoint tests + 11 service tests + OpenAPI snapshot test green. Frontend client (getPartPriceHistorySummary + getBatchPriceHistorySummary) wired with TS types; 26 vitest cases green. Verified 2026-04-25. |
| R008 | primary-user-loop | validated | M002/S06 | M002/S10 | M002/S06 shipped frontend/src/components/charts/Sparkline.tsx + frontend/src/components/parts/PriceDeltaLine.tsx and integrated them into PartsCatalog rows; M002/S10 reskinned PartsCatalog onto the new design system preserving sparkline+delta surface. Verified at M002 close: M002/S13/T01 live UAT walkthrough confirms /parts catalog renders sparklines + delta lines for parts with observations (zero observations renders no sparkline; single observation renders a dot). Playwright e2e price-history.spec.ts:480 ('/parts catalog renders sparklines + delta lines') and parts-catalog visual-regression baselines green at mobile/tablet/desktop. Evidence: refreshed price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-{mobile,tablet,desktop}-linux.png + parts-catalog.spec.ts-snapshots/. |
| R009 | primary-user-loop | validated | M002/S06 | none | M002/S06 shipped per-part price-history detail surface on /parts/:id with retailer breakdowns (flat list when ≤3 retailers, Tabs when >3), listing-level history rows, 'best price seen at retailer X' callout, and stale-observation 'as of $date' caveats for listings 60+ days old. Verified at M002 close: Playwright e2e price-history.spec.ts:533 ('/parts/:id detail renders retailer breakdown + stale caveat') green at mobile/tablet/desktop. M002/S13/T01 live UAT walkthrough exercised the click-through from /parts → /parts/:id and confirmed retailer breakdowns + stale caveats render. M002/S13/T03 removed the legacy=true query-param and PriceHistoryLineChart leaving the S06 'Price summary (90 days)' block as the canonical surface. Evidence: refreshed price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-{mobile,tablet,desktop}-linux.png. |
| R010 | primary-user-loop | validated | M002/S07 | none | M002/S07 shipped backend/app/api/models/part_price_alert.py + Alembic migration + part_price_alerts CRUD endpoints + price-drop alert evaluator hooked into the observation write path + SES email path + /account/alerts subscription-management page + unsubscribe-token redirect flow. Verified at M002 close (M002/S13/T01 live UAT walkthrough): subscribe → trigger observation below threshold → SES email arrives at fixture inbox `tylert2610+m002-uat@gmail.com` → click unsubscribe link → 302 redirect → /account/alerts?status=success → row removed. Backend logs surface `price_alert_evaluated: alert_id=... verdict=fired` and `price_alert_email_sent: alert_id=... success=true`. Playwright e2e price-alerts.spec.ts subscribe→manage→unsubscribe demo flow green at mobile/tablet/desktop. Evidence: T01 extraction-and-alert.log excerpts + refreshed price-alerts.spec.ts-snapshots/. |
| R011 | core-capability | validated | M002/S08 | all subsequent UX slices | S08/T02 — frontend/src/styles/tokens.css declares the full shadcn-standard token vocabulary on :root with HSL channels (background/foreground, card, popover, primary/secondary/accent, muted, destructive, border, input, ring + radius scale + shadow scale + z-index layers), bridges into Tailwind v4 via @theme so utilities like bg-background and border-border resolve, and is imported once from frontend/src/index.css. Production build (vite build) confirms .bg-background / --background present in dist/assets/*.css. Legacy --primary-*/--neutral-*/--accent-* blocks left intact for additive coexistence until S12 retires components/common/. |
| R012 | core-capability | validated | M002/S08 | M002/S09–S12 | S08/T03+T04 — all 9 primitives committed under frontend/src/components/ui/: button.tsx, input.tsx, select.tsx, tabs.tsx, combobox.tsx (Wave 1, T03) and dialog.tsx, dropdown-menu.tsx, sheet.tsx, toast.tsx (Wave 2, T04). Each uses cn() + cva() where applicable, consumes T02 tokens via Tailwind utilities (bg-primary, text-primary-foreground, focus-visible:ring-ring), and exposes the full state surface (default/hover/focus/disabled/loading/error). Sheet wraps Radix Dialog with a side cva variant; Toast wraps sonner. Animations land via inline @keyframes + @utility declarations in tokens.css instead of installing tailwindcss-animate (per slice plan preference). |
| R013 | quality-attribute | validated | M002/S08 | none | S08/T05+T06 — frontend/e2e/components.spec.ts mounts /_kitchen-sink (renders all 9 primitives in every state via data-testid sections) and runs toHaveScreenshot({ fullPage: true }) at three viewport projects (mobile 375x667 / tablet 768x1024 / desktop 1280x800). playwright.config.ts sets expect.toHaveScreenshot.maxDiffPixelRatio = 0.002 (R013's 0.2% bar) and animations='disabled'. Three baseline PNGs committed under e2e/components.spec.ts-snapshots/. Fresh evidence: `npm run test:e2e` exits 0 with 6 passed (4.1s) — 3 components.spec runs + 3 smoke.spec runs across the three projects. |
| R014 | primary-user-loop | validated | M002/S09 | none | M002/S09 rebuilt /build-lists/{id} on the new component library + tokens. Playwright e2e build-list.spec.ts:232 (build-list detail visual regression), build-list.spec.ts:245 (edit dialog opens, focuses, and Escape closes), and build-list.spec.ts:278 (tab order surfaces visible focus on first interactive control) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. S09-UAT.md documented manual UAT checklist. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports. Evidence: refreshed build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-{mobile,tablet,desktop}-linux.png + gauntlet-evidence.json item #4. |
| R015 | primary-user-loop | validated | M002/S10 | M002/S06 | M002/S10 rebuilt /parts on the new component library + tokens with S06 sparklines integrated into part cards. Playwright e2e parts-catalog.spec.ts:445 (parts catalog visual regression), parts-catalog.spec.ts:481 (add-to-build-list dialog opens, focus moves into it, Escape closes it), and parts-catalog.spec.ts:528 (tab traversal lands visible focus on search input) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. S10-UAT.md documented manual UAT checklist. price-history.spec.ts:480 (sparklines + delta lines) also green. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports. Evidence: refreshed parts-catalog.spec.ts-snapshots/ + price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-* + gauntlet-evidence.json item #4. |
| R016 | admin/support | validated | M002/S11 | M002/S04 | M002/S11 shipped /admin shell + ExtractionHealth view rebuilt on the new component library + tokens. Playwright e2e admin.spec.ts:251 (admin dashboard visual regression) and admin.spec.ts:269 (admin extraction-health visual regression) green at mobile/tablet/desktop after M002/S13/T06 baseline refresh. Keyboard navigation, focus indicators, and Escape on dialogs validated by S09/S10/S11 desktop keyboard specs. Verified at M002 close: M002/S13/T04 live admin extraction-health JSON dump confirms backend contract still serves the canonical 108/108 shape consumed by the reskinned UI. Evidence: refreshed admin.spec.ts-snapshots/admin-{dashboard,extraction-health}-1-{mobile,tablet,desktop}-linux.png + admin-extraction-health.json. |
| R017 | quality-attribute | validated | M002/S12 | M002/S09, M002/S10, M002/S11 | M002/S12 retired components/common/ + components/buttons/ across all ~17 remaining pages. Enforcement locked at M002/S12/T06 via (a) frontend/src/__tests__/no-legacy-primitives.test.ts vitest grep-guard, (b) frontend/eslint.config.js no-restricted-imports rule on **/components/common/* + **/components/buttons/*, (c) physical deletion of both directories (test ! -d frontend/src/components/buttons && test ! -d frontend/src/components/common returns 0). Verified at M002 close: gauntlet `npm test -- --run` returns 594 pass including the no-legacy-primitives.test.ts guard; `npm run lint` returns 108 errors at the MEM062 baseline with zero no-restricted-imports violations; `grep -rln 'components/common\\|components/buttons' frontend/src/` returns one self-referential match in the guard test only. Evidence: gauntlet-evidence.json items #3, #5 + frontend/src/__tests__/no-legacy-primitives.test.ts. |
| R018 | quality-attribute | validated | M002/S01 | M002/S02, M002/S04 | Crawler test suite green at M002 close: `TESTING=true pytest -n auto --rootdir=backend -q --no-cov backend/tests` exits 0 with 2800 passed / 15 skipped / 0 failed in 36.34s (1075 warnings, all pre-existing). Suite includes M002/S01 SpecRegistry contract tests + ingest validation hook tests (23 in test_spec_registry_contract.py + test_ingest_spec_validation.py), M002/S02 universal-extractor fixture tests (extract_weight/material/finish/warranty/fitment_notes), M002/S03 compliance audit tests, M002/S04 backfill smoke tests sampling 100 parts and asserting extraction_failure_rate below threshold, plus per-adapter contract tests with 3-5 spot fixtures from S3-archived HTML for each Pydantic category model (CoiloverSpec, BrakeSpec, TurboSpec, UniversalSpec). Evidence: gauntlet-evidence.json item #1. |
| R019 | quality-attribute | validated | M002/S05 | none | M002/S13/T02 re-ran the S05 perf gate against the live stack at the 10× config (50 users, 10 spawn-rate, 60s) on 2026-04-26 UTC. PASSED with GET p95=95ms (budget <200ms), POST p95=130ms (budget <500ms), 0 failures across 1893 requests. Evidence: .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json (mirrored from backend/.perf-runs/price-history-PASSED-20260426T051456Z.json). R036 (materialized part_price_summary) precondition not met — stays deferred per D004. |
| R020 | quality-attribute | validated | M002/S09, M002/S10, M002/S11 | M002/S12 | Tab order, focus indicators, Escape handling on dialogs, and screen-reader-friendly labels validated across each redesigned page during M002/S09 (build-list), M002/S10 (parts catalog), and M002/S11 (admin). Playwright e2e tests at desktop viewport assert keyboard behavior: build-list.spec.ts:245 ('edit dialog opens, focuses, and Escape closes'), build-list.spec.ts:278 ('tab order surfaces visible focus on first interactive control'), parts-catalog.spec.ts:481 ('add-to-build-list dialog opens, focus moves into it, Escape closes it'), parts-catalog.spec.ts:528 ('tab traversal lands visible focus on search input'). Radix primitives in frontend/src/components/ui/ provide built-in focus-trap behavior on Dialog/Sheet/DropdownMenu. Verified at M002 close: gauntlet `npm run test:e2e` returns 35 passed / 10 skipped at all 3 viewports including these keyboard specs. Evidence: gauntlet-evidence.json item #4. |
| R048 | core-capability | active | M003/S01 | M003/S05 | mapped |
| R049 | core-capability | active | M003/S02 | M003/S05 | mapped |
| R050 | core-capability | active | M003/S02 | none | mapped |
| R051 | quality-attribute | active | M003/S04 | none | mapped |
| R052 | quality-attribute | active | M003/S04 | none | mapped |
| R053 | convention | active | M003/S01 | M003/S02, M003/S04, M003/S05 | mapped |
| R054 | primary-user-loop | active | M003/S03 | none | mapped |
| R055 | primary-user-loop | active | M003/S03 | none | mapped |
| R056 | quality-attribute | active | M003/S03 | M003/S05 | mapped |
| R057 | primary-user-loop | active | M003/S03 | none | mapped |
| R058 | primary-user-loop | active | M003/S03 | M003/S05 | mapped |
| R059 | primary-user-loop | active | M003/S05 | none | mapped |
| R060 | quality-attribute | active | M003/S01 | M003/S02, M003/S03, M003/S04, M003/S05 | mapped |
| R061 | quality-attribute | active | M003/S06 | none | mapped |
| R030 | core-capability | deferred | M003 | none | unmapped |
| R031 | primary-user-loop | deferred | M003 | none | unmapped |
| R032 | primary-user-loop | deferred | M003 | none | unmapped |
| R033 | differentiator | deferred | M003 | none | unmapped |
| R034 | operability | deferred | M003-adjacent | none | unmapped |
| R035 | differentiator | deferred | post-M002 | none | unmapped |
| R036 | quality-attribute | deferred | M002 fix-task | none | unmapped |
| R040 | quality-attribute | out-of-scope | none | none | n/a |
| R041 | quality-attribute | out-of-scope | none | none | n/a |
| R042 | quality-attribute | out-of-scope | none | none | n/a |
| R043 | quality-attribute | out-of-scope | none | none | n/a |
| R044 | core-capability | out-of-scope | none | none | n/a |
| R045 | quality-attribute | out-of-scope | none | none | n/a |
| R046 | failure-visibility | out-of-scope | none | none | n/a |
| R047 | differentiator | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 14 (R048, R049, R050, R051, R052, R053, R054, R055, R056, R057, R058, R059, R060, R061)
- Mapped to slices: 14
- Validated: 20 (R001, R002, R003, R004, R005, R006, R007, R008, R009, R010, R011, R012, R013, R014, R015, R016, R017, R018, R019, R020)
- Unmapped active requirements: 0
