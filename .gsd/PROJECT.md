# CarModPicker

## What This Is

CarModPicker is a price-aggregation, parts-discovery, compatibility, and build-planning hub for car enthusiasts. The car modification hobby is fractured — information lives across dozens of retailer sites, forums, Discord servers, and YouTube videos, with no single tool that helps an enthusiast plan, price, and track a full build across multiple projects. CarModPicker aims to be that common flashpoint: a place to discover parts, aggregate prices across retailers, map part-to-car compatibility, and organize builds in shareable lists.

The platform consists of a FastAPI/PostgreSQL backend, a React frontend, and a Chrome extension that scrapes retailer pages. A per-retailer crawler swarm of 108 auto-discovered adapters populates a canonical parts catalog, deduplicated across retailers, with per-retailer price history. The product is live on AWS (App Runner + RDS + S3 + SES + CloudWatch + Sentry) at low traffic — not yet publicly launched at scale. Foundational tech-debt is paid down (v1.0 milestone shipped 2026-04-24); the next milestone moves into rich structured data extraction and user-facing build-planning tooling.

## Core Value

**A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.** If everything else fails — social features, build logs, the Chrome extension, the admin tooling — what must remain true is that an enthusiast can find the parts they're considering, see what they cost across sellers, know whether they fit their car, and organize the ones they want into a build list.

Core Value reaffirmed at v1.0 close — every shipped capability traces back to it. Next milestone adds **transformative comparative depth** (structured extraction, derived comparative data, LLM-assisted build planning) — same north star, deeper utility.

## Requirements

### Validated

<!-- Shipped and in production. Items inferred from codebase pre-v1.0 are listed first; v1.0 milestone deliverables follow with milestone reference. -->

**Pre-v1.0 (existing platform):**

- ✓ Email/password auth with email verification — existing
- ✓ Optional 2FA (TOTP) and WebAuthn passkeys — existing
- ✓ Google OAuth sign-in / link account — existing
- ✓ JWT sessions (configurable expiry, 15min–7d) — existing
- ✓ User roles: user / admin / superuser — existing
- ✓ Subscription tiers with feature gating — existing
- ✓ Canonical parts model (recently refactored for cross-retailer dedup) — existing
- ✓ Part manufacturers, retailers, categories reference data — existing
- ✓ Car generations reference dataset (car inference engine) — existing
- ✓ Build lists with phases, part membership, car linkage — existing
- ✓ Build logs (forum-style threads; deliberately thin) — existing
- ✓ Polymorphic voting system (one table, all entities) — existing
- ✓ Polymorphic reporting system (parallel to votes) — existing
- ✓ S3 image upload + presigned-URL serving + Pillow processing — existing
- ✓ Search across parts, build lists, etc. — existing
- ✓ Admin endpoints (jobs, crawlers, stats, DB ops) — existing
- ✓ Bug-report capture endpoint — existing
- ✓ Per-retailer crawler adapter system (108 adapters auto-discovered, 3 fetcher tiers) — existing
- ✓ Self-archive bucket + re-scrape against archive for offline tuning — existing
- ✓ Chrome extension (scrape retailer pages → POST to API; popup auth) — existing
- ✓ AWS deployment: App Runner + RDS PG16 + S3 + SES + EventBridge + CloudFront — existing
- ✓ Rate limiting + structured logging (request/user context) — existing
- ✓ `BaseEndpointRouter` / `BaseCRUDService` / `EndpointRegistry` abstractions — existing

**v1.0 (Tech-Debt Audit + Fix-All — shipped 2026-04-24):**

