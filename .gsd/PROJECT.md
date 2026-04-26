# CarModPicker

## What This Is

CarModPicker is a price-aggregation, parts-discovery, compatibility, and build-planning hub for car enthusiasts. The car modification hobby is fractured — information lives across dozens of retailer sites, forums, Discord servers, and YouTube videos, with no single tool that helps an enthusiast plan, price, and track a full build across multiple projects. CarModPicker aims to be that common flashpoint: a place to discover parts, aggregate prices across retailers, map part-to-car compatibility, and organize builds in shareable lists.

The platform consists of a FastAPI/PostgreSQL backend, a React frontend, and a Chrome extension that scrapes retailer pages. A per-retailer crawler swarm of 108 auto-discovered adapters populates a canonical parts catalog, deduplicated across retailers, with per-retailer price history. The product is live on AWS (App Runner + RDS + S3 + SES + CloudWatch + Sentry) at low traffic — not yet publicly launched at scale. Foundational tech-debt is paid down (v1.0 milestone shipped 2026-04-24); M002 (Data Enrichment + Frontend Design Reset) shipped 2026-04-25 — structured per-category extraction across all 108 adapters, price-history surfaces (sparkline + detail view + drop alerts via SES), and a repo-wide reskin onto shadcn+Tailwind tokens with `components/common/` retired across all pages. M003 (LLM-Assisted Build Tools) is next.

## Core Value

**A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.** If everything else fails — social features, build logs, the Chrome extension, the admin tooling — what must remain true is that an enthusiast can find the parts they're considering, see what they cost across sellers, know whether they fit their car, and organize the ones they want into a build list.

Core Value reaffirmed at M002 close — every shipped capability traces back to it. M002 added **transformative comparative depth via structured extraction + first-class price history** (closes ENRICH-01..04). M003 layers **LLM-assisted build planning** on top of M002's schema contract — same north star, deeper utility.

## Requirements

### Validated

<!-- Shipped and in production. Items inferred from codebase pre-v1.0 are listed first; v1.0 + M002 milestone deliverables follow with milestone reference. -->

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

**M002 (Data Enrichment + Frontend Design Reset — shipped 2026-04-25):**

- ✓ Rich structured extraction from scraped pages (ENRICH-01) — universal-field floor (weight/material/finish/warranty/fitment_notes) auto-merged via base-class post-hook + per-category Pydantic spec models — M002 (S01 + S02)
- ✓ Per-adapter schema contract for structured fields (ENRICH-02) — `SpecRegistry` + `CategorySpec(BaseModel)` with confidence-flag conventions; 108/108 adapters declare `category_targets` ClassVar; `compliance_audit.py` script-as-test — M002 (S01 + S03)
- ✓ Price-history derivation surfaces (ENRICH-03) — `GET /api/parts/{id}/price-history` (retailer + listing breakdowns, windowed) + `POST /api/parts/price-history` (batch); `Sparkline` + `PriceDeltaLine` + `PartDetail` components on every catalog/detail surface — M002 (S05 + S06)
- ✓ Transformative-use positioning (ENRICH-04) — derived comparative data is the user-facing output: per-tier coverage gradient + price-summary cards + drop-alert subscriptions — M002 (S04 + S06 + S07)
- ✓ Frontend design-language reset onto shadcn/Tailwind tokens — `tokens.css` + 9 Radix primitives under `components/ui/` (button/dialog/dropdown-menu/combobox/toast/tabs/input/select/sheet) + 5 layout primitives (card/alert/spinner/pagination/card-info-item); all ~20 pages reskinned; `components/common/` + `components/buttons/` retired with R017 enforcement (vitest grep-guard + ESLint no-restricted-imports rule) — M002 (S08–S12)
- ✓ Price-drop alert subscription end-to-end — `PartPriceAlert` model + Alembic migration + CRUD endpoints + React Email template + alert evaluation hook on observation-write path + frontend management UI; live SES round-trip handed off via S13-UAT.md operator script — M002 (S07)
- ✓ Re-extraction backfill against S3 self-archive — idempotent + resumable `python -m app.crawlers.backfill` CLI with cursor at `backend/.crawler-state/backfill_cursor.json`; 100-part real run at S13/T05 repopulated 97/100 specs (0 failures); operator runs `--resume` post-merge to drain the long-tail (28,085 candidates) — M002 (S04 + S13/T05)
- ✓ Admin extraction-health view distinguishing compliance from coverage — `GET /api/admin/extraction-health` + `/admin/extraction-health` UI returning compliance binary (108/108 + per-tier `<n>/<n>`) + per-tier coverage gradient over universal fields + 7d failure-rate by source — M002 (S04 + S11)
- ✓ Price-history p95 inside budget at 10× current traffic — perf gate at S13/T02: GET p95=95ms (budget <200ms), POST p95=130ms (budget <500ms), 0 failures across 1893 reqs; R036 caching/precompute strategy STAYS deferred per D004 — M002 (S05 + S13/T02)
- ✓ Playwright screenshot tests at three breakpoints — kitchen-sink + build-list + parts catalog + admin + price-alerts + price-history specs green at mobile/tablet/desktop with 24 baselines refreshed at S13/T06 close (`--update-snapshots` sweep for design-system reskin ripple per MEM140) — M002 (S08–S13)

