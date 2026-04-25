# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R002 — Shared utilities in `crawlers/parsing.py` extract universal fields (weight, material, finish, warranty, fitment notes) from product HTML. `RetailerCrawlerAdapter.parse_product_page` post-hook merges these into the `ScrapedPayload.specifications` dict for every adapter. Adapters can override or suppress per field.
- Class: core-capability
- Status: active
- Description: Shared utilities in `crawlers/parsing.py` extract universal fields (weight, material, finish, warranty, fitment notes) from product HTML. `RetailerCrawlerAdapter.parse_product_page` post-hook merges these into the `ScrapedPayload.specifications` dict for every adapter. Adapters can override or suppress per field.
- Why it matters: Universal coverage across all 111 adapters without per-adapter retrofit. Iteration is cheap because the S3 self-archive lets us re-extract against stored HTML.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: mapped
- Notes: Confidence flags on extracted fields mitigate false-positives (e.g., "weight" extracted from a shipping table).

### R003 — Every adapter in T0 (84), T1 (16), and T2 (11) declares its category-schema targets and inherits universal-field extraction via the base class. Compliance is binary and audited by `compliance_audit` script: 111/111.
- Class: core-capability
- Status: active
- Description: Every adapter in T0 (84), T1 (16), and T2 (11) declares its category-schema targets and inherits universal-field extraction via the base class. Compliance is binary and audited by `compliance_audit` script: 111/111.
- Why it matters: Pattern compliance is uniform; coverage gradient is per-tier (T2 sparse until Cloudflare reliability lands in M003-adjacent work). Avoids two-tier code paths.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S04
- Validation: mapped
- Notes: T2 adapters compliant-but-sparse is the expected state at M002 close, not a regression.

### R005 — Chunked, idempotent, resumable backfill job iterates the S3 `crawl_html/by_url/` self-archive and repopulates `Part.specifications` for existing parts using the new extraction layer. Started by milestone end; can finish post-merge.
- Class: operability
- Status: active
- Description: Chunked, idempotent, resumable backfill job iterates the S3 `crawl_html/by_url/` self-archive and repopulates `Part.specifications` for existing parts using the new extraction layer. Started by milestone end; can finish post-merge.
- Why it matters: The 25k+ parts already scraped pre-M002 don't have structured fields. Backfill is what makes price-history + comparative-display UX feel alive on launch.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: none
- Validation: mapped
- Notes: Backfill *started* (not necessarily complete) is the milestone gate per Layer 4.

### R006 — Admin page distinguishes compliance (binary, 111/111 expected) from coverage (per-tier gradient — T0/T1/T2 with field-presence heatmap). Includes per-adapter `extraction_failure_rate` over a rolling window.
- Class: admin/support
- Status: active
- Description: Admin page distinguishes compliance (binary, 111/111 expected) from coverage (per-tier gradient — T0/T1/T2 with field-presence heatmap). Includes per-adapter `extraction_failure_rate` over a rolling window.
- Why it matters: Operational visibility for the admin operator; "adapter X is silently failing" is detectable without log diving.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S11
- Validation: mapped
- Notes: Surfaced inside the redesigned admin shell in S11.

### R008 — Every part-card surface (parts catalog, build-list view, search results) shows a sparkline of recent price observations plus a "$X → $Y over N days" delta line where observations exist. No sparkline is rendered when zero observations exist; a single observation renders a dot.
- Class: primary-user-loop
- Status: active
- Description: Every part-card surface (parts catalog, build-list view, search results) shows a sparkline of recent price observations plus a "$X → $Y over N days" delta line where observations exist. No sparkline is rendered when zero observations exist; a single observation renders a dot.
- Why it matters: First user-visible payoff of the price-history work — turns dormant data into a comparative signal at-a-glance.
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: M002/S10
- Validation: mapped
- Notes: 90-day window cap on list views; full history only in detail view.

### R009 — Clickable sparkline opens a per-part price-history detail view with retailer breakdowns, listing-level history, "best price seen at retailer X," and stale-observation caveats ("as of $date") for listings 60+ days old.
- Class: primary-user-loop
- Status: active
- Description: Clickable sparkline opens a per-part price-history detail view with retailer breakdowns, listing-level history, "best price seen at retailer X," and stale-observation caveats ("as of $date") for listings 60+ days old.
- Why it matters: Drill-down for the comparative-shopping use case — "where was this cheapest, when?"
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: none
- Validation: mapped
- Notes: Reuses aggregation API from R007.

