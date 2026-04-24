# CarModPicker

## What This Is

CarModPicker is a price-aggregation, parts-discovery, compatibility, and build-planning hub for car enthusiasts. The car modification hobby is fractured — information lives across dozens of retailer sites, forums, Discord servers, and YouTube videos, with no single tool that helps an enthusiast plan, price, and track a full build across multiple projects. CarModPicker aims to be that common flashpoint: a place to discover parts, aggregate prices across retailers, map part-to-car compatibility, and organize builds in shareable lists.

The platform consists of a FastAPI/PostgreSQL backend, a React frontend, and a Chrome extension that scrapes retailer pages. A per-retailer crawler swarm populates a canonical parts catalog, deduplicated across retailers, with per-retailer price history. The product is live on AWS (App Runner + RDS + S3) at low traffic — not yet publicly launched at scale.

## Core Value

**A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.** If everything else fails — social features, build logs, the Chrome extension, the admin tooling — what must remain true is that an enthusiast can find the parts they're considering, see what they cost across sellers, know whether they fit their car, and organize the ones they want into a build list.

## Requirements

### Validated

<!-- Shipped and in production. Inferred from existing codebase (2026-04-21). -->

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
- ✓ Per-retailer crawler adapter system (114 adapters, 3 fetcher tiers) — existing
- ✓ Self-archive bucket + re-scrape against archive for offline tuning — existing
- ✓ Chrome extension (scrape retailer pages → POST to API; popup auth) — existing
- ✓ AWS deployment: App Runner + RDS PG16 + S3 + SES + EventBridge + CloudFront — existing
- ✓ Rate limiting + structured logging (request/user context) — existing
- ✓ `BaseEndpointRouter` / `BaseCRUDService` / `EndpointRegistry` abstractions — existing

### Active

<!-- Current scope: a systemic tech-debt audit + fix-all milestone across 8 areas. -->

- [ ] Auth / account-flow refactor — break up oversized `auth.py`, resolve debt from 2FA/WebAuthn/OAuth accretion
- [ ] Crawler system hardening — adapter auto-discovery, parse-failure alerting, parallelization, retry/health-check, archive reuse patterns
- [x] Observability & logging audit — structured logs, crawler metrics, request tracing, production monitoring hooks (Phase 2: Sentry backend+frontend, CloudWatch EMF, parse-failure alarm, log-context regression guard)
- [ ] DB / migrations / perf pass — fix N+1 in build logs, add missing indexes, audit migration hygiene, index join keys, tune connection pool
- [ ] Parts & canonical dedup consolidation — transactional part linking, inference engine maintainability, finish what the canonical refactor started
- [ ] Frontend structure cleanup — pages/components organization, API client consistency, context usage, type-safety gaps
- [ ] Test coverage & CI gates — raise backend + frontend coverage, enforce pyright/eslint/bandit, add concurrency + adapter-integration tests
- [ ] General code-quality sweep — admin.py split (2,055 lines), car_generations_data.py (8,412 lines) load strategy, dead code, duplication, Base* compliance
- [ ] Opportunistic UX polish — when a page is refactored, pull its UX up to the quality bar of the home page (parts catalog is the known rough spot)

### Out of Scope

<!-- Explicit exclusions for this milestone, with reasoning. -->

- **Deep security hardening** — target the attainable 90%, not the last 10%. Maintain current baseline (rate-limit, JWT, 2FA, email verify, CORS) but no penetration-testing / SOC2 / compliance arc. Not a B2B SaaS.
- **LLM-based scraping / extraction** — cost-prohibitive until a business model proves out. Stay selector-based for this milestone; reserve LLMs for future user-facing tools (build helpers/planners) once rich structured data exists.
- **New user-facing features** — this is a cleanup arc. No new product surface this milestone. New features belong to the next milestone once the foundation is solid.
- **Heavy social features / build-log expansion** — build logs stay intentionally thin; social angles are post-MVP and come after rich data + planning tools land.
- **Mobile app** — web + extension only. Native clients are a separate future arc.
- **Dedicated parts-catalog UX redesign phase** — UX work is opportunistic (touched-page-gets-polished), not a dedicated design phase. Full catalog UX redesign is a later milestone.
- **Payment / subscription tier rework** — current tier system stands as-is; no tier additions, pricing changes, or billing-provider swaps.

## Context

