# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Tech-Debt Audit + Fix-All

**Shipped:** 2026-04-24
**Phases:** 8 | **Plans:** 60 | **Commits:** 418
**Timeline:** 2026-04-22 → 2026-04-24 (~2.5 days, ~60 hours wall-clock)
**Files changed:** 676 (+191,791 / −16,422 LOC)
**Audit verdict:** `tech_debt` (60/60 reqs · 6/6 phases · 8/8 integration · 3/3 E2E flows; no critical blockers)

### What Was Built

- **Safety nets** — backend `--cov-fail-under=51`, frontend vitest CI runs, migration DROP-guard, OpenAPI snapshot drift guard, 7 auth + 5 crawler-adapter characterization tests, MetaData naming convention, weekly Dependabot
- **Production observability** — Sentry SDK 2.x backend (FastAPI/SQLAlchemy/before_send) + frontend (`@sentry/react` + Session Replay + RouteGroupBoundary on 4 lazy route groups), CloudWatch EMF per-adapter crawler metrics, per-adapter parse-failure alarm
- **Crawler hardening** — 108 adapters via `pkgutil.iter_modules` auto-discovery, pybreaker circuit breaker (fail_max=3, reset_timeout=120), per-adapter `robots.txt` health check, ThreadPoolExecutor parallelization, parse-failure email reporting
- **DB & parts integrity** — N+1 fix in build logs (selectinload + 2-query regression test), 13 FK indexes, `with_for_update()` row locks + 10-thread postgres concurrency CI, 304-site `session.query → select()` sweep, build-log eager-creation backfill, `lazy="raise"` on hot relationships
- **Structural router splits** — `admin.py` (2,055 LOC) → `admin/` subpackage, `auth.py` (1,195 LOC) → `auth/` subpackage, python-jose → PyJWT 2.12.1 migration, OpenAPI-driven `chrome-extension/API_CONTRACT.md` with drift guard
- **Frontend modernization** — `services/Api.ts` (1,520 LOC) → 20 per-domain modules, ESLint strict (`no-explicit-any`, `no-unsafe-*`), Tailwind v3→v4 codemod, bandit HIGH gate, madge circular-import CI, FastAPI 0.136 + Pydantic 2.13 + SQLAlchemy 2.0.49 + Alembic 1.18 + Uvicorn 0.45 stack upgrades, frontend coverage 0.43% → 60/50/50/60 thresholds enforced

### What Worked

- **Phase 1 hard-prerequisite gate held its weight.** The 7 auth + 5 crawler-adapter characterization tests (Phase 1 Plans 01-06 / 01-07) caught zero regressions during the Phase 5 router splits — confirming the gate's design intent. Investing in characterization before structural change is the right sequencing.
- **Two-track parallelism (Phases 2 + 3 concurrent).** Both phases were additive / low-regression-risk after Phase 1 nets landed; running them concurrently saved a full phase-cycle without integration conflict.
- **Wave-based dependency planning within phases.** Phase 4's 6 plans were strict-serial (Wave 1 → Wave 6) because of file-overlap on `build_logs.py`, `part_linker_service.py`, and models. Phase 8's 20 plans had Wave 0 (shared infra) → Wave 1 (6 parallel API clusters) → Wave 2 → Wave 3 → Wave 4 → Wave 5 — explicit wave declarations made the dependency graph legible and prevented merge thrash.
- **Audit-driven Phase 7 + 8 force-creation.** `/gsd-plan-milestone-gaps` from the `tech_debt` block of `v1.0-MILESTONE-AUDIT.md` (despite empty `gaps[]` array) caught 22 follow-up items that would otherwise have shipped as silent debt: `init_service_accounts.py %d→%s` UUID crash, `reelect_canonical` deadlock potential, `build_lists.py` filter duplication, dead `common_patterns.py` helpers, `terraform/monitoring.tf:216` per-adapter for_each TODO, Nyquist Wave 0 doc closure, REQUIREMENTS/ROADMAP doc drift sync.
- **Splitting SAFE-03 to its own Phase 8.** Frontend coverage baseline (0.43%) was far below D-06 targets (60/50/50/60). Trying to land it inside Phase 1 would have either gated the entire milestone or shipped diluted thresholds. Deferring to Phase 8 (20 plans, breadth-pass test-writing) let Phase 1 close on time and produced a clean threshold landing.
- **Deferred work tracked explicitly in `## Deferred Items` of STATE.md.** OAuth cassette recording (sandbox creds required), DATA-07 pool override, AUTH-02 OAuth restructure, AUTH-03 logout gating — all surfaced as documented intentional deviations rather than silent debt.
- **Wave-end SUMMARY.md frontmatter (`provides:` lists)** gave per-plan one-line claims that fed the phase-level VERIFICATION.md and the milestone audit cleanly.
- **Mechanical sweeps caught real bugs.** The 304-site `session.query → select()` sweep (Plan 04-04) modernized the entire codebase in a single PR; the 68-site logger DI sweep (Plan 03-05) caught silent decorator inconsistencies.
- **Test pyramid — SQLite default + postgres opt-in.** Adding `@pytest.mark.postgres` for concurrency/migration tests against a `postgres:16` sidecar (Plan 04-05) preserved the fast `pytest -n auto` SQLite default while gaining true row-lock semantics where they matter.

