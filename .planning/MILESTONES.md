# Milestones — CarModPicker

History of shipped milestones. Each entry summarizes the goal, scope, deliverables, and operational state at close. Detailed artifacts (ROADMAP, REQUIREMENTS, audit) live under `milestones/v[X.Y]-*`.

---

## v1.0 — Tech-Debt Audit + Fix-All

**Status:** ✅ SHIPPED 2026-04-24
**Phases:** 8 (1–6 original + 7–8 inserted via `/gsd-plan-milestone-gaps` to close audit residue and SAFE-03)
**Plans:** 60 (all SUMMARY.md present)
**Timeline:** 2026-04-22 → 2026-04-24 (~2.5 days)
**Git range:** `04fc7d3` → `f03f849` (418 commits, 676 files changed, +191,791 / −16,422 LOC)
**Audit:** [`milestones/v1.0-MILESTONE-AUDIT.md`](milestones/v1.0-MILESTONE-AUDIT.md) — 60/60 reqs · 6/6 phases · 8/8 integration · 3/3 E2E flows · status `tech_debt` (no critical blockers)
**Integration check:** [`milestones/v1.0-INTEGRATION-CHECK.md`](milestones/v1.0-INTEGRATION-CHECK.md)

### Delivered

A brownfield FastAPI + React + crawler platform that paid down 8 areas of structural and operational debt before any real traffic — every area resolved (no half-refactors), no external API contract changes, and net-additive observability/test coverage that lets the next milestone (data enrichment + LLM build helpers) build on a sound foundation.

### Key Accomplishments

1. **Safety nets locked in (Phase 1, 8 plans)** — backend coverage floor (`--cov-fail-under=51`); migration DROP-guard; OpenAPI snapshot drift guard; 7 auth + 5 crawler-adapter characterization tests; SQLAlchemy `MetaData(naming_convention=…)`; 3 broken `op.drop_constraint(None, …)` migrations repaired forward-only; weekly Dependabot (pip + npm + github-actions).
2. **Production observability live (Phase 2, 5 plans)** — Sentry SDK 2.x backend (FastAPI + Starlette + SQLAlchemy + Logging integrations + before_send scope processor); `@sentry/react` + Session Replay on-error + ErrorBoundary; CloudWatch EMF per-adapter crawler metrics in `CarModPicker/Crawlers`; Terraform parse-failure alarm (Phase 7 converted composite → per-adapter `for_each`).
3. **Crawler subsystem hardened (Phase 3, 5 plans)** — adapter auto-discovery (108 adapters via `pkgutil.iter_modules`); pybreaker circuit breaker (fail_max=3, reset_timeout=120); per-adapter pre-crawl `robots.txt` health check; bounded `ThreadPoolExecutor` parallelization with per-worker `SessionLocal`; parse-failure email reporting; `car_generations_data.py` 8,412-line Python literal → JSON + `@lru_cache` loader; Pydantic v1 sweep (`@validator` → `@field_validator`); 68-site `Depends(get_logger)` → module-level logger sweep.
4. **DB & parts data integrity (Phase 4, 6 plans)** — N+1 fix in `build_logs.py` via `selectinload(BuildLogPost.author)` with 2-query regression test; 13 FK indexes added across 22 models; `with_for_update()` row locks on link_new_part/reelect_canonical/unlink_part with 10-thread postgres concurrency CI job (postgres:16 sidecar); 304-site `session.query()` → `select()` + `session.scalars()` mechanical sweep; Alembic build-log eager-creation backfill (`gen_random_uuid()`); `lazy="raise"` on hot relationships; `pool_recycle=1800`.
5. **Structural router splits (Phase 5, 4 plans)** — `admin.py` (2,055 LOC) → `admin/` subpackage (stats/jobs/crawlers/db_ops/parts) with parametrized 401/403 coverage; `auth.py` (1,195 LOC) → `auth/` subpackage (core/two_factor/webauthn/oauth/_helpers); `python-jose` → `PyJWT 2.12.1` migration (algorithm explicit on every decode); OpenAPI-driven `chrome-extension/API_CONTRACT.md` generator + drift-guard pytest; `/api/auth/google/*` → `/api/auth/oauth/google/*` restructure (web frontend migrated same PR; extension critical path unaffected).
6. **Frontend modernization + final CI gates (Phase 6 + Phase 8, 26 plans)** — `services/Api.ts` (1,520 LOC) split into 20 per-domain modules under `frontend/src/api/*` with co-located response types; ESLint strict (`@typescript-eslint/no-explicit-any: error` + `no-unsafe-*`); `RouteGroupBoundary` on 4 lazy route groups (admin/authentication/builder/public) with Sentry FallbackRender; Tailwind v3 → v4 gradient codemod; bandit HIGH gate; madge circular-import CI; FastAPI 0.128 → 0.136.1 + Pydantic 2.11 → 2.13.3 + SQLAlchemy 2.0.41 → 2.0.49 + Alembic 1.16 → 1.18.4 + Uvicorn 0.34 → 0.45.0 stack upgrades; Glacier 90d lifecycle on `carmodpicker-production-crawl-data`; SAFE-03 frontend coverage 0.43% baseline → 60/50/50/60 thresholds enforced in `frontend/vitest.config.ts` (Phase 8, 20 plans, fail-force proof captured).

