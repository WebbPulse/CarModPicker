# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

Guidelines:
- Keep requirements capability-oriented, not a giant feature wishlist.
- Requirements should be atomic, testable, and stated in plain language.
- Every **Active** requirement should be mapped to a slice, deferred, blocked with reason, or moved out of scope.
- Each requirement should have one accountable primary owner and may have supporting slices.
- Research may suggest requirements, but research does not silently make them binding.
- Validation means the requirement was actually proven by completed work and verification, not just discussed.

## Active

### R001 — Per-category Pydantic spec models registered centrally

- Class: core-capability
- Status: active
- Description: Define a `SpecRegistry` plus base `CategorySpec(BaseModel)` and 3–5 initial concrete category models (e.g., `CoiloverSpec`, `BrakeSpec`, `TurboSpec`). Adapters declare which categories they target via class attribute; ingest validates `Part.specifications` against the resolved schema.
- Why it matters: Schema contract that survives the M002→M003 boundary — extractor-agnostic so an LLM extractor can be dropped in later without restructuring. Errors surface at adapter boundary, not silently at ingest.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03
- Validation: mapped
- Notes: Pydantic v2 throughout project; `Part.specifications` is JSON-typed so no migration needed for new categories.

### R002 — Universal-field extraction auto-runs in adapter base class

- Class: core-capability
- Status: active
- Description: Shared utilities in `crawlers/parsing.py` extract universal fields (weight, material, finish, warranty, fitment notes) from product HTML. `RetailerCrawlerAdapter.parse_product_page` post-hook merges these into the `ScrapedPayload.specifications` dict for every adapter. Adapters can override or suppress per field.
- Why it matters: Universal coverage across all 111 adapters without per-adapter retrofit. Iteration is cheap because the S3 self-archive lets us re-extract against stored HTML.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: mapped
- Notes: Confidence flags on extracted fields mitigate false-positives (e.g., "weight" extracted from a shipping table).

### R003 — All 111 adapters conform to the new extraction pattern

- Class: core-capability
- Status: active
- Description: Every adapter in T0 (84), T1 (16), and T2 (11) declares its category-schema targets and inherits universal-field extraction via the base class. Compliance is binary and audited by `compliance_audit` script: 111/111.
- Why it matters: Pattern compliance is uniform; coverage gradient is per-tier (T2 sparse until Cloudflare reliability lands in M003-adjacent work). Avoids two-tier code paths.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S04
- Validation: mapped
- Notes: T2 adapters compliant-but-sparse is the expected state at M002 close, not a regression.

### R004 — Ingest validates and gracefully degrades on malformed specs

- Class: failure-visibility
- Status: active
- Description: When an adapter returns specs that fail Pydantic validation, ingest drops the spec block, ingests the part without specs, logs a structured warning, and increments a per-adapter `extraction_failure_rate` metric. Part ingest must never regress because category extraction is new.
- Why it matters: Extraction is new across all 111 adapters; silent regression of the existing ingest pipeline is the worst-case outcome.
- Source: inferred
- Primary owning slice: M002/S01
- Supporting slices: M002/S04
- Validation: mapped
- Notes: Sensible-defaults policy applied (Layer 3 gate).

### R005 — Re-extraction backfill against S3 self-archive

- Class: operability
- Status: active
- Description: Chunked, idempotent, resumable backfill job iterates the S3 `crawl_html/by_url/` self-archive and repopulates `Part.specifications` for existing parts using the new extraction layer. Started by milestone end; can finish post-merge.
- Why it matters: The 25k+ parts already scraped pre-M002 don't have structured fields. Backfill is what makes price-history + comparative-display UX feel alive on launch.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: none
- Validation: mapped
- Notes: Backfill *started* (not necessarily complete) is the milestone gate per Layer 4.

### R006 — Admin extraction-health view

- Class: admin/support
- Status: active
- Description: Admin page distinguishes compliance (binary, 111/111 expected) from coverage (per-tier gradient — T0/T1/T2 with field-presence heatmap). Includes per-adapter `extraction_failure_rate` over a rolling window.
- Why it matters: Operational visibility for the admin operator; "adapter X is silently failing" is detectable without log diving.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S11
- Validation: mapped
- Notes: Surfaced inside the redesigned admin shell in S11.

### R007 — Price-history aggregation API

- Class: core-capability
- Status: active
- Description: `GET /api/parts/{id}/price-history` returns retailer-level and listing-level history for a part with windowing. Batch endpoint `POST /api/parts/price-history` returns min/max/last/trend for N parts (used by list views).
- Why it matters: The write path already exists (`part_listing_service.py`) but no read path consumes it. Surfacing it is what turns price-history from a table into a feature.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S06
- Validation: mapped
- Notes: Query-time aggregation with explicit perf gate (D-arch-4); materialization is a fix-task only if the gate misses.