- **Brownfield.** Substantial existing codebase (25+ models, 114 crawler adapters, Chrome extension, Terraform-managed AWS). Codebase map lives in `.planning/codebase/` (`ARCHITECTURE.md`, `STACK.md`, `CONCERNS.md`, `CONVENTIONS.md`, `INTEGRATIONS.md`, `STRUCTURE.md`, `TESTING.md`) and is the authoritative starting point for this milestone.
- **Production status.** Deployed on AWS at `carmodpicker.com` with a staging subdomain. Low / no external traffic yet — fast iteration is safe, breaking changes don't harm real users. Treat this as the last chance to pay down debt before the platform sees traction.
- **Existing tech-debt catalog.** `.planning/codebase/CONCERNS.md` already inventories major debt items (oversized files, N+1 query, crawler parse-failure visibility, CORS/JWT notes, perf bottlenecks, missing metrics, test gaps). This milestone's phases should track back to that document.
- **Data-at-scale playground.** Local Postgres has ~25k real scraped parts; the self-archive bucket lets the crawler re-run against stored HTML. Both are first-class tools for iterating on canonical-dedup logic and extraction robustness without hammering retailers.
- **Copyright / transformative-use posture.** The crawler must evolve beyond dumping descriptions; structured, derived, comparative data is the defensible product. Any crawler work this milestone should push in that direction even while staying selector-based.
- **AI-assisted development ethos.** The developer's goal is output-driven AI-assisted work: use LLM tooling to chew through debt fast, without sacrificing architectural rigor. GSD's workflow is the scaffolding for that.
- **Canonical parts refactor (recent).** Already a step toward dedup across retailers; the foundation is laid but not finished. This milestone consolidates rather than redesigns it.
- **No LLMs in production path (yet).** Cost-sensitive stance. LLMs enter the product once rich data unlocks user-facing tools (build planners/helpers) and the business model justifies API spend.

## Constraints

- **Tech stack**: Python 3.13 / FastAPI 0.128 + React 19 / TypeScript + PostgreSQL 16 + AWS (App Runner, RDS, S3, SES, EventBridge, CloudFront) — no stack swaps this milestone.
- **Budget**: Solo dev + AWS low-traffic footprint. No LLM API line item. Any infra additions must fit the same envelope.
- **Compatibility**: Chrome extension must keep working against modern Chrome (90+) across any backend auth/API changes.
- **Migrations**: Alembic autogenerate only — no hand-written migrations. Schema changes must remain backwards-compatible with the live DB.
- **Testing**: Backend tests run on SQLite in-memory with `pytest -n auto`. Any backend refactor must keep that contract. Rate limiting stays off in tests by default.
- **Data**: ~25k real parts in local DB; production DB is the real source of truth. Schema migrations must be safe for both.
- **Security posture**: Target the attainable 90%. Don't regress current auth/rate-limit/CORS baseline, but don't rabbit-hole on hardening.
- **Crawler etiquette**: Respect retailer rate limits / robots; copyright-defensive (rich derived data over raw descriptions).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| First GSD milestone = tech-debt audit + fix-all, not new features | Ensure the next feature milestone (data enrichment / LLM build helpers) is built on a solid foundation. Low-traffic now is the window to pay down debt safely. | — Pending |
| LLMs excluded from scraping pipeline this milestone | Cost-prohibitive pre-business-model. Stay selector-based; reserve LLM budget for future user-facing planner tools once rich data exists. | — Pending |
| Opportunistic UX, no dedicated UX phase | Parts catalog UX is rough but full catalog redesign is a separate milestone. Touching a page for refactor = license to polish it. | — Pending |
| Security hardening capped at "attainable 90%" | Not B2B SaaS. Baseline hygiene only; no penetration/compliance arc this milestone. | — Pending |
| No new user-facing features this milestone | Cleanup arc. Keeps scope sharp and prevents tech-debt work from becoming a feature sprint in disguise. | — Pending |
| Canonical parts model consolidated, not redesigned | Recent refactor set the direction; finish it (transactional linking, inference maintainability) rather than rebuild. | — Pending |
| Existing `.planning/codebase/CONCERNS.md` is the debt seed list | Don't re-audit from scratch; phases trace back to that file and add what it missed. | — Pending |

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
*Last updated: 2026-04-23 after Phase 6 complete — frontend cleanup & final CI gates (ESLint strict typing rules at error, RouteGroupBoundary on 4 lazy route groups with Sentry FallbackRender + drift-guard coverage test, services/Api.ts split into 20 per-domain modules under frontend/src/api/*, FastAPI 0.136.1 + Pydantic 2.13.3 + SQLAlchemy 2.0.49 + Alembic 1.18.4 + Uvicorn 0.45.0 + python-jose→PyJWT migration, bandit HIGH gate, madge circular-dep CI, Tailwind v4 gradient codemod, Glacier lifecycle on crawl-data S3 bucket; 5/5 success criteria verified mechanically; 06-HUMAN-UAT.md Sections 1-3 operator-pending — chrome-extension smoke, Sentry route-group tags in staging, Terraform apply confirmation. Milestone v1.0 complete.)*