- ✓ Auth / account-flow refactor — `auth.py` (1,195 LOC) → `auth/` subpackage (core/two_factor/webauthn/oauth/_helpers); `admin.py` (2,055 LOC) → `admin/` subpackage; PyJWT migration; OpenAPI-driven `API_CONTRACT.md` — v1.0 (Phase 5)
- ✓ Crawler system hardening — adapter auto-discovery (108 adapters), pybreaker circuit breaker, per-adapter pre-crawl `robots.txt` health check, ThreadPoolExecutor parallelization, parse-failure email reporting — v1.0 (Phase 3)
- ✓ Observability & logging audit — Sentry backend (FastAPI/SQLAlchemy/before_send) + frontend (`@sentry/react` + Session Replay + RouteGroupBoundary), CloudWatch EMF per-adapter metrics, per-adapter parse-failure alarm, request_id/user_id propagation — v1.0 (Phase 2)
- ✓ DB / migrations / perf pass — N+1 fix in build logs (selectinload + 2-query regression test), 13 FK indexes, `with_for_update` row locks + 10-thread postgres concurrency CI, 304-site `session.query → select()` sweep, `lazy="raise"` on hot relationships, `pool_recycle=1800` — v1.0 (Phase 4)
- ✓ Parts & canonical dedup consolidation — transactional part linking with concurrency invariants (no orphans, no cycles, exactly-one-canonical), `AMBIGUOUS_STANDALONE_CODES` documented + 26 ambiguity-vector regression tests — v1.0 (Phase 4)
- ✓ Frontend structure cleanup — `services/Api.ts` (1,520 LOC) → 20 per-domain modules; ESLint strict (`no-explicit-any`, `no-unsafe-*`); `RouteGroupBoundary` on 4 lazy route groups; Tailwind v3→v4 codemod; madge circular-import CI — v1.0 (Phase 6)
- ✓ Test coverage & CI gates — backend `--cov-fail-under=51`; frontend vitest 60/50/50/60 thresholds enforced; migration DROP-guard; bandit HIGH gate; weekly Dependabot — v1.0 (Phase 1 + Phase 8)
- ✓ General code-quality sweep — `car_generations_data.py` (8,412 LOC literal) → JSON + `lru_cache`; Pydantic v1 sweep; 68-site logger DI sweep; dead-code helpers removed; OpenAPI snapshot drift guard — v1.0 (Phase 3 + 5 + 7)
- ✓ Opportunistic UX polish — parts-catalog polish landed alongside Phase 6 frontend touches — v1.0 (Phase 6)
- ✓ Stack patch upgrades — FastAPI 0.136, Pydantic 2.13, SQLAlchemy 2.0.49, Alembic 1.18, Uvicorn 0.45 — v1.0 (Phase 6)

### Active

<!-- Next milestone scope: data enrichment + user-facing planner tooling. Sources: REQUIREMENTS.md v2 section + v1.0 audit residue retained as forward-looking themes. -->

- [ ] **Rich structured extraction from scraped pages** — derived attributes, specs, compatibility hints beyond bare descriptions (ENRICH-01)
- [ ] **Per-adapter schema contract for structured fields** — make derived data validatable per retailer (ENRICH-02)
- [ ] **Price-history derivation from repeated scrapes** — turn the existing self-archive into time-series price data (ENRICH-03)
- [ ] **Transformative-use positioning** — derived comparative data as the user-facing output (defensible product framing) (ENRICH-04)
- [ ] **LLM build helper** — suggests parts that fit user's car + compatibility + budget (LLM-01) — gates on enrichment landing
- [ ] **LLM build planner** — decomposes goals (e.g., "daily driver → track car") into phased parts list (LLM-02)
- [ ] **Part-page summarization for research** — LLM-assisted (LLM-03)
- [ ] **OAuth cassette recording** — record 2 Google OAuth characterization tests with sandbox creds (carry-over from v1.0 — currently skip clean) — bounds: SAFE-06 follow-up
- [ ] **Deploy v1.0 infrastructure changes** — operator-gated terraform apply for per-adapter parse-failure alarm fan-out (~108 alarm creates, ~$10.80/mo CloudWatch delta) — bounds: gated to v1.0 deploy window with 24h staging bake (D-58)

### Out of Scope