### Active

<!-- Next milestone scope: LLM-assisted build tools, part-page summarization. Sources: REQUIREMENTS.md M003 section + M002 carry-forward. -->

- [ ] **LLM build helper** — suggests parts that fit user's car + compatibility + budget (LLM-01) — now unblocked by M002 schema contract
- [ ] **LLM build planner** — decomposes goals (e.g., "daily driver → track car") into phased parts list (LLM-02) — now unblocked by M002 schema contract
- [ ] **Part-page summarization for research** — LLM-assisted (LLM-03)
- [ ] **T2 Cloudflare reliability work** (R034) — bypass / fallback strategy for the 10 T2 browser-tier adapters; dedicated future cycle
- [ ] **Light theme support** (R035) — deferred carry-forward from M002; dark-only locked at M002 close
- [ ] **AccountAlerts MEM097 self-cancel useEffect bug** — vitest sync mocks hide it; surfaces only at production latency. Fix in next slice that touches AccountAlerts.tsx.
- [ ] **OAuth cassette recording** — record 2 Google OAuth characterization tests with sandbox creds (carry-over from v1.0 — currently skip clean) — bounds: SAFE-06 follow-up
- [ ] **Deploy v1.0 + M002 infrastructure changes** — operator-gated terraform apply for per-adapter parse-failure alarm fan-out (~108 alarm creates, ~$10.80/mo CloudWatch delta) plus M002 backend code (price-alert endpoints, admin extraction-health) — bounds: gated to deploy window with 24h staging bake
- [ ] **Operator runs S13-UAT.md script post-merge** to seal live SES round-trip signal (subscribe → trigger observation → email arrives → unsubscribe)
- [ ] **Operator runs `python -m app.crawlers.backfill --resume` post-merge** to drain the long-tail (28,085 candidates total; first batch of 100 done at S13/T05)

### Out of Scope

<!-- Explicit exclusions for ongoing work, with reasoning. Reviewed at M002 close. -->