### What Was Inefficient

- **REQUIREMENTS.md traceability table drift.** Most rows stayed `Pending` even after VERIFICATION.md reports came in green. Required Phase 7 Plan 07-06 to flip 59 rows in a documentation-sync pass. Future fix: have `/gsd-execute-phase` (or `gsd-sdk query phase.complete`) flip traceability rows automatically when SUMMARY.md `provides:` lists claim a REQ-ID.
- **UAT frontmatter status labels never flipped.** Phases 02/03/05/06 HUMAN-UAT files had inconsistent or missing `status:` frontmatter even after all checkboxes were `[x]`. The pre-close artifact audit flagged 5 phases as UAT gaps that were actually 0-pending. Required manual edits before `/gsd-complete-milestone`. Future fix: standardize `status: complete` write at UAT close.
- **ROADMAP.md doc drift between phase-progression and ROADMAP checkboxes.** Phases 7 and 8 stayed `[ ]` in ROADMAP.md and "In progress" in the Progress table even after every plan SUMMARY landed. Same root cause as REQUIREMENTS drift.
- **Per-plan velocity rows in STATE.md degraded into garbage.** Several rows had duplicated phrases ("Phase Phase…", "tasks tasks", "files files"). Indicates a brittle string-template path in the GSD execution layer. Future fix: switch to structured row append.
- **Bare `gsd-sdk query milestone.complete` is a thin wrapper.** It only renames phase directories — does NOT archive ROADMAP/REQUIREMENTS, create MILESTONES.md, or update STATE.md (despite the workflow doc claiming it does). Required manual archival. Future fix: workflow doc and CLI need to converge.
- **Phase 8's 20-plan breadth pass had high overhead.** Each plan re-loaded shared mock factories from `test-mocks.ts` / `test-utils.tsx` / `test/mocks/admin/` independently. A single combined plan with parallel sub-agents probably would have shipped in fewer plan cycles.

### Patterns Established

- **GSD audit + force-create pattern for tech-debt closures.** When `/gsd-audit-milestone` returns `tech_debt` (not `gaps_found`), run `/gsd-plan-milestone-gaps` from the audit's tech-debt block to surface a closure phase. This catches doc drift, code-review residue, and operator-gated deferrals that would otherwise leak into the next milestone.
- **Characterization-first sequencing.** Any milestone touching auth, payments, crawlers, or canonical-data invariants gets a Phase 1 that lands characterization tests + CI gates + drift guards before any structural work begins.
- **Decimal phase numbering for urgent insertions.** `2.1`, `5.1` for hotfixes that need to slot between integer phases without renumbering downstream work. Used pre-emptively in roadmap design even when no decimal phase shipped.
- **Wave declarations inside phases.** `Wave 1 → Wave 2 → …` blocks in plan-level Notes give the executor a clean dependency graph and let parallel-safe waves run concurrently.
- **`@pytest.mark.postgres` opt-in tier.** SQLite default + postgres sidecar for concurrency/migration tests. Added as a CI matrix path, not a default — keeps developer feedback loop fast.
- **OpenAPI-driven contract docs.** `chrome-extension/API_CONTRACT.md` is regenerated from the live OpenAPI schema with a drift-guard pytest. Pattern reusable for any external contract surface.
- **`# SAFE: <reason>` annotation discipline.** Migration DROP-guard + downgrade safety annotations made it impossible to ship a destructive op silently. Pattern applies to any future "irreversible op" (cache flush, S3 delete, etc.).
- **`provides:` / `requires:` SUMMARY frontmatter for dependency-aware planning.** Gives the next plan's discuss/plan phases a structured handle on what's available without re-reading prior plan files.
- **Audit doc as `gaps[]` + `tech_debt[]` two-bucket split.** Lets the audit pass with operator-gated deferrals (`tech_debt`) without forcing a milestone-block.