<!-- Explicit exclusions for ongoing work, with reasoning. Reviewed at v1.0 close. -->

- **Deep security hardening (SOC2, pen-testing, compliance arc)** — target the attainable 90%, not the last 10%. Maintain v1.0 baseline (rate-limit, PyJWT, 2FA, email verify, CORS, bandit HIGH gate) but no penetration-testing / SOC2 / compliance arc. Not a B2B SaaS. — *Still valid*
- **LLM-based scraping / extraction pipeline** — cost-prohibitive until business model proves out. Stay selector-based; LLMs reserved for *user-facing* tools (build helpers/planners) downstream of structured-data extraction. — *Still valid*
- **Heavy social features / build-log expansion** — build logs stay intentionally thin; social angles are post-MVP and come after rich data + planning tools land. — *Still valid*
- **Mobile app** — web + extension only. Native clients are a separate future arc. — *Still valid*
- **Dedicated parts-catalog UX redesign phase** — UX work remains opportunistic (touched-page-gets-polished). Full catalog UX redesign deferred to its own future milestone. — *Still valid*
- **Payment / subscription tier rework** — current tier system stands as-is; no tier additions, pricing changes, or billing-provider swaps. — *Still valid*
- **Microservices split for crawler subsystem** — App Runner + ECS Fargate already provides isolation. — *Still valid*
- **Async SQLAlchemy migration** — major refactor; premature at current traffic. Reconsider when read-replica pressure proves out. — *Still valid*
- **Distributed tracing (OpenTelemetry / X-Ray)** — CloudWatch Logs Insights + Sentry covers 90% at current traffic; revisit when end-to-end latency debugging demands it. — *Still valid (deferred from v1.0 OBS)*

**Removed at v1.0 close:** "New user-facing features" — this exclusion was scoped to the v1.0 cleanup arc only. Next milestone is explicitly a feature milestone (data enrichment + LLM-assisted build planning).

## Context

- **Post-v1.0 brownfield, foundation now solid.** v1.0 (Tech-Debt Audit + Fix-All) shipped 2026-04-24 — 8 phases, 60 plans, 60/60 requirements satisfied. Codebase: ~81k LOC backend Python (`app/`), ~49k LOC frontend TS/TSX (`src/`), ~3k LOC Chrome extension; ~42k LOC backend tests, ~13k LOC frontend tests. 22+ models with FK indexes; 108 crawler adapters auto-discovered.
- **Stack post-v1.0:** Python 3.13 / FastAPI 0.136.1 + React 19 / TypeScript + PostgreSQL 16 + AWS (App Runner, RDS PG16, S3, SES, EventBridge, CloudFront). Pydantic 2.13.3 + SQLAlchemy 2.0.49 + Alembic 1.18.4 + Uvicorn 0.45.0 + PyJWT 2.12.1 (replaced python-jose). Tailwind v4. Sentry SDK 2.x backend + `@sentry/react` with Session Replay frontend.
- **CI gates landed:** backend `--cov-fail-under=51` + frontend vitest 60/50/50/60 thresholds; migration DROP-guard; bandit HIGH; madge circular-import; OpenAPI snapshot drift; weekly Dependabot.
- **Codebase map** lives in `.planning/codebase/` (`ARCHITECTURE.md`, `STACK.md`, `CONCERNS.md`, `CONVENTIONS.md`, `INTEGRATIONS.md`, `STRUCTURE.md`, `TESTING.md`) — was the seed list for v1.0 audit; refresh as next milestone surfaces new debt.
- **Production status.** Deployed on AWS at `carmodpicker.com` with a staging subdomain. Low / no external traffic yet — fast iteration is safe, breaking changes don't harm real users. v1.0 paid down structural debt; next milestone can build user-facing depth (enrichment + LLM tools) on a stable foundation.
- **Data-at-scale playground.** Local Postgres has ~25k real scraped parts; `carmodpicker-local-crawl` (local) and `carmodpicker-production-crawl-data` (prod) S3 archive buckets let the crawler re-run against stored HTML. Both are first-class tools for iterating on canonical-dedup logic and extraction robustness without hammering retailers.
- **Copyright / transformative-use posture.** Crawler must evolve beyond dumping descriptions; structured, derived, comparative data is the defensible product. Next milestone (ENRICH-01..04) lands this directly.
- **AI-assisted development ethos.** The developer's goal is output-driven AI-assisted work: use LLM tooling to chew through debt and feature work fast, without sacrificing architectural rigor. GSD's workflow is the scaffolding for that. Pattern proven on v1.0 (60 plans in ~2.5 days, 418 commits).
- **Canonical parts refactor consolidated at v1.0** — `with_for_update` row locks + 10-thread postgres concurrency CI proves the canonical model holds under contention. Forward path is enrichment (per-adapter structured field extraction), not redesign.
- **LLMs still out of scraping pipeline.** Cost-sensitive stance. LLMs enter the product *user-facing* once enrichment unlocks build planners/helpers and the business model justifies API spend. v2 LLM-01..03 sit on top of ENRICH-01..04 deliverables.