- **Deep security hardening (SOC2, pen-testing, compliance arc)** — target the attainable 90%, not the last 10%. Maintain v1.0 baseline (rate-limit, PyJWT, 2FA, email verify, CORS, bandit HIGH gate) but no penetration-testing / SOC2 / compliance arc. Not a B2B SaaS. — *Still valid*
- **LLM-based scraping / extraction pipeline** — cost-prohibitive until business model proves out. Stay selector-based; LLMs reserved for *user-facing* tools (build helpers/planners) downstream of structured-data extraction. M002 proved the selector-based contract holds at 108/108. — *Still valid*
- **Heavy social features / build-log expansion** — build logs stay intentionally thin; social angles are post-MVP and come after rich data + planning tools land. — *Still valid*
- **Mobile app** — web + extension only. Native clients are a separate future arc. — *Still valid*
- **Dedicated parts-catalog UX redesign phase** — superseded by M002 frontend design-language reset (S08–S12). Future UX iteration is opportunistic on the new shadcn substrate. — *Updated at M002 close*
- **Payment / subscription tier rework** — current tier system stands as-is; no tier additions, pricing changes, or billing-provider swaps. — *Still valid*
- **Microservices split for crawler subsystem** — App Runner + ECS Fargate already provides isolation. — *Still valid*
- **Async SQLAlchemy migration** — major refactor; premature at current traffic. Reconsider when read-replica pressure proves out. — *Still valid*
- **Distributed tracing (OpenTelemetry / X-Ray)** — CloudWatch Logs Insights + Sentry covers 90% at current traffic; revisit when end-to-end latency debugging demands it. — *Still valid (deferred from v1.0 OBS)*
- **Caching / precompute layer for price-history endpoints (R036)** — STAYS deferred per D004; S05 perf gate at 10× PASSED with margin (GET p95=95ms vs <200ms budget; POST p95=130ms vs <500ms budget); query-time aggregation is the strategy through M003. — *New at M002 close*

**Removed at v1.0 close:** "New user-facing features" — this exclusion was scoped to the v1.0 cleanup arc only. M002 was a feature milestone (data enrichment + design reset); M003 continues with LLM-assisted build planning.

## Context

- **Post-M002 brownfield, design substrate now solid.** v1.0 (Tech-Debt Audit + Fix-All) shipped 2026-04-24; M002 (Data Enrichment + Frontend Design Reset) shipped 2026-04-25 — 13 slices, 70+ tasks, 20/20 in-scope requirements validated. Codebase: ~81k LOC backend Python (`app/`), ~50k LOC frontend TS/TSX (`src/`) including 9 Radix primitives + 5 layout primitives under `components/ui/` and 6 Playwright e2e specs at 3 viewports; ~3k LOC Chrome extension; ~42k LOC backend tests, ~14k LOC frontend tests. 22+ models with FK indexes; 108 crawler adapters auto-discovered; per-category Pydantic spec contract live with `compliance_audit.py` enforcement.
- **Stack post-M002:** Python 3.13 / FastAPI 0.136.1 + React 19 / TypeScript + PostgreSQL 16 + AWS (App Runner, RDS PG16, S3, SES, EventBridge, CloudFront). Pydantic 2.13.3 + SQLAlchemy 2.0.49 + Alembic 1.18.4 + Uvicorn 0.45.0 + PyJWT 2.12.1 (replaced python-jose). Tailwind v4 with `tokens.css` HSL-channel dark palette + Radix UI primitives (shadcn) + cmdk + sonner. Sentry SDK 2.x backend + `@sentry/react` with Session Replay frontend. Locust for perf gates.
- **CI gates landed:** backend `--cov-fail-under=51` + frontend vitest 60/50/50/60 thresholds; migration DROP-guard; bandit HIGH; madge circular-import; OpenAPI snapshot drift; weekly Dependabot. M002 added: vitest grep-guard + ESLint no-restricted-imports rule for R017 (no imports from retired `components/common/` or `components/buttons/`).
- **Codebase map** lives in `.planning/codebase/` (`ARCHITECTURE.md`, `STACK.md`, `CONCERNS.md`, `CONVENTIONS.md`, `INTEGRATIONS.md`, `STRUCTURE.md`, `TESTING.md`) — was the seed list for v1.0 audit; refresh as M003 surfaces new structural concerns post-design-reset.
- **Production status.** Deployed on AWS at `carmodpicker.com` with a staging subdomain. Low / no external traffic yet — fast iteration is safe, breaking changes don't harm real users. v1.0 paid down structural debt; M002 added structured comparative depth on a stable foundation; M003 layers LLM-assisted user tools on top.
- **Data-at-scale playground.** Local Postgres has ~25k real scraped parts; `carmodpicker-local-crawl` (local) and `carmodpicker-production-crawl-data` (prod) S3 archive buckets let the crawler re-run against stored HTML. Both are first-class tools for iterating on canonical-dedup logic and extraction robustness without hammering retailers. M002 backfill long-tail (28,085 candidates) drains via `python -m app.crawlers.backfill --resume` post-merge.
- **Copyright / transformative-use posture.** Crawler must evolve beyond dumping descriptions; structured, derived, comparative data is the defensible product. M002 landed the schema contract (per-category Pydantic spec models + universal-field floor) + first-class price history (sparkline + detail view + drop alerts). M003 layers LLM-assisted comparative tooling on top.
- **AI-assisted development ethos.** The developer's goal is output-driven AI-assisted work: use LLM tooling to chew through debt and feature work fast, without sacrificing architectural rigor. GSD's workflow is the scaffolding for that. Pattern proven on v1.0 (60 plans in ~2.5 days, 418 commits) and M002 (13 slices in ~1 day).
- **Canonical parts refactor consolidated at v1.0; extraction enrichment consolidated at M002** — `with_for_update` row locks + 10-thread postgres concurrency CI proves the canonical model holds under contention; `SpecRegistry` + 108/108 `category_targets` declaration proves the extraction contract holds across all tiers. Forward path is LLM-assisted user tooling, not redesign.
- **LLMs still out of scraping pipeline.** Cost-sensitive stance. LLMs enter the product *user-facing* at M003 (LLM-01..03) now that M002 enrichment has unlocked the schema contract for build planners/helpers.