### Phase Index

| # | Name | Plans | Completed | Goal |
|---|------|-------|-----------|------|
| 1 | Safety Nets & CI Hardening | 8/8 | 2026-04-23 | Coverage floors + characterization tests + migration DROP guard |
| 2 | Observability | 5/5 | 2026-04-23 | Sentry + CloudWatch EMF + parse-failure alarm |
| 3 | Non-Breaking Internal Improvements | 5/5 | 2026-04-22 | Crawler hardening + adapter auto-discovery + Pydantic v1 sweep |
| 4 | DB & Parts Hardening | 6/6 | 2026-04-23 | N+1 fix + FK indexes + with_for_update + session.query sweep |
| 5 | Structural Router Splits | 4/4 | 2026-04-23 | admin/auth subpackages + PyJWT migration |
| 6 | Frontend Cleanup & Final CI Gates | 6/6 | 2026-04-23 | ESLint + RouteGroupBoundary + Tailwind v4 + stack upgrades |
| 7 | v1.0 Residue Cleanup & Audit-Drift Sync | 6/6 | 2026-04-24 | Close 22 tech-debt items from audit + Nyquist Wave 0 + doc sync |
| 8 | Frontend Coverage Expansion (SAFE-03) | 20/20 | 2026-04-24 | Lift coverage to 60/50/50/60 + enforce thresholds in CI |

### Key Decisions

- **Tech-debt-first milestone, not feature-first.** Low-traffic now is the window to pay down debt safely; ensures next milestone (data enrichment + LLM build helpers) builds on a sound foundation.
- **Audit + fix-all approach** — every area inventoried, every issue resolved before phase close. No half-refactors.
- **Phase 1 is hard prerequisite for Phase 5** — no structural router splits until characterization tests are CI-green.
- **Phase 4 must complete before Phase 5** — avoid concurrent migration + router-split change windows.
- **Phases 2 + 3 may run concurrently** — both additive/low-regression-risk after Phase 1.
- **Within Phase 5, admin split precedes auth split** — admin is not in Chrome extension critical path; used as dry run for the split pattern.
- **Audit force-created Phase 7 + 8** — `/gsd-plan-milestone-gaps` triggered from `tech_debt` block of audit (despite empty `gaps[]` array). SAFE-03 split to its own Phase 8 because frontend coverage baseline (0.43%) was far below D-06 targets (60/50/50/60).
- **DATA-07 pool override (intentional deviation)** — `pool_size=25 + max_overflow=75` total capacity 100 exceeds REQ floor of 50; retained to preserve Phase 3 crawler worker formula coupling.
- **AUTH-02 OAuth restructure (intentional deviation)** — `/auth/google/*` → `/auth/oauth/google/*` aggressive restructure; web frontend migrated same PR; Chrome extension critical path unaffected.
- **AUTH-03 hardening (intentional deviation)** — `/api/auth/logout` now auth-gated (was previously public).

### Known Deferred Items at Close

**Count: 1** (operator-gated infrastructure apply, deferred to deploy window)

- **Phase 07 Terraform plan review** — `cd terraform && terraform plan -var-file=<env>.tfvars` for per-adapter parse-failure alarm fan-out (~108 alarm creates, ~$10.80/mo CloudWatch cost delta). Marked `autonomous: false` per Plan 07-04; gated to v1.0 deploy window with 24h staging bake (D-58 in 02-HUMAN-UAT.md). All 9/9 automated must-haves on `07-VERIFICATION.md` verified. See STATE.md `## Deferred Items` for full context.

Additionally, the milestone audit catalogued 22 documented follow-up items already closed by Phase 7 (operational bugs, code-review residue, dead-code cleanup, integration advisory A-01, Nyquist Wave 0 close) — see `milestones/v1.0-MILESTONE-AUDIT.md` for the original list.

### Issues Resolved

- 8,412-line Python literal startup overhead (QUAL-01) → JSON + `lru_cache`
- N+1 query in build logs (DATA-01) → 2-query selectinload + regression test
- 304-site `session.query()` legacy API (DATA-06) → `select()` + `scalars()`
- Three broken `op.drop_constraint(None, …)` migrations (SAFE-08) → forward-only repair
- 2,055-line `admin.py` + 1,195-line `auth.py` (ADMIN-01 / AUTH-01) → subpackages
- 1,520-line `services/Api.ts` (FE-04) → 20 per-domain modules
- WR-04 `init_service_accounts.py` `%d` UUID format-specifier crash (Phase 7) → `%s` fix + cold-start regression test

### Technical Debt Incurred

- DATA-07 pool override (preserved Phase 3 coupling; documented in 04-CONTEXT.md D-18/D-21)
- WR-01 backend pytest.ini `testpaths = app/tests` (latent hazard — full 2154-test suite runs; documented)
- 8 legacy `db.query(...)` call sites in `backend/tests/conftest.py` (test helpers; regression guard scoped to `backend/app/` only)
- OAuth cassette recording (Flows 5 + 6) — Google sandbox required; tests skip cleanly until committed
- Alembic migration round-trip CI automation (D-31; reviewer-gated helper script)

---

*For current project status, see [.planning/PROJECT.md](PROJECT.md) and [.planning/ROADMAP.md](ROADMAP.md).*