## Constraints

- **Tech stack**: Python 3.13 / FastAPI 0.136 + React 19 / TypeScript + PostgreSQL 16 + AWS (App Runner, RDS, S3, SES, EventBridge, CloudFront) — no stack swaps. Major-version dep upgrades require explicit decision.
- **Budget**: Solo dev + AWS low-traffic footprint. LLM API line item enters envelope only when next milestone's user-facing tools (LLM-01..03) ship; until then no LLM spend in production path.
- **Compatibility**: Chrome extension must keep working against modern Chrome (90+) across any backend auth/API changes. `chrome-extension/API_CONTRACT.md` is the contract; drift-guard pytest enforces it.
- **Migrations**: Alembic autogenerate only — no hand-written migrations. Schema changes must remain backwards-compatible with the live DB. Migration DROP-guard rejects `drop_column`/`drop_table`/`drop_constraint` without `# SAFE:` annotation.
- **Testing**: Backend tests run on SQLite in-memory with `pytest -n auto` (default contract). `@pytest.mark.postgres` opt-in tier added in v1.0 for concurrency/migration tests against postgres:16 sidecar. Rate limiting stays off in tests by default.
- **Data**: ~25k real parts in local DB; production DB is the real source of truth. Schema migrations must be safe for both.
- **Security posture**: Target the attainable 90%. Don't regress v1.0 baseline (PyJWT migration, bandit HIGH gate, 2FA/WebAuthn, email verify, CORS, rate-limit) but don't rabbit-hole on hardening.
- **Crawler etiquette**: Respect retailer rate limits / robots; copyright-defensive (rich derived data over raw descriptions). Per-adapter pre-crawl health check + pybreaker circuit breaker enforced.
- **Coverage floors**: Backend `--cov-fail-under=51`; frontend vitest 60/50/50/60. PRs that drop below fail CI.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| First GSD milestone = tech-debt audit + fix-all, not new features | Ensure the next feature milestone (data enrichment / LLM build helpers) is built on a solid foundation. Low-traffic now is the window to pay down debt safely. | ✓ Good — 60/60 reqs satisfied; foundation now solid (v1.0) |
| LLMs excluded from scraping pipeline | Cost-prohibitive pre-business-model. Stay selector-based; reserve LLM budget for future user-facing planner tools once rich data exists. | ✓ Good — selector-based crawl proved out (108 adapters auto-discovered); LLM budget held for v2 user-facing tools |
| Opportunistic UX, no dedicated UX phase | Parts catalog UX is rough but full catalog redesign is a separate milestone. Touching a page for refactor = license to polish it. | ✓ Good — parts-catalog polish landed via Phase 6 Plan 06-06; full UX milestone deferred |
| Security hardening capped at "attainable 90%" | Not B2B SaaS. Baseline hygiene only; no penetration/compliance arc. | ✓ Good — PyJWT migration, bandit HIGH gate, 2FA/WebAuthn unchanged, no scope creep |
| No new user-facing features in v1.0 | Cleanup arc. Keeps scope sharp and prevents tech-debt work from becoming a feature sprint in disguise. | ✓ Good — scope held; next milestone explicitly feature-focused |
| Canonical parts model consolidated, not redesigned | Recent refactor set the direction; finish it (transactional linking, inference maintainability) rather than rebuild. | ✓ Good — `with_for_update` + 10-thread concurrency CI + `lazy="raise"` + 26 ambiguity vectors landed; canonical holds under contention |
| `.planning/codebase/CONCERNS.md` is the debt seed list | Don't re-audit from scratch; phases trace back to that file and add what it missed. | ✓ Good — audit traced back to CONCERNS.md; v1.0 audit catalogued 22 follow-up items, all closed in Phase 7 except 1 operator-gated terraform apply |
| Phase 1 hard prerequisite for Phase 5 (router splits) | No structural changes until characterization tests are CI-green. | ✓ Good — 7 auth + 5 crawler-adapter characterization tests caught zero regressions during the splits |
| Phase 4 must complete before Phase 5 | Avoid concurrent migration + router-split change windows. | ✓ Good — sequencing held; `session.query → select()` sweep + admin/auth splits landed cleanly |
| Phases 2 + 3 may run concurrently | Both additive / low-regression-risk after Phase 1 nets are in. | ✓ Good — concurrent execution worked; no integration conflicts |
| Within Phase 5, admin split precedes auth split | Admin not in Chrome extension critical path; dry run for the split pattern. | ✓ Good — admin split surfaced helpers/_helpers.py pattern reused in auth split |
| `/gsd-plan-milestone-gaps` to handle audit `tech_debt` verdicts | Phase 7 + 8 force-created from audit residue, not from formal REQ-IDs. | ✓ Good — pattern proved valuable; recommend repeating for any tech_debt verdict (catches doc drift, code-review residue, deferred validation) |
| DATA-07 pool override (capacity 100 > floor 50) | Preserve Phase 3 crawler worker formula (DB_POOL_SIZE + DB_MAX_OVERFLOW − API_CONNECTION_RESERVE). | ✓ Good — documented deviation in 04-CONTEXT.md D-18/D-21 |
| AUTH-02 OAuth restructure `/auth/google/*` → `/auth/oauth/google/*` | Aggressive intentional deviation D-10; web frontend migrated same PR; extension critical path unaffected (D-14). | ✓ Good — clean migration, zero rollback events |
| AUTH-03 logout auth-gating | `/api/auth/logout` previously public — gated to authenticated requests during refactor. | ✓ Good — security hardening came along for free |
| Backend coverage baseline = 51% (floor of measured run) | `--cov-fail-under=51` in `backend/pytest.ini`. Avoid setting unrealistically high baseline that flake-blocks future work. | ✓ Good — gate held across 60 plans without false-flagging |
| Frontend coverage thresholds = 60/50/50/60 (D-06 targets) | Reachable via breadth pass on API modules + hooks + contexts + customer pages + admin pages; deferred from Phase 1 to dedicated Phase 8 (20 plans) because 0.43% baseline was far below targets. | ✓ Good — Phase 8 hit thresholds; fail-force proof captured |

