# M002: Data Enrichment + Frontend Design Reset — Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

## Project Description

CarModPicker scraped 25k+ parts during v1.0 but the catalog is bare — names, descriptions, prices. M002 turns that catalog into structured, comparative, derived data: per-category Pydantic spec models that all 111 adapters declare against, a universal-field extraction floor that auto-runs in the adapter base class, and price-history surfaces (sparkline + per-part detail view + drop alerts) that finally consume the `PartPriceHistory` table the v1.0 work landed. In parallel, the entire frontend gets a design-language reset on shadcn-on-Tailwind-tokens: the three user-flagged "needs love" pages (build-list view, parts catalog, admin) get first-class Playwright-screenshot-tested treatment; the other ~17 pages ripple onto the new component library; the hand-rolled `components/common/` retires.

## Why This Milestone

v1.0 closed the "platform debt" loop — Sentry, CloudWatch metrics, canonical parts dedup, concurrency hardening, test/coverage gates. v1.0 explicitly did not move the product forward; it made the product solid enough to move forward *from*. M002 is the first milestone where the product itself changes: enrichment delivers the *transformative comparative depth* called out in PROJECT.md as the core value upgrade, and the design reset matches the visual product to the new data depth. Doing them together (rather than enrichment-then-design or design-then-enrichment) keeps the slice ordering coherent — every redesigned page can land with the new data surfaces from day one, and the component library is in place when the price-history UI needs it.