## Constraints

- **Tech stack**: Python 3.13 / FastAPI 0.136 + React 19 / TypeScript + PostgreSQL 16 + AWS (App Runner, RDS, S3, SES, EventBridge, CloudFront) — no stack swaps. Major-version dep upgrades require explicit decision.
- **Budget**: Solo dev + AWS low-traffic footprint. LLM API line item enters envelope at M003 (LLM-01..03 user-facing tools).
- **Compatibility**: Chrome extension must keep working against modern Chrome (90+) across any backend auth/API changes. `chrome-extension/API_CONTRACT.md` is the contract; drift-guard pytest enforces it.
- **Migrations**: Alembic autogenerate only — no hand-written migrations. Schema changes must remain backwards-compatible with the live DB. Migration DROP-guard rejects `drop_column`/`drop_table`/`drop_constraint` without `# SAFE:` annotation.
- **Testing**: Backend tests run on SQLite in-memory with `pytest -n auto` (default contract). `@pytest.mark.postgres` opt-in tier added in v1.0 for concurrency/migration tests against postgres:16 sidecar. Rate limiting stays off in tests by default. M002 added Playwright e2e at 3 viewports with visual-regression baselines (refresh via `--update-snapshots` at design-system milestone close per MEM140).
- **Data**: ~25k real parts in local DB; production DB is the real source of truth. Schema migrations must be safe for both.
- **Security posture**: Target the attainable 90%. Don't regress v1.0 baseline (PyJWT migration, bandit HIGH gate, 2FA/WebAuthn, email verify, CORS, rate-limit) but don't rabbit-hole on hardening.
- **Crawler etiquette**: Respect retailer rate limits / robots; copyright-defensive (rich derived data over raw descriptions). Per-adapter pre-crawl health check + pybreaker circuit breaker enforced. M002 added per-category Pydantic validation hook that drops invalid spec blocks fail-soft (ingests part with `specifications=null`, increments `extraction_failure_rate`).
- **Coverage floors**: Backend `--cov-fail-under=51`; frontend vitest 60/50/50/60. PRs that drop below fail CI.
- **Design system**: All new pages must consume `components/ui/*` primitives + `tokens.css` design tokens. No new imports from `components/common/` or `components/buttons/` (R017 enforced via vitest grep-guard + ESLint no-restricted-imports rule).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| First GSD milestone = tech-debt audit + fix-all, not new features | Ensure the next feature milestone (data enrichment / LLM build helpers) is built on a solid foundation. Low-traffic now is the window to pay down debt safely. | ✓ Good — 60/60 reqs satisfied; foundation now solid (v1.0) |
| LLMs excluded from scraping pipeline | Cost-prohibitive pre-business-model. Stay selector-based; reserve LLM budget for future user-facing planner tools once rich data exists. | ✓ Good — selector-based crawl proved out (108 adapters auto-discovered); M002 confirmed at 108/108 contract; LLM budget held for M003 user-facing tools |
| Opportunistic UX, no dedicated UX phase | Parts catalog UX is rough but full catalog redesign is a separate milestone. Touching a page for refactor = license to polish it. | ✓ Good through v1.0 — superseded at M002 close by the dedicated S08–S12 design-language reset (every page reskinned onto shadcn substrate) |
| Security hardening capped at "attainable 90%" | Not B2B SaaS. Baseline hygiene only; no penetration/compliance arc. | ✓ Good — PyJWT migration, bandit HIGH gate, 2FA/WebAuthn unchanged, no scope creep |
| No new user-facing features in v1.0 | Cleanup arc. Keeps scope sharp and prevents tech-debt work from becoming a feature sprint in disguise. | ✓ Good — scope held; M002 explicitly feature-focused |
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
| D004: Caching/precompute layer (R036) opens conditionally on perf gate FAIL | Only build the cache layer if query-time aggregation cannot meet the 10× budget. | ✓ Good — S13/T02 perf gate at 10× PASSED (GET p95=95ms, POST p95=130ms, 0 failures); R036 STAYS deferred; query-time aggregation is the strategy through M003 |
| D011: Close-gate pattern for SES-touching milestones | Live UAT verifies SES path with `+`-suffix fixture inbox; operator runs runnable S##-UAT.md script for human-only round-trip portions. | ✓ Good — established at M002/S13 close; reusable for any future SES-touching milestone |
| Vision-text "111 adapters" reconciled to canonical 108/108 | Per MEM037/MEM122/MEM141 + D-03 — IS_FALLBACK GenericHtmlParser instances per tier excluded from `ADAPTER_REGISTRY` by `__init_subclass__` (three of them, one per tier). | ✓ Good — reconciled in M002-VALIDATION.md so M003 does not inherit the drift |
| MEM140: design-system milestone close needs `--update-snapshots` sweep across nearly every Playwright spec | Reskin ripple from S08 substrate landing affects every spec that takes screenshots indirectly; intermediate slices only refresh baselines for specs they directly touched. | ✓ Good — 24 baselines refreshed at S13/T06; future auto-mode runs do not treat the drift as a blocker |