## Milestone Sequence

<!-- Check off milestones as they complete. One-liners describe intent, not implementation detail. -->

- [x] M001: v1.0 Tech-Debt Audit + Fix-All — Pay down platform debt across 8 phases / 60 plans; ship Sentry + CloudWatch EMF + canonical parts dedup + concurrency hardening; closed 2026-04-24
- [ ] M002: Data Enrichment + Frontend Design Reset — Structured per-category extraction across all 108 adapters, price-history surfaces (sparkline + detail view + drop alerts), repo-wide reskin on shadcn+Tailwind tokens
  - [x] S01: Schema contract + crawler test infrastructure — SpecRegistry + CategorySpec base + 3 stub models, category_targets opt-in on adapter base, fail-soft ingest validation hook with WARN+EMF, conftest + tracked HTML sample; 23 tests + full crawler suite green (closed 2026-04-24)
  - [x] S02: Universal-field extraction floor — 5 universal extractors (weight/material/finish/warranty/fitment_notes) wired into base-class post-hook, suppress_universal opt-out mechanism, fixtures backfill (closed 2026-04-24)
  - [x] S03: 108-adapter category_targets retrofit — every concrete adapter declares category_targets ClassVar (4 brake / 5 coilover / 2 turbo specialists + 97 ['universal'] catch-alls); compliance_audit script + parametrized pytest gate; 108/108 compliance pinned at PR time (closed 2026-04-25)
  - [x] S04: Re-extraction backfill + admin extraction-health API — chunked/idempotent/resumable `python -m app.crawlers.backfill` CLI (state cursor under `.crawler-state/`, --batch-size/--limit/--source/--resume/--dry-run/--max-failure-rate); GET /api/admin/extraction-health returns DB-derived compliance (108/108 + per-tier `<n>/<n>`), per-tier coverage gradient over UNIVERSAL_FIELD_NAMES, and 7d failure-rate grouped by source from `crawled_pages.parse_status` (no CloudWatch round-trip — D009); 20 tests green (closed 2026-04-25)
  - [x] S05: Price-history aggregation API + perf gate — `app/api/services/part_price_aggregation_service.py` (canonical-coalesce aggregation, 4 SELECTs/batch independent of input size); GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param + retailer filter + `legacy=true` list shim; POST /api/parts/price-history (1-100 IDs → batch min/max/last/trend); typed frontend client (`getPartPriceHistorySummary`, `getBatchPriceHistorySummary`); Locust perf gate split bash/Python with 6-case CSV-fixture pytest gate-on-the-gate (live 10× run deferred to manual invocation); 89 tests green (closed 2026-04-25)
  - [x] S08: Design system substrate — `frontend/src/styles/tokens.css` (HSL-channel dark palette + Tailwind v4 @theme bridge + inline @keyframes/@utility animation utilities); 9 shadcn/Radix primitives under `frontend/src/components/ui/` (button, input, select, tabs, combobox, dialog, dropdown-menu, sheet, toast); dev-only `/_kitchen-sink` page (lazy-factory guard tree-shakes chunk + cmdk/sonner from prod bundle, ~200kB vendor drop); Playwright multi-viewport spec at mobile/tablet/desktop with 0.2% pixel-diff threshold; 6/6 tests passing (closed 2026-04-25). Foundation for S09–S12 reskin.
- [ ] M003: LLM-Assisted Build Tools — Build helper, build planner, part-page summarization, LLM-as-extractor strategy plugged into M002's schema contract; T2 Cloudflare reliability work

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-24 after v1.0 milestone — Tech-Debt Audit + Fix-All shipped (8 phases, 60 plans, 60/60 requirements satisfied, 418 commits over ~2.5 days). Stack landed at FastAPI 0.136.1 + Pydantic 2.13.3 + SQLAlchemy 2.0.49 + Alembic 1.18.4 + Uvicorn 0.45.0 + PyJWT 2.12.1; backend `--cov-fail-under=51` + frontend vitest 60/50/50/60 thresholds enforced; Sentry live (backend + frontend Session Replay); CloudWatch EMF per-adapter crawler metrics + per-adapter parse-failure alarm; 108 crawler adapters auto-discovered with pybreaker; canonical parts model concurrency-hardened with `with_for_update` + 10-thread postgres CI. One operator-gated item carried to v1.0 deploy window: terraform apply for per-adapter parse-failure alarm fan-out (~$10.80/mo CloudWatch delta). Next: `/gsd-new-milestone` for data enrichment + user-facing planner tooling (ENRICH-01..04, LLM-01..03).*