### R010 — User opts in on the part detail page with a threshold price; when any listing observation falls below threshold, an email fires via the existing SES path. Subscription-management page lists all active alerts and supports unsubscribe. Threshold evaluation is unit-tested; an integration test fires a real email to a fixture address.
- Class: primary-user-loop
- Status: active
- Description: User opts in on the part detail page with a threshold price; when any listing observation falls below threshold, an email fires via the existing SES path. Subscription-management page lists all active alerts and supports unsubscribe. Threshold evaluation is unit-tested; an integration test fires a real email to a fixture address.
- Why it matters: Converts price-history from passive display into an active engagement loop — gives users a reason to come back.
- Source: user
- Primary owning slice: M002/S07
- Supporting slices: none
- Validation: mapped
- Notes: New `part_price_alert` table + new email template. Unsubscribe link required for compliance.

### R014 — `/build-lists/{id}` rebuilt against new component library + tokens. Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works (tab order, focus indicators, escape on dialogs). Manual UAT checklist documented.
- Class: primary-user-loop
- Status: active
- Description: `/build-lists/{id}` rebuilt against new component library + tokens. Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works (tab order, focus indicators, escape on dialogs). Manual UAT checklist documented.
- Why it matters: One of three explicitly user-flagged "needs love" surfaces; the canonical build-planning surface.
- Source: user
- Primary owning slice: M002/S09
- Supporting slices: none
- Validation: mapped

### R015 — `/parts` rebuilt against new component library + tokens, with sparklines integrated into part cards (R008). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Class: primary-user-loop
- Status: active
- Description: `/parts` rebuilt against new component library + tokens, with sparklines integrated into part cards (R008). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; the discovery entry point for the entire catalog.
- Source: user
- Primary owning slice: M002/S10
- Supporting slices: M002/S06
- Validation: mapped

### R016 — `/admin` rebuilt against new component library + tokens, including the extraction-health view (R006). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Class: admin/support
- Status: active
- Description: `/admin` rebuilt against new component library + tokens, including the extraction-health view (R006). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; admin-as-operator efficiency surface.
- Source: user
- Primary owning slice: M002/S11
- Supporting slices: M002/S04
- Validation: mapped

### R017 — All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check.
- Class: quality-attribute
- Status: active
- Description: All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check.
- Why it matters: The cohesion goal — new visual language is the entire app, not three islands.
- Source: user
- Primary owning slice: M002/S12
- Supporting slices: M002/S09, M002/S10, M002/S11
- Validation: mapped

### R018 — Build out `tests/` for the crawler subsystem: fixture-based unit tests for the universal extractor, contract tests for each Pydantic category model with 3–5 spot fixtures drawn from S3-archived HTML, smoke test on the backfill job sampling 100 parts and asserting `extraction_failure_rate` below threshold.
- Class: quality-attribute
- Status: active
- Description: Build out `tests/` for the crawler subsystem: fixture-based unit tests for the universal extractor, contract tests for each Pydantic category model with 3–5 spot fixtures drawn from S3-archived HTML, smoke test on the backfill job sampling 100 parts and asserting `extraction_failure_rate` below threshold.
- Why it matters: Crawler subsystem currently has no tests. Building a quality bar for a new extraction layer with zero existing tests is core to making M002 verifiable.
- Source: inferred
- Primary owning slice: M002/S01
- Supporting slices: M002/S02, M002/S04
- Validation: mapped

### R019 — Load test against the batch `POST /api/parts/price-history` endpoint at 10× current traffic on current catalog size. p95 latency budget enforced. If missed, the materialization fix-task (R036) opens.
- Class: quality-attribute
- Status: active
- Description: Load test against the batch `POST /api/parts/price-history` endpoint at 10× current traffic on current catalog size. p95 latency budget enforced. If missed, the materialization fix-task (R036) opens.
- Why it matters: The user is scaling toward real users; perf gate is phrased against forward traffic, not localhost feel.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: none
- Validation: mapped