LLM-tooling (build helper, planner, summarization, LLM-as-extractor) is M003 and depends on M002 — helpers without structured data are noise.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Browse `/parts` and see a sparkline + price-delta line on every product card where price observations exist
- Click any part card to drill into a per-part price-history view with retailer-by-retailer breakdowns and listing-level history
- Subscribe to a part with a price threshold and receive an email when any listing drops below it; manage their alerts on a subscription-management page
- See structured spec fields (universal floor + category-specific where the adapter's HTML cooperates) on every part the catalog has rescraped
- Navigate the entire app — build-list view, parts catalog, admin, and every other page — on a coherent shadcn+Tailwind design language with full keyboard support
- Read the redesigned admin extraction-health view and see which adapters are compliant (binary) and how much coverage each tier is producing (gradient)

### Entry point / environment

- Entry point: production app at `https://www.carmodpicker.com` (post-deploy) and dev at `localhost:4000`
- Environment: production (App Runner + RDS + S3 + SES + CloudWatch + Sentry); CI runs Playwright against the dev server
- Live dependencies involved: PostgreSQL (RDS), S3 (`crawl_html/by_url/` self-archive + user-images bucket), SES (email path for alerts), Sentry, CloudWatch (metrics + logs)

## Completion Class

- **Contract complete means:** Pydantic schema contract + universal extractor + adapter compliance audit passes 111/111 in `pytest`; all category spec models have contract tests; price-history aggregation API has unit + integration tests; component library has kitchen-sink Playwright spec passing.
- **Integration complete means:** End-to-end scrape → structured-spec extraction → ingest → aggregation API → frontend sparkline → detail view → drop alert email runs against a real product URL in staging or production with all subsystems live.
- **Operational complete means:** Re-extraction backfill running against the S3 archive (idempotent, resumable, can finish post-merge); admin extraction-health view live and showing real per-adapter signal; price-history list-endpoint p95 inside budget at 10× current traffic in load test.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A real production scrape of a coilover/brake/turbo product flows through: deterministic universal-field extraction → category-specific Pydantic validation → ingest → `Part.specifications` populated → aggregation API returns history → catalog page shows sparkline → detail page shows retailer breakdowns
- A subscribed user receives a real email when a listing drops below their threshold; the unsubscribe link works
- All 111 adapters report compliant in `python -m app.crawlers.compliance_audit`; T2 (11) compliant-but-sparse is the explicit expected state, not a regression
- No page in the app imports from `frontend/src/components/common/`; lint or grep check enforces this
- Playwright screenshot tests pass at mobile/tablet/desktop for build-list view, parts catalog, admin, and the kitchen-sink primitive page
- Re-extraction backfill is *running* against the S3 archive (does not need to be complete for milestone close)

## Architectural Decisions

### Per-category Pydantic spec models registered centrally

**Decision:** Schema contract is a `SpecRegistry` plus a base `CategorySpec(BaseModel)` and concrete category models (`CoiloverSpec`, `BrakeSpec`, `TurboSpec`, etc.). Adapters import the model they target and return validated instances; `ScrapedPayload.specifications: dict | None` carries the serialized result. Validation happens at the adapter boundary.

**Rationale:** Pydantic v2 is the project's validation library across `api/schemas/`. Type safety + IDE autocomplete inside adapters; errors surface at the adapter, not silently at ingest. Adapters fail silently today (junk extraction → null fields → still ingests) — strongly typed extraction puts a hard barrier between "tried to extract" and "ingest got something useful."

**Alternatives Considered:**
- JSON Schema files runtime-loaded — rejected: no type safety inside adapters, runtime-only errors.

### Universal-fields strategy — hybrid base-class auto-run

**Decision:** Shared utilities live in `crawlers/parsing.py` (`extract_weight`, `extract_material`, etc.). `RetailerCrawlerAdapter.parse_product_page` post-hook auto-merges universal-field extraction into every adapter's result. Adapters can override or suppress per field.

**Rationale:** Universal coverage across all 111 adapters without per-adapter retrofit. S3 self-archive lets us re-run the extractor against stored HTML cheaply when tuning; iteration is cheap. False-positive risk (extracting "weight" from a shipping table) mitigated by confidence flags on extracted fields.

**Alternatives Considered:**
- Each adapter handles universal fields itself — rejected: too much duplication for 111 retailers.
- Shared-but-opt-in — rejected: defeats the "universal floor" intent.

### Frontend design system — shadcn-style copy-into-repo on Tailwind 4

**Decision:** Copy Radix-based primitives into `frontend/src/components/ui/`, restyle them against a new token system, refactor pages to use them. Replaces hand-rolled `components/common/` over the course of M002.

**Rationale:** Radix brings accessibility, keyboard nav, focus management, and dark-mode-friendly behavior for free. Copy-into-repo means we own the code and can restyle freely. Replaces accumulated hand-rolled drift in `components/common/`. Tailwind 4 is already the styling layer; React 19 + TS is shadcn-compatible.

**Alternatives Considered:**
- Tokens-only refresh — rejected: too light-touch for the ambition; perpetuates `components/common/` drift.
- Custom-component polish — rejected: smallest scope, biggest "we still own this code" cost long-term.

### Price-history aggregation — query-time with explicit perf gate

**Decision:** `/api/parts/{id}/price-history` and the batch `POST /api/parts/price-history` aggregate at query time. A load test in S05 enforces a p95 budget at 10× current traffic. If the gate fails, a materialized `part_price_summary` table opens as a fix-task (R036).

**Rationale:** Write path already exists in `part_listing_service.py`; building denormalized table in M002 is premature given Redis and read replicas are deferred (R042/R043). Well-indexed Postgres handles this access pattern fine to 1M+ rows. `(part_listing_id, observed_at)` composite is already in place.

**Alternatives Considered:**
- Materialized `part_price_summary` upfront — rejected: premature optimization without measured signal.
- Pure query-time without perf gate — rejected: risk of shipping slow list views.

### Design exploration — mockup spike inside design-system slice

**Decision:** First 20–30% of S08 produces 2–3 distinct visual-direction mockups for user selection; rest of the slice implements against the chosen direction.

**Rationale:** Single sole stakeholder; protects against direction drift across later slices without eating a whole slice on mockups. Slice still ships real code.

**Alternatives Considered:**
- Dedicated mockup slice up front — rejected: one "unproductive-looking" slice, harder to demo.
- Skip exploration, agent picks direction — rejected: risk of regret several slices into the ripple.

### LLM extraction deferred to M003

**Decision:** M002 is deterministic-only extraction. The schema contract is designed to be extractor-agnostic so an LLM extractor can drop in during M003 alongside the LLM build helper/planner.

**Rationale:** Cost analysis (200k catalog × 20% × Haiku-cached ≈ $150–$200 one-time, ~$2k/year recurring) is acceptable but commits M002 to LLM cost, eval harness, and prompt management — infrastructure that should be shared with M003's user-facing LLM tools, not built twice.

**Alternatives Considered:**
- LLM-as-fallback in M002 — rejected: builds half an LLM harness now, full one in M003.
- LLM-first with deterministic validators — rejected: highest cost, biggest "is this actually right?" verification problem.

> See `.gsd/DECISIONS.md` for the full append-only register of project decisions.

## Error Handling Strategy

Sensible defaults applied (Layer 3 gate confirmed by user):

**Backend / extraction:**
- Adapter raises during structured extraction → part still ingests with `specifications=null`, structured warning logged, per-adapter `extraction_failure_rate` metric incremented. Part ingest must not regress because category extraction is new.
- Pydantic validation fails on returned specs → drop the spec block, ingest part without specs, log loudly, surface in admin extraction-health view.
- Universal-extractor false-positive (extracts "weight" from shipping table) → confidence flag on extracted fields; admin sees heuristic vs. high-confidence; UI threshold to display vs. hide.
- New category model added against existing parts → old parts have null specs and the UI handles "this category has a schema but this part predates it" gracefully (no fake values).

**Price-history:**
- Zero observations on a part → no sparkline, no delta line, just current price. Don't fake a flat line.
- Single observation only → sparkline shows a dot, "$X" with no delta.
- Aggregation query slower than perf budget → R019 perf gate fires, surface slow-query warning in logs, fall back to "current price only" in list views; materialization fix-task (R036) opens.
- Stale observations (60+ days) → "as of $date" caveat on the displayed price.

**Frontend:**
- Component library swap regresses an existing flow → per-page visual regression checklist before merging ripple slices; manual smoke pass against saved screenshots for non-priority pages, Playwright `toHaveScreenshot()` for priority pages + kitchen sink.
- Sparkline render fails on huge price-history payloads → cap to 90-day window for list views, full history only in detail view.

**Cross-cutting:**
- Re-extraction backfill against S3 archive → chunked, idempotent, resumable, doesn't lock live ingest pipeline, progress logged to admin.
- Extraction health visibility → admin sees per-adapter compliance (binary) and coverage (per-tier gradient) without log diving.

## Risks and Unknowns

- **Universal-extractor false-positive rate** — extracting "weight" from a shipping table is easy to do; tuning strictness without killing recall is an iteration loop. Mitigated by S3 self-archive (re-run extractor against historical HTML cheaply) and confidence flags on extracted fields.
- **Category-schema coverage against real HTML** — 3–5 Pydantic category models will land, but how many of the 111 adapters can actually fill them depends on adapter HTML cooperativeness. Coverage target is "30–50 of T0+T1 surface meaningful structured data," not "every adapter fills every category."
- **Ripple-wide reskin regression** — 20 pages touched by a new component library is the highest-blast-radius surface in M002. Defenses: kitchen-sink component spec + three-priority-page Playwright specs + manual UAT per ripple slice.
- **Price-history aggregation query perf** — `(part_listing_id, observed_at)` is indexed, but the batched list-view endpoint fanning out to N parts is the risk. R019 perf gate decides if materialization is needed.
- **Zero existing adapter test coverage** — `Has Tests: No` for the crawler subsystem means S01 is partly "build the test infra." That's real work, not free.
- **Uncommitted Playwright config** — `playwright.config.ts` and `frontend/e2e/smoke.spec.ts` are uncommitted as of M002 start; they land in S08 as part of the design-system slice.

## Existing Codebase / Prior Art

- `backend/app/crawlers/base.py` — `RetailerCrawlerAdapter` ABC; the seam where universal-field auto-run hooks in.
- `backend/app/crawlers/parsing.py` — existing shared parsing utilities; new `extract_weight`, `extract_material`, etc. land here.
- `backend/app/crawlers/adapters/tier0_http/` (84 adapters), `tier1_tls/` (16 adapters), browser-tier (11 adapters under `__init__.py`/dispatch) — all 111 retrofit targets.
- `backend/app/api/models/part.py` — `Part.specifications: JSON` already exists; no migration needed for new categories.
- `backend/app/api/models/part_price_history.py` — write path live in `part_listing_service.py:372`; no read path consumes it yet.
- `backend/app/api/services/part_listing_service.py` — observations write on every scrape; aggregation reads added in S05.
- `frontend/src/components/common/` — hand-rolled primitive library being retired by S08–S12.
- `frontend/src/pages/BuildListsCatalog.tsx` (660 LOC), `frontend/src/pages/PartsCatalog.tsx` (161 LOC), `frontend/src/pages/AdminDashboard.tsx` (131 LOC) — three priority redesign targets.
- `frontend/playwright.config.ts` + `frontend/e2e/smoke.spec.ts` — uncommitted; land in S08.
- S3 `crawl_html/by_url/` — self-archive keyed by URL hash; substrate for re-extraction backfill.
- `backend/app/core/email.py` + `backend/app/core/email_templates/` — existing email path; new `price_drop_alert.html` template lands in S07.

## Relevant Requirements

See `.gsd/REQUIREMENTS.md` for the full capability contract (R001–R020 active in M002, R030–R036 deferred to M003 / post-M002, R040–R047 out of scope).

Highlights:
- R001–R005: Schema contract, universal extraction, 111-adapter compliance, ingest validation, backfill — the data-enrichment spine.
- R006: Admin extraction-health view — the operational visibility surface.
- R007–R010: Price-history aggregation API, sparkline + delta on cards, detail view, drop alerts — the user-visible payoff.
- R011–R013: Token system, shadcn primitives, kitchen-sink visual-regression — the design-system substrate.
- R014–R017: Build-list / catalog / admin redesigns + repo-wide ripple — the visual-cohesion goal.
- R018: Crawler test infrastructure — quality bar.
- R019: Price-history p95 perf gate — scaling-readiness.
- R020: Keyboard accessibility on redesigned pages.

## Scope

### In Scope

- Per-category Pydantic spec contract + central registry
- Universal-field extraction in adapter base class; 111/111 adapter compliance
- Re-extraction backfill against S3 self-archive (started, not necessarily complete)
- Admin extraction-health view (compliance + per-tier coverage gradient)
- Price-history aggregation API (single + batch); query-time with perf gate
- Sparkline + price-delta on every part card
- Per-part price-history detail view with retailer breakdowns
- Price-drop alerts: subscription, threshold, email, unsubscribe management
- Tailwind token system + dark palette lock
- shadcn-style Radix primitives copied into `components/ui/`
- Kitchen-sink visual-regression Playwright spec at three breakpoints
- Build-list view, parts catalog, admin redesigns with Playwright screenshot tests at three breakpoints
- Repo-wide ripple reskin: every other page on the new system, manual UAT per page
- Crawler test infrastructure (universal-extractor fixtures, category-schema contract tests, backfill smoke test)
- Keyboard accessibility pass on redesigned pages
- Playwright `playwright.config.ts` + existing smoke spec committed (currently uncommitted)

### Out of Scope / Non-Goals

- LLM-based extraction or LLM-assisted user tools (deferred to M003)
- T2 Cloudflare reliability work (T2 adapters compliant-but-sparse is acceptable for M002 close)
- Light mode (deferred unless it falls out of token architecture for free)
- Materialized `part_price_summary` table (only opens if R019 perf gate misses)
- Public launch announcement / changelog (no users yet)
- Distributed tracing / OpenTelemetry, async SQLAlchemy, read replicas, Redis caching, ML-assisted `car_inference`, optimistic concurrency, synthetic monitoring (R040–R046)

## Technical Constraints

- Pydantic v2 is the validation layer across the project; new schemas must be Pydantic v2.
- `Part.specifications` is JSON-typed → no Alembic migration required for new category fields.
- All 111 adapters must conform to the new pattern; T2 (11) compliant-but-sparse is the explicit expected state.
- `RetailerCrawlerAdapter` is an ABC; base-class behavior must not break any existing adapter's existing fields (name/description/price/manufacturer/part_number/images/gtin).
- Tailwind 4 is the styling layer (already migrated in v1.0).
- React 19 + TypeScript strict mode (post-v1.0 ESLint strict applied).
- Frontend tests run via `vitest`; Playwright runs via `npm run test:e2e` (config landing in S08).
- Backend tests run via `pytest -n auto`; SQLite in-memory used for tests; Postgres only required for crawler integration smoke.
- No new external service dependencies in M002 (LLM provider deferred to M003).
- `--cov-fail-under=51` backend / 60-50-50-60 frontend coverage thresholds carried from v1.0; new code should hold the line, not regress.

## Integration Points

- **PostgreSQL (RDS):** new aggregation queries against `part_price_history` + `part_listing` + `retailer`; new `part_price_alert` table for R010.
- **S3 (`carmodpicker-prod-crawl-archive` or equivalent):** read-only iteration of `crawl_html/by_url/` for backfill (R005).
- **SES:** new email template `price_drop_alert.html`; sender path reuses existing `core/email.py` infrastructure.
- **Sentry:** structured warnings on extraction failures get auto-captured; no new SDK work.
- **CloudWatch:** new EMF metric for `extraction_failure_rate` per adapter; admin view consumes the same data via API.
- **Playwright:** new CI dependency for screenshot tests; runs against `localhost:4000` via `npm run dev` auto-launch.
- **Existing v1.0 adapter circuit breaker (pybreaker), parse-failure email reporting:** preserved; new extraction failures are *additive* logging, don't trigger circuit breaks.

## Testing Requirements

- **Crawler unit tests:** fixture-based tests for the universal extractor in `crawlers/parsing.py`; one fixture per universal field, multiple HTML patterns per fixture.
- **Category-schema contract tests:** for each Pydantic category model, 3–5 spot fixtures drawn from S3-archived HTML across multiple adapters; assert validated extraction result.
- **Adapter compliance audit:** `python -m app.crawlers.compliance_audit` script-as-test asserts all 111 adapters declare category targets and inherit base-class universal extraction.
- **Backfill smoke test:** sample 100 parts from the S3 archive, run through the full extraction pipeline, assert `extraction_failure_rate < threshold` (threshold defined in S04).
- **Price-history API tests:** unit tests for aggregation logic (windowing, retailer grouping, stale detection); integration test against fixture observations.
- **Price-drop alert tests:** unit test for threshold evaluation; integration test fires real email to a fixture address using the SES test mode.
- **Playwright kitchen-sink spec:** every primitive in every state at mobile/tablet/desktop; commit baseline snapshots.
- **Playwright priority-page specs:** build-list view, parts catalog, admin at mobile/tablet/desktop; commit baselines.
- **Manual UAT smoke checklists:** per slice, documented in slice UAT files.
- **Load test for R019:** explicit perf gate in S05 against 10× current traffic on current catalog size.

## Acceptance Criteria

Per-slice acceptance criteria (the planner uses these directly):

- **S01 (Schema contract + crawler test infra):** `pytest backend/app/crawlers/` passes; `SpecRegistry.resolve(category_id)` returns Pydantic models; ingest validates and rejects malformed specs without dropping the part; 3+ category models defined.
- **S02 (Universal extractor + base-class auto-run):** universal-field extraction runs on every adapter result; 5 archived HTML samples from 5 adapters all produce populated `specifications` at appropriate confidence levels; suppression mechanism works.
- **S03 (111-adapter compliance):** `python -m app.crawlers.compliance_audit` prints 111/111 compliant; each adapter declares category targets; T2 adapters compliant-but-sparse as expected.
- **S04 (Backfill + admin extraction-health):** `/admin/extraction-health` shows compliance (111/111) and per-tier coverage gradient; backfill kicked off, idempotent, resumable, logs progress.
- **S05 (Price-history aggregation API):** `GET /api/parts/{id}/price-history` + batch `POST` working with retailer + listing breakdowns; load test asserts p95 inside budget at 10× current traffic; if missed, R036 fix-task opens.
- **S06 (Sparkline + detail view):** every part card with observations shows sparkline + "$X → $Y" delta; detail view shows retailer breakdowns; zero-observation case renders cleanly without faking data.
- **S07 (Price-drop alerts):** subscription works; threshold evaluation fires email; subscription-management page lists + unsubscribes; integration test fires real email.
- **S08 (Design system + tokens + primitives + kitchen sink):** mockup variants presented and chosen; tokens file + 9+ shadcn primitives in `components/ui/`; `e2e/components.spec.ts` kitchen-sink screenshots green at three breakpoints; `playwright.config.ts` committed.
- **S09 (Build-list view redesign):** `/build-lists/{id}` reskinned; Playwright screenshot tests at mobile/tablet/desktop green; keyboard nav works; manual UAT complete.
- **S10 (Parts catalog redesign):** `/parts` reskinned with integrated sparklines from S06; Playwright screenshot tests green; keyboard nav works; manual UAT complete.
- **S11 (Admin shell redesign):** `/admin` reskinned including extraction-health view from S04; Playwright screenshot tests green; keyboard nav works; manual UAT complete.
- **S12 (Repo-wide ripple reskin):** all ~17 remaining pages on new component library; manual UAT per page; lint or grep check enforces no `components/common/` imports.
- **S13 (Final integration):** end-to-end scenario passes (real product → specs → observation → sparkline → detail → alert email); all Playwright specs green; backfill running.

## Open Questions

- **Which 3–5 category schemas land first?** — Coilovers, brakes, turbos are obvious candidates but the right call is "which categories have the most cooperative HTML across the largest number of adapters." Resolved during S01 with data-informed selection from the S3 archive.
- **Does admin UX grow large enough to split into its own milestone?** — Soft default is "fold it in, split-if-it-grows." Signal for splitting is mid-roadmap during planning. If S11 can't fit one slice, surface it as a re-roadmap event.
- **Does light mode fall out of token architecture for free?** — Token-first design makes light mode *possible*; whether it *ships* in M002 is a mid-S08 judgment call. Default deferred unless it's nearly free.
- **What's the exact p95 budget number for R019?** — Set during S05 before the load test based on a reasonable user-perceived list-view latency budget (~150ms p95 at 10× traffic is a reasonable starting target; refine in S05).