### Key Lessons

1. **Doc-state drift compounds — bake doc-flip into the execution path.** REQUIREMENTS.md traceability rows, ROADMAP.md checkboxes, UAT status frontmatter all drifted out of sync with VERIFICATION.md reports. The fix isn't a closing sweep; it's making the executor flip them as plans land. Lesson scoped: any "documentation reflects state" surface must be writable by the executor, not the human.
2. **Audit `tech_debt` verdict is a strong signal, not a soft one.** v1.0's audit had `gaps[] = []` but 22 tech-debt items. Without `/gsd-plan-milestone-gaps`, all 22 would have shipped as silent debt and been re-discovered painfully during the next milestone's planning. Treat `tech_debt` as a force-creation trigger, not an FYI.
3. **Splitting an oversized requirement to its own phase is rarely wrong.** SAFE-03 (frontend coverage) split to Phase 8 was the right call — trying to land it in Phase 1 would have either gated the milestone or diluted the thresholds. Heuristic: if a requirement's baseline is more than 10× off-target, it earns its own phase.
4. **Operator-gated infra deferrals belong in the audit, not the failure case.** The terraform per-adapter alarm fan-out (Phase 7 Plan 07-04) was never going to apply during the milestone — it's a deploy-window action with a 24h staging bake. Modeling it as `autonomous: false` + audit `tech_debt` (not `gaps_found`) was the right framing; preserved milestone close while keeping the operator action visible.
5. **Stack patch upgrades ride on existing guards.** FastAPI 0.128 → 0.136.1 + Pydantic 2.11 → 2.13.3 + SQLAlchemy 2.0.41 → 2.0.49 + Alembic 1.16 → 1.18.4 + Uvicorn 0.34 → 0.45.0 (Plans 06-04 + 06-05) shipped with zero new tests because they rode on Phase 3 Pydantic-v1 catch_warnings + Phase 1 OpenAPI snapshot + SAFE-06 auth characterization + Plan 04-06 Alembic round-trip canary. Lesson: invest in baseline guards early; cheap upgrades follow.
6. **Avoid "boil the ocean" plans.** Phase 8 had 20 plans for a single REQ-ID. The breadth pass worked but had repetitive infrastructure setup. For future big-coverage pushes, consider 1 infra plan + 1 parallelizable test-writing plan with N sub-agents instead of N sequential plans.
7. **`/gsd-complete-milestone` workflow doc and CLI need to stay aligned.** The doc described `milestone.complete` CLI as doing archival + MILESTONES.md + STATE.md updates, but the installed CLI (`@gsd-build/sdk` v0.1.0) only renames phase directories. Either align the doc to current CLI capability or land the missing CLI features.

### Cost Observations

- **Model mix:** Not instrumented this milestone. (Recommend `/gsd-session-report` instrumentation for v2.)
- **Sessions:** Single sustained session per phase typical; 8 phases ≈ 8–12 sessions.
- **Wall-clock vs. AI-time:** ~2.5 days wall-clock, but most plan-level cycles ran in single-digit minutes once the Phase 1 nets were in place. The audit + Phase 7 closure + Phase 8 breadth pass dominated time.
- **Notable:** Phases 2 + 3 ran concurrently and saved approximately one full phase-cycle of wall-clock. Phase 4's strict-serial 6-wave structure was the wall-clock bottleneck inside the milestone (file-overlap forced serialization).

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Process Change |
|-----------|--------|-------|---------------------|
| v1.0 | 8 (1–6 + tech-debt 7–8) | 60 | Established characterization-first Phase 1; introduced `/gsd-plan-milestone-gaps` for `tech_debt` audit verdicts; introduced `@pytest.mark.postgres` opt-in tier; split SAFE-03 to its own Phase 8 when baseline was >10× off target |

### Cumulative Quality

| Milestone | Tests (backend) | Tests (frontend) | Coverage (backend) | Coverage (frontend) | Zero-Dep Additions |
|-----------|-----------------|------------------|--------------------|---------------------|--------------------|
| v1.0 | ~2,363 passing | 76+ vitest | `--cov-fail-under=51` enforced | 60/50/50/60 enforced | pybreaker, vitest, @sentry/react, madge, bandit, dependabot, sentry-sdk[fastapi], PyJWT |

### Top Lessons (Verified Across Milestones)

*Single-milestone retrospective — top lessons not yet cross-verified. Re-evaluate after next milestone.*

1. *(Pending second milestone for verification.)*