### R020 — Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass — not a full WCAG audit; baseline that Radix primitives unlock for free is preserved.
- Class: quality-attribute
- Status: active
- Description: Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass — not a full WCAG audit; baseline that Radix primitives unlock for free is preserved.
- Why it matters: Scaling to real users includes users with assistive tech. Radix primitives cover the heavy lifting — this requirement is to not regress that for free coverage.
- Source: inferred
- Primary owning slice: M002/S09, M002/S10, M002/S11
- Supporting slices: M002/S12
- Validation: mapped

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
| R002 | core-capability | active | M002/S02 | M002/S03 | mapped |
| R003 | core-capability | active | M002/S03 | M002/S04 | mapped |
| R004 | failure-visibility | validated | M002/S01 | M002/S04 | M002/S01 wired ingest_payload to fail-soft on Pydantic ValidationError: drops the spec block (specifications=None), logs a structured WARN with adapter_name + inferred slug + e.errors()[:3], emits ExtractionFailureRate EMF metric (env-gated, same isolation pattern as emit_crawler_run_metrics — catch and log; never raise), and the Part still persists. Verified by 3 integration tests: test_invalid_specs_drop_to_none_and_part_persists, test_type_coercion_failure_drops_to_none, test_emit_extraction_failure_called_once_on_invalid_specs (caplog assertions lock in adapter_name + slug visibility). Pass-through cases (no spec block, no inferred slug, no model registered) keep all 108 legacy adapters working unchanged. |
| R005 | operability | active | M002/S04 | none | mapped |
| R006 | admin/support | active | M002/S04 | M002/S11 | mapped |
| R007 | core-capability | validated | M002/S05 | M002/S06 | M002/S05 shipped both endpoints. GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param (30d/90d/180d/1y/all default 90d), retailer_id filter, and legacy=true list-shape shim for backward compatibility. POST /api/parts/price-history accepts 1-100 part_ids → batch min/max/last/trend with link-group dedup. Aggregation lives in app/api/services/part_price_aggregation_service.py (pure read service, canonical-coalesce expression). 18 endpoint tests + 11 service tests + OpenAPI snapshot test green. Frontend client (getPartPriceHistorySummary + getBatchPriceHistorySummary) wired with TS types; 26 vitest cases green. Verified 2026-04-25. |
| R008 | primary-user-loop | active | M002/S06 | M002/S10 | mapped |
| R009 | primary-user-loop | active | M002/S06 | none | mapped |
| R010 | primary-user-loop | active | M002/S07 | none | mapped |
| R011 | core-capability | validated | M002/S08 | all subsequent UX slices | S08/T02 — frontend/src/styles/tokens.css declares the full shadcn-standard token vocabulary on :root with HSL channels (background/foreground, card, popover, primary/secondary/accent, muted, destructive, border, input, ring + radius scale + shadow scale + z-index layers), bridges into Tailwind v4 via @theme so utilities like bg-background and border-border resolve, and is imported once from frontend/src/index.css. Production build (vite build) confirms .bg-background / --background present in dist/assets/*.css. Legacy --primary-*/--neutral-*/--accent-* blocks left intact for additive coexistence until S12 retires components/common/. |
| R012 | core-capability | validated | M002/S08 | M002/S09–S12 | S08/T03+T04 — all 9 primitives committed under frontend/src/components/ui/: button.tsx, input.tsx, select.tsx, tabs.tsx, combobox.tsx (Wave 1, T03) and dialog.tsx, dropdown-menu.tsx, sheet.tsx, toast.tsx (Wave 2, T04). Each uses cn() + cva() where applicable, consumes T02 tokens via Tailwind utilities (bg-primary, text-primary-foreground, focus-visible:ring-ring), and exposes the full state surface (default/hover/focus/disabled/loading/error). Sheet wraps Radix Dialog with a side cva variant; Toast wraps sonner. Animations land via inline @keyframes + @utility declarations in tokens.css instead of installing tailwindcss-animate (per slice plan preference). |
| R013 | quality-attribute | validated | M002/S08 | none | S08/T05+T06 — frontend/e2e/components.spec.ts mounts /_kitchen-sink (renders all 9 primitives in every state via data-testid sections) and runs toHaveScreenshot({ fullPage: true }) at three viewport projects (mobile 375x667 / tablet 768x1024 / desktop 1280x800). playwright.config.ts sets expect.toHaveScreenshot.maxDiffPixelRatio = 0.002 (R013's 0.2% bar) and animations='disabled'. Three baseline PNGs committed under e2e/components.spec.ts-snapshots/. Fresh evidence: `npm run test:e2e` exits 0 with 6 passed (4.1s) — 3 components.spec runs + 3 smoke.spec runs across the three projects. |
| R014 | primary-user-loop | active | M002/S09 | none | mapped |
| R015 | primary-user-loop | active | M002/S10 | M002/S06 | mapped |
| R016 | admin/support | active | M002/S11 | M002/S04 | mapped |
| R017 | quality-attribute | active | M002/S12 | M002/S09, M002/S10, M002/S11 | mapped |
| R018 | quality-attribute | active | M002/S01 | M002/S02, M002/S04 | mapped |
| R019 | quality-attribute | active | M002/S05 | none | mapped |
| R020 | quality-attribute | active | M002/S09, M002/S10, M002/S11 | M002/S12 | mapped |
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

- Active requirements: 14
- Mapped to slices: 14
- Validated: 6 (R001, R004, R007, R011, R012, R013)
- Unmapped active requirements: 0