### R008 — Sparkline + price-delta line on every part card

- Class: primary-user-loop
- Status: active
- Description: Every part-card surface (parts catalog, build-list view, search results) shows a sparkline of recent price observations plus a "$X → $Y over N days" delta line where observations exist. No sparkline is rendered when zero observations exist; a single observation renders a dot.
- Why it matters: First user-visible payoff of the price-history work — turns dormant data into a comparative signal at-a-glance.
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: M002/S10
- Validation: mapped
- Notes: 90-day window cap on list views; full history only in detail view.

### R009 — Per-part price-history detail view

- Class: primary-user-loop
- Status: active
- Description: Clickable sparkline opens a per-part price-history detail view with retailer breakdowns, listing-level history, "best price seen at retailer X," and stale-observation caveats ("as of $date") for listings 60+ days old.
- Why it matters: Drill-down for the comparative-shopping use case — "where was this cheapest, when?"
- Source: user
- Primary owning slice: M002/S06
- Supporting slices: none
- Validation: mapped
- Notes: Reuses aggregation API from R007.

### R010 — Price-drop alerts (subscription, threshold, email)

- Class: primary-user-loop
- Status: active
- Description: User opts in on the part detail page with a threshold price; when any listing observation falls below threshold, an email fires via the existing SES path. Subscription-management page lists all active alerts and supports unsubscribe. Threshold evaluation is unit-tested; an integration test fires a real email to a fixture address.
- Why it matters: Converts price-history from passive display into an active engagement loop — gives users a reason to come back.
- Source: user
- Primary owning slice: M002/S07
- Supporting slices: none
- Validation: mapped
- Notes: New `part_price_alert` table + new email template. Unsubscribe link required for compliance.

### R011 — Tailwind token system with locked dark palette

- Class: core-capability
- Status: active
- Description: CSS-variable-based token layer for color, spacing, type scale, radii, and shadows. Dark palette locked during the design-system slice; light mode deferred unless it falls out of token architecture naturally.
- Why it matters: Substrate for the repo-wide reskin. Tokens-first means future palette adjustments don't require a code sweep.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: all subsequent UX slices
- Validation: mapped
- Notes: Mockup spike at top of S08 (2–3 variants) gives user veto on direction before tokens lock.

### R012 — shadcn-style copy-into-repo Radix primitives

- Class: core-capability
- Status: active
- Description: Restyled Radix primitives committed under `frontend/src/components/ui/`: Button, Dialog, DropdownMenu, Combobox, Toast, Tabs, Input, Select, Sheet at minimum. Each primitive supports all relevant states (default, hover, focus, disabled, loading, error). Replaces hand-rolled `components/common/` over the course of M002.
- Why it matters: Accessibility, keyboard nav, focus management for free; replaces accumulated hand-rolled drift in `components/common/`.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: M002/S09–S12
- Validation: mapped
- Notes: Deprecated `components/common/` primitives must be fully removed by S12.

### R013 — Kitchen-sink visual-regression Playwright spec

- Class: quality-attribute
- Status: active
- Description: A single `e2e/components.spec.ts` mounts a kitchen-sink page rendering every primitive in every state and runs `toHaveScreenshot()` at three breakpoints (mobile/tablet/desktop). Snapshots committed; CI fails on diff with a generous-but-not-loose threshold (~0.2% pixel diff).
- Why it matters: Single spec file protects all 20+ pages from primitive-level visual drift during the ripple reskin.
- Source: user
- Primary owning slice: M002/S08
- Supporting slices: none
- Validation: mapped
- Notes: Existing uncommitted `playwright.config.ts` and `smoke.spec.ts` land as part of S08.

### R014 — Build-list view redesigned + Playwright screenshot tests pass

- Class: primary-user-loop
- Status: active
- Description: `/build-lists/{id}` rebuilt against new component library + tokens. Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works (tab order, focus indicators, escape on dialogs). Manual UAT checklist documented.
- Why it matters: One of three explicitly user-flagged "needs love" surfaces; the canonical build-planning surface.
- Source: user
- Primary owning slice: M002/S09
- Supporting slices: none
- Validation: mapped

### R015 — Parts catalog redesigned + Playwright screenshot tests pass

- Class: primary-user-loop
- Status: active
- Description: `/parts` rebuilt against new component library + tokens, with sparklines integrated into part cards (R008). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; the discovery entry point for the entire catalog.
- Source: user
- Primary owning slice: M002/S10
- Supporting slices: M002/S06
- Validation: mapped