## Milestone Sequence

<!-- Check off milestones as they complete. One-liners describe intent, not implementation detail. -->

- [x] M001: v1.0 Tech-Debt Audit + Fix-All — Pay down platform debt across 8 phases / 60 plans; ship Sentry + CloudWatch EMF + canonical parts dedup + concurrency hardening; closed 2026-04-24
- [x] M002: Data Enrichment + Frontend Design Reset — Structured per-category extraction across all 108 adapters, price-history surfaces (sparkline + detail view + drop alerts), repo-wide reskin on shadcn+Tailwind tokens; closed 2026-04-25 (13 slices, 70+ tasks, 20/20 in-scope requirements validated)
  - [x] S01: Schema contract + crawler test infrastructure — SpecRegistry + CategorySpec base + 3 stub models, category_targets opt-in on adapter base, fail-soft ingest validation hook with WARN+EMF, conftest + tracked HTML sample; 23 tests + full crawler suite green (closed 2026-04-24)
  - [x] S02: Universal-field extraction floor — 5 universal extractors (weight/material/finish/warranty/fitment_notes) wired into base-class post-hook, suppress_universal opt-out mechanism, fixtures backfill (closed 2026-04-24)
  - [x] S03: 108-adapter category_targets retrofit — every concrete adapter declares category_targets ClassVar (4 brake / 5 coilover / 2 turbo specialists + 97 ['universal'] catch-alls); compliance_audit script + parametrized pytest gate; 108/108 compliance pinned at PR time (closed 2026-04-25)
  - [x] S04: Re-extraction backfill + admin extraction-health API — chunked/idempotent/resumable `python -m app.crawlers.backfill` CLI (state cursor under `.crawler-state/`, --batch-size/--limit/--source/--resume/--dry-run/--max-failure-rate); GET /api/admin/extraction-health returns DB-derived compliance (108/108 + per-tier `<n>/<n>`), per-tier coverage gradient over UNIVERSAL_FIELD_NAMES, and 7d failure-rate grouped by source from `crawled_pages.parse_status` (no CloudWatch round-trip — D009); 20 tests green (closed 2026-04-25)
  - [x] S05: Price-history aggregation API + perf gate — `app/api/services/part_price_aggregation_service.py` (canonical-coalesce aggregation, 4 SELECTs/batch independent of input size); GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param + retailer filter + `legacy=true` list shim; POST /api/parts/price-history (1-100 IDs → batch min/max/last/trend); typed frontend client (`getPartPriceHistorySummary`, `getBatchPriceHistorySummary`); Locust perf gate split bash/Python with 6-case CSV-fixture pytest gate-on-the-gate (live 10× run deferred to manual invocation); 89 tests green (closed 2026-04-25)
  - [x] S06: Price-history frontend surfaces (sparkline + detail view) — `frontend/src/components/charts/Sparkline.tsx` (pure-SVG zero/single/multi rendering, no recharts dep) + `frontend/src/components/parts/PriceDeltaLine.tsx` (trend arrow + min/max range) + `frontend/src/hooks/usePartPriceSummaries.ts` (sorted-key memoized batch fetch with frozen-empty-singleton anti-loop guard); `SparklineCell` lazy per-row component (IntersectionObserver gating + 5-min module TTL cache + in-flight Promise dedupe) wired into PartList table+card layouts; ViewPart.tsx renders new "Price summary (90 days)" block above the legacy chart with stat strip + per-retailer flat-list-or-Tabs (>3 retailers) + 60-day stale "as of" caveat on listings; Playwright e2e spec at three viewports with deterministic page.route mock (excluding Vite source modules), Date.now pinning for stale math, dual network-counter asserting exactly ONE batch POST per page; 39 vitest tests + 15 e2e tests green (closed 2026-04-25). Foundation for S07 alerts + S10 catalog redesign.
  - [x] S07: Price-drop alerts subscription — PartPriceAlert model + Alembic migration + CRUD endpoints + React Email price_drop_alert.html template + alert evaluation hook on observation-write path + AccountAlerts.tsx management UI; vitest + e2e green; live SES round-trip handed off via S13-UAT.md script (operator-pending due to env mutation + inbox access) (closed 2026-04-25)
  - [x] S08: Design system substrate — `frontend/src/styles/tokens.css` (HSL-channel dark palette + Tailwind v4 @theme bridge + inline @keyframes/@utility animation utilities); 9 shadcn/Radix primitives under `frontend/src/components/ui/` (button, input, select, tabs, combobox, dialog, dropdown-menu, sheet, toast); dev-only `/_kitchen-sink` page (lazy-factory guard tree-shakes chunk + cmdk/sonner from prod bundle, ~200kB vendor drop); Playwright multi-viewport spec at mobile/tablet/desktop with 0.2% pixel-diff threshold; 6/6 tests passing (closed 2026-04-25). Foundation for S09–S12 reskin.
  - [x] S09: Build-list view redesign — `frontend/src/components/ui/confirm-dialog.tsx` (new shadcn primitive with destructive/default variants, parent-controlled open state for async confirm flows, loading + error/warning slots, 14 unit tests); `frontend/src/pages/builder/ViewBuildlist.tsx` + `BuildListParts.tsx` + `EditBuildListPartForm.tsx` reskinned onto ui/button + ui/dialog + ui/input + ui/tabs + ui/confirm-dialog (5 dialogs migrated, view-mode toggle on ui/Tabs, phase-row inputs on ui/Input); Playwright `frontend/e2e/build-list.spec.ts` at three viewports with mocked API graph + R020 keyboard assertions (Escape closes, focus rings visible) + chrome-extension-promo deflake; 17 unit + 8 e2e tests green; zero net-new lint errors in slice-touched files (closed 2026-04-25). Pattern for S10/S11 page reskins.
  - [x] S10: Parts catalog redesign — `PartsCatalog.tsx` + `PartsFilterSidebar.tsx` + `PartsActiveFilterChips.tsx` + `PartList.tsx` (row actions) + `AddToBuildListDialog.tsx` reskinned onto ui/button + ui/input + ui/dialog while preserving S06 sparkline+delta integration (one batch POST per page invariant intact), responsive table column-priority logic, and R020 keyboard accessibility; new `frontend/e2e/parts-catalog.spec.ts` with multi-viewport visual regression + AddToBuildList dialog focus/Escape (desktop) + Tab focus assertion (desktop) + 3 baseline PNGs committed; refreshed 6 price-history.spec.ts baselines aligned with the new design system; 6/6 unit + 17/17 e2e green (4 intentional desktop-only skips); zero net-new lint errors in slice-touched files (closed 2026-04-25). Layout chrome (PageHeader, Pagination, Card, SectionHeader, ErrorAlert, LoadingSpinner, VehicleFilterSection) deferred to S12 ripple sweep per MEM107.
  - [x] S11: Admin shell redesign + extraction-health UI — `frontend/src/api/admin.ts` typed `getExtractionHealth()` + 6 exported interfaces mirroring backend `ExtractionHealthResponse` (literal-union `'http' | 'tls' | 'browser'` tier keys for compile-time exhaustiveness); `AdminDashboard.tsx` per-section CTAs reskinned onto ui/Button (default variant, w-full) with 8th `Extraction Health` entry card; new `/admin/extraction-health` route lazy-loaded under admin RouteGroupBoundary in App.tsx + mirrored in App.coverage.test.tsx ALL_ROUTES with drift-guard floor bumped 37→38 (MEM095); new `ExtractionHealth.tsx` page with auth guard + cancellable data fetch + Refresh button (sole ui/Button) + Compliance Card (108/108 hero + per-tier pills) + Coverage Card (per-tier heatmaps with `—` empty-state and alphabetized field iteration for deterministic snapshots) + sortable Failure-Rate table (rate desc via useMemo + "No failures in window" empty-state); inline ErrorAlert with HTTP-status + `crawled_pages.parse_status` hint; new `frontend/e2e/admin.spec.ts` with multi-viewport visual regression at mobile/tablet/desktop (6 PNG baselines) + desktop-only keyboard-focus ring assertion; 596/596 vitest tests green + 35/35 e2e green (10 intentional desktop-only skips); type-check clean (closed 2026-04-25). Layout chrome (Card, PageHeader, SectionHeader, ErrorAlert, LoadingSpinner) deferred to S12 ripple sweep per MEM107/MEM121. Patterns established: MEM119 (admin sub-page structure idiom), MEM120 (four-edit shape for new admin route), MEM122 (108/108 contract, not 111/111 vision text), MEM123 (focus-ring assertion pattern).
  - [x] S12: Repo-wide ripple reskin — every page and inner component (~85 files) swept off `frontend/src/components/common/` + `frontend/src/components/buttons/` onto S08 `ui/*` design system; built 5 new ui/* primitives (card, alert, spinner, pagination, card-info-item) with named-export legacy-shim wrappers; relocated structural infra to `routes/` (RouteGroupBoundary + 3 route guards) + `shell/` (ErrorBoundary + 4 banner components) and 9 non-primitive helpers to `forms/` + `cars/` + `images/` + `filters/` + `tables/` + `buildLists/AddItemTile`; deleted both legacy directories; locked R017 with vitest grep-guard (`__tests__/no-legacy-primitives.test.ts`) + ESLint no-restricted-imports rule on `**/components/{common,buttons}/*`; refreshed kitchen-sink Playwright baselines at 3 viewports; fixed pre-existing vitest test-infra defect (MEM129: `e2e/**` was crashing vitest); type-check 0, 597/597 unit tests pass, 35/35 e2e pass, lint baseline preserved (108 errors == MEM062), grep returns only the self-referential match (closed 2026-04-25). Patterns established: MEM124 (re-export shim for staged multi-task relocations), MEM127 (rm shim → git mv → fix sibling refs preserves git history), MEM132 (formal-variant-first design-system convention), MEM133 (vitest scoping for Playwright coexistence), MEM134 (parent-owned-state Dialog pattern carried from S09), MEM135 (two-layer boundary enforcement). R017 satisfied; R020 preserved across all sweeps. Pattern is general — same shape works for any future retired-module boundary.
  - [x] S13: M002 Final Integration & Close — Closed M002 with the full live-stack close-gate walkthrough: T01 captured live-stack pre-flight + authored S13-UAT.md operator script; T02 re-ran S05 perf gate at 10× and PASSED (GET p95=95ms, POST p95=130ms, 0 failures across 1893 reqs — R019 promoted, R036 STAYS deferred per D004); T03 removed the S05 legacy=true price-history shim from backend + frontend and regenerated the OpenAPI snapshot; T04 captured live compliance-audit + admin extraction-health proof against the running stack (both surfaces report 108/108); T05 kicked off the S04 backfill against the live local stack (97/100 specs repopulated, 0 failures, cursor committed at backend/.crawler-state/backfill_cursor.json for post-merge --resume); T06 ran the final 6/6 close gauntlet (pytest 2800/0, type-check 0, vitest 594, e2e 35 passed at 3 viewports after `--update-snapshots` sweep refreshed 24 baselines per MEM140, lint at MEM062 baseline, compliance audit 108/108) and promoted 14 requirements to validated for a final coverage of 20/20 in-scope; M002-VALIDATION.md verdict=pass; D011 + MEM140 + MEM141 captured (closed 2026-04-25). Live SES UAT round-trip + AdminExtractionHealth UI screenshot are operator-pending per S13-UAT.md script (gated on env mutation + inbox access).
- [ ] M003: Frontend Design System Migration & Polish — Complete the design-system migration M002 started, hard-delete the legacy CSS layer (`@theme` palette + `.glass*` + decorative + animation utilities) so drift can't recur, audit every dense layout for responsive overflow, collapse ViewPart price-block redundancy, polish pass at three breakpoints across every page
- [ ] M004 (planned): LLM-Assisted Build Tools — Build helper, build planner, part-page summarization, LLM-as-extractor strategy plugged into M002's schema contract; T2 Cloudflare reliability work; light theme support

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
*Last updated: 2026-04-25 after M002 close — Data Enrichment + Frontend Design Reset shipped (13 slices, 70+ tasks, 20/20 in-scope requirements validated). Three pillars: (1) per-category Pydantic extraction contract across all 108 adapters with universal-field floor + compliance audit + backfill CLI + admin extraction-health endpoint; (2) price-history first-class on every catalog/detail surface (Sparkline + PriceDeltaLine + PartDetail) + drop-alert subscriptions via SES; (3) full frontend design-language reset onto shadcn/Tailwind tokens (9 ui/* + 5 layout primitives) + components/common/ retired with R017 enforcement. Perf gate at 10× PASSED (GET p95=95ms, POST p95=130ms, 0 failures). M002-VALIDATION.md verdict=pass. Operator follow-ups: run S13-UAT.md script for live SES round-trip + run `python -m app.crawlers.backfill --resume` to drain long-tail (28,085 candidates total; first 100 done at S13/T05). Next: `/gsd-new-milestone` for M003 LLM-Assisted Build Tools (LLM-01..03 + T2 Cloudflare reliability + light theme).*