### R016 — Admin shell redesigned + Playwright screenshot tests pass

- Class: admin/support
- Status: active
- Description: `/admin` rebuilt against new component library + tokens, including the extraction-health view (R006). Playwright `toHaveScreenshot()` tests pass at mobile/tablet/desktop. Keyboard nav works. Manual UAT checklist documented.
- Why it matters: One of three priority surfaces; admin-as-operator efficiency surface.
- Source: user
- Primary owning slice: M002/S11
- Supporting slices: M002/S04
- Validation: mapped

### R017 — Repo-wide reskin: every other page on the new system

- Class: quality-attribute
- Status: active
- Description: All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check.
- Why it matters: The cohesion goal — new visual language is the entire app, not three islands.
- Source: user
- Primary owning slice: M002/S12
- Supporting slices: M002/S09, M002/S10, M002/S11
- Validation: mapped

### R018 — Crawler test infrastructure

- Class: quality-attribute
- Status: active
- Description: Build out `tests/` for the crawler subsystem: fixture-based unit tests for the universal extractor, contract tests for each Pydantic category model with 3–5 spot fixtures drawn from S3-archived HTML, smoke test on the backfill job sampling 100 parts and asserting `extraction_failure_rate` below threshold.
- Why it matters: Crawler subsystem currently has no tests. Building a quality bar for a new extraction layer with zero existing tests is core to making M002 verifiable.
- Source: inferred
- Primary owning slice: M002/S01
- Supporting slices: M002/S02, M002/S04
- Validation: mapped

### R019 — Price-history list-endpoint p95 inside budget at 10× current traffic

- Class: quality-attribute
- Status: active
- Description: Load test against the batch `POST /api/parts/price-history` endpoint at 10× current traffic on current catalog size. p95 latency budget enforced. If missed, the materialization fix-task (R036) opens.
- Why it matters: The user is scaling toward real users; perf gate is phrased against forward traffic, not localhost feel.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: none
- Validation: mapped

### R020 — Keyboard accessibility pass on redesigned pages

- Class: quality-attribute
- Status: active
- Description: Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass — not a full WCAG audit; baseline that Radix primitives unlock for free is preserved.
- Why it matters: Scaling to real users includes users with assistive tech. Radix primitives cover the heavy lifting — this requirement is to not regress that for free coverage.
- Source: inferred
- Primary owning slice: M002/S09, M002/S10, M002/S11
- Supporting slices: M002/S12
- Validation: mapped

## Validated

<!-- v1.0 (M001) requirements were tracked in `.planning/milestones/v1.0-REQUIREMENTS.md` (60 validated). They are not migrated here individually — see PROJECT.md "Validated" section for the rollup. -->

## Deferred

### R030 — LLM-as-fallback / LLM-first structured extraction

- Class: core-capability
- Status: deferred
- Description: LLM extractor strategy that plugs into M002's per-category schema contract — adapter parser tries deterministic first; LLM fills missing fields against the schema; deterministic validators reject obviously wrong values.
- Why it matters: Coverage ceiling for category schemas on adapters with messy HTML; transformative-use positioning at scale.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped
- Notes: Cost analysis at 200k catalog × 20% × Haiku-cached ≈ $150–$200 one-time, ~$2k/year recurring. Acceptable; deferred to share LLM infrastructure (provider client, prompt mgmt, evals, cost tracking) with R031–R033 in M003.

### R031 — LLM build helper

- Class: primary-user-loop
- Status: deferred
- Description: LLM suggests parts that fit the user's car + compatibility constraints + budget.
- Why it matters: Direct user value — turns the catalog into a guided shopping experience.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped
- Notes: Gates on R001–R009 — helpers without structured data are noise.

### R032 — LLM build planner

- Class: primary-user-loop
- Status: deferred
- Description: LLM decomposes a goal (e.g., "daily driver → track car") into a phased parts list across multiple budget tiers.
- Why it matters: One step deeper than the helper — the "I don't know what I need" entry point.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped

### R033 — LLM part-page summarization

- Class: differentiator
- Status: deferred
- Description: LLM-assisted summarization of a part page — TL;DR of specs, fit notes, and known compatibility callouts.
- Why it matters: Lighter-weight than helper/planner; research-aid surface.
- Source: user
- Primary owning slice: M003
- Supporting slices: none
- Validation: unmapped

### R034 — T2 (browser-tier) Cloudflare reliability

- Class: operability
- Status: deferred
- Description: Solve the Cloudflare bypass story for the 11 T2 adapters (aemelectronics, americanmuscle, apexwheels, dinan, ecstuning, fcpeuro, jegs, speedindustry, summitracing, tirerack) so they reliably produce extraction-able HTML.
- Why it matters: T2 adapters are M002-compliant but coverage will be sparse; fixing reliability unlocks the rest of the catalog.
- Source: inferred
- Primary owning slice: M003-adjacent
- Supporting slices: none
- Validation: unmapped

### R035 — Light mode

- Class: differentiator
- Status: deferred
- Description: Light theme support across the app.
- Why it matters: Scaling to a broader user base may include light-mode-preferring users.
- Source: inferred
- Primary owning slice: post-M002
- Supporting slices: none
- Validation: unmapped
- Notes: Token architecture in S08 makes light mode *possible*; whether we *ship* it in M002 is a mid-design-system-slice judgment call. Default: deferred unless it falls out for free.

### R036 — Materialized `part_price_summary` table

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

### R040 — Distributed tracing via OpenTelemetry / X-Ray

- Class: quality-attribute
- Status: out-of-scope
- Description: OpenTelemetry instrumentation with X-Ray-compatible export.
- Why it matters: At current traffic, CloudWatch Logs Insights + Sentry covers ~90% of debugging needs.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R041 — Async SQLAlchemy migration

- Class: quality-attribute
- Status: out-of-scope
- Description: Migrate from sync SQLAlchemy to async.
- Why it matters: Premature until traffic genuinely demands it; sync is fine at current scale.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R042 — Read replicas for report/stat queries

- Class: quality-attribute
- Status: out-of-scope
- Description: PostgreSQL read replicas behind a routing layer.
- Why it matters: Admin dashboard pressure not yet a problem; primary write load is fine.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R043 — Redis query-result caching

- Class: quality-attribute
- Status: out-of-scope
- Description: Redis cache for slow-moving reference data (cars, categories, manufacturers).
- Why it matters: Not the bottleneck right now; introduces operational complexity.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R044 — ML-assisted `car_inference` disambiguation

- Class: core-capability
- Status: out-of-scope
- Description: Replace hand-maintained `AMBIGUOUS_STANDALONE_CODES` with keyword-embedding-based disambiguation.
- Why it matters: Hand-maintained set covers known cases; ML investment doesn't pay back at current ambiguity volume.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R045 — Optimistic concurrency (`version_id_col`)

- Class: quality-attribute
- Status: out-of-scope
- Description: SQLAlchemy `version_id_col` optimistic concurrency control.
- Why it matters: `SELECT FOR UPDATE` from v1.0 currently sufficient.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R046 — Synthetic monitoring / canary crawler runs

- Class: failure-visibility
- Status: out-of-scope
- Description: Scheduled canary runs of the most-stable adapter for synthetic uptime checks.
- Why it matters: Per-adapter parse-failure alarms from v1.0 already cover the gap.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a

### R047 — Public launch announcement / changelog

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
| R001 | core-capability | active | M002/S01 | M002/S03 | mapped |
| R002 | core-capability | active | M002/S02 | M002/S03 | mapped |
| R003 | core-capability | active | M002/S03 | M002/S04 | mapped |
| R004 | failure-visibility | active | M002/S01 | M002/S04 | mapped |
| R005 | operability | active | M002/S04 | none | mapped |
| R006 | admin/support | active | M002/S04 | M002/S11 | mapped |
| R007 | core-capability | active | M002/S05 | M002/S06 | mapped |
| R008 | primary-user-loop | active | M002/S06 | M002/S10 | mapped |
| R009 | primary-user-loop | active | M002/S06 | none | mapped |
| R010 | primary-user-loop | active | M002/S07 | none | mapped |
| R011 | core-capability | active | M002/S08 | all UX slices | mapped |
| R012 | core-capability | active | M002/S08 | M002/S09–S12 | mapped |
| R013 | quality-attribute | active | M002/S08 | none | mapped |
| R014 | primary-user-loop | active | M002/S09 | none | mapped |
| R015 | primary-user-loop | active | M002/S10 | M002/S06 | mapped |
| R016 | admin/support | active | M002/S11 | M002/S04 | mapped |
| R017 | quality-attribute | active | M002/S12 | M002/S09–S11 | mapped |
| R018 | quality-attribute | active | M002/S01 | M002/S02, M002/S04 | mapped |
| R019 | quality-attribute | active | M002/S05 | none | mapped |
| R020 | quality-attribute | active | M002/S09–S11 | M002/S12 | mapped |
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

- Active requirements: 20
- Mapped to slices: 20
- Validated: 0 (M001 v1.0 rolled up in PROJECT.md)
- Unmapped active requirements: 0
