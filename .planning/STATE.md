---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 6 context gathered
last_updated: "2026-04-24T01:12:56.754Z"
last_activity: 2026-04-23 -- Phase 05 execution started
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 28
  completed_plans: 28
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.
**Current focus:** Phase 05 — structural-router-splits

## Current Position

Phase: 05 (structural-router-splits) — EXECUTING
Plan: 1 of 4
Status: Executing Phase 05
Last activity: 2026-04-23 -- Phase 05 execution started

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 24
- Average duration: — min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |
| 03 | 5 | - | - |
| 02 | 5 | - | - |
| 04 | 6 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-safety-nets-ci-hardening P02 | 25 | 3 tasks | 4 files |
| Phase 01-safety-nets-ci-hardening P03 | 30 | 3 tasks | 32 files |
| Phase 01-safety-nets-ci-hardening P04 | 35 | 3 tasks | 4 files |
| Phase 01-safety-nets-ci-hardening P07 | 55 | 3 tasks | 16 files |
| Phase 01-safety-nets-ci-hardening P08 | 1 | 1 tasks | 1 files |
| Phase 04-db-parts-hardening P04-01 | 15 | 3 tasks | 11 files |
| Phase Phase 04-db-parts-hardening PP04-02 | 20 | 3 tasks tasks | 5 files files |
| Phase 04-db-parts-hardening P04-03 | 5 | 2 tasks | 4 files |
| Phase 04-db-parts-hardening P04 | 65 | 2 tasks tasks | 55 files files |
| Phase 04-db-parts-hardening P04-05 | 8min | 3 tasks | 6 files |
| Phase 04-db-parts-hardening P06 | 9min | 4 tasks tasks | 8 files files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Phase 1 is HARD prerequisite for Phase 5. No structural router splits until characterization tests are CI-green.
- Roadmap: Phase 4 must complete before Phase 5 — avoid concurrent migration + router-split change windows.
- Roadmap: Within Phase 5, admin split precedes auth split. Admin is not in Chrome extension critical path; use as dry run.
- Roadmap: Phase 2 (Observability) and Phase 3 (Non-Breaking Internal) may run concurrently — both are additive/low regression risk after Phase 1.
- Roadmap: Coverage note — REQUIREMENTS.md header stated 56 requirements but 60 are actually defined. All 60 mapped; no orphans.
- SAFE-08: Branch B (forward-only repair) chosen because all three broken revisions were already applied on prod
- SAFE-08: Third FK constraint at repair migration downgrade time is parts_part_manufacturer_id_fkey on parts (not global_parts_brand_id_fkey — renamed by c1f3e8a92d45 and d2e9c4a1f57b)
- SAFE-04: All 82 pre-existing unannotated downgrade() destructive ops annotated with downgrade-reversal SAFE comment to make checker exit 0 on current tree
- SAFE-04: Two distinct annotation regexes — SAFE_ANNOTATION_RE anchored to line start (preceding-line), INLINE_SAFE_RE unanchored (same-line) — prevents docstring-embedded SAFE tokens from satisfying guard (T-03-02 defense)
- Option C: SAFE-03 frontend vitest threshold enforcement deferred to plan 01-09; vitest thresholds staged as commented D-06 literals in frontend/vitest.config.ts
- Backend coverage baseline set at 51% (floor of measured run); --cov-fail-under=51 in backend/pytest.ini
- SAFE-07: Swapped tier2_browser adapter picks (summitracing, ecstuning) for tier0/tier1 alternatives — user confirmed tier2_browser is currently non-functional
- SAFE-07: Final 5 adapter picks: briantooleyracing, amsperformance, subispeed (tier0), texasspeed, cobbtuning (tier1) — sourced from carmodpicker-local-crawl MinIO bucket
- SAFE-07: D-21 corrected — crawl archives in carmodpicker-local-crawl (local) and carmodpicker-production-crawl-data (prod), not carmodpicker-prod-user-images
- SAFE-10: No ignore block in dependabot.yml — majors auto-raised individually per Dependabot default (RESEARCH Pitfall 6)
- SAFE-10: Single npm entry with directories: [/frontend, /chrome-extension] — schema v2 multi-dir, not two separate entries
- Plan 04-01: FK audit scope grew from 9 confirmed FKs to 13 during systematic sweep (added BuildLogPost.user_id, BugReport.assigned_to, BuildListPhase.build_list_id, CrawlerAdapterConfig.default_category_id)
- Plan 04-01: Discarded non-index autogenerate output (4 ops: categories UNIQUE rename + 3 FK convention-name re-adds) per D-13/Pitfall 10 — forward-only historic-name deferrals
- Plan 04-01: pool_recycle=1800 literal committed; pool_size=25 + max_overflow=75 + API_CONNECTION_RESERVE=20 preserved per Phase 3 D-14 crawler formula coupling
- Plan 04-02: gen_random_uuid() chosen over Python-side uuid7() callable per Pitfall 2 — Python callable in raw INSERT fires once at statement-prepare, tripping uq_build_logs_build_list_id on row 2
- Plan 04-02: downgrade() is deliberate no-op with SAFE-04 annotation — reversing backfill would destroy user posts captured against backfilled rows (D-26)
- Plan 04-02: Retained db.query(...).first() lines in both deleted branches — plan 04-04 owns the session.query → select() sweep
- Plan 04-02: CREATE EXTENSION pgcrypto NOT prepended — gen_random_uuid() verified on local Postgres 16 without extension; prod RDS 16 verification deferred to operator per VALIDATION.md Manual-Only Verifications
- Plan 04-03: Option Y (inline select in regression test) chosen over Option X (new build_log_service.py helper) — no existing service module justifies premature abstraction
- Plan 04-03: read-path only — create_build_log_post (line 221) and update_build_log_post (line 289) single-author fetches NOT touched per plan directive line 417; plan 04-04 sweep owns them
- Plan 04-03: db.scalar(select(func.count())) returns Optional[int]; coerced with `or 0` to satisfy create_paginated_response non-optional total param — COUNT(*) semantically never returns NULL
- Plan 04-03: load_only(User.id, User.username, User.image_urls) NOT applied per D-35 Claude's Discretion — matches old N+1 code's full-row fetch; zero OpenAPI drift; future optimization pass can add it
- Plan 04-04: Helper-function signature migration (common_patterns / common_operations / pagination_utils) — accept Select[Any] at entry, gain db: Session param at terminal points (get_paginated_response / get_total_count / paginate_query). Enables clean Select-end-to-end code paths in callers without double conversion.
- Plan 04-04: Bulk DML migrated to sql_delete/sql_update + execution_options(synchronize_session=False) for admin /cars/delete-all and /part-manufacturers/delete-all — preserves table-level DELETE/UPDATE semantics without per-row ORM cascade.
- Plan 04-04: with_entities(Model.id) → Select.with_only_columns(Model.id) for two-query id-then-hydrate pagination pattern in build_lists.py and parts.py. Preserves sort-then-fetch semantics exactly.
- Plan 04-04: COUNT(*) consistently rewritten to select(func.count()).select_from(Model).where(...) per Pitfall 5; coerced with or 0 to satisfy non-Optional[int] callers (db.scalar returns Optional[int] but COUNT(*) semantically never returns NULL).
- Plan 04-05: unlink_part lock scope covers subject + canonical + full sibling set per D-05 — naive subject-only lock would leave reelect_canonical free to mutate stale siblings
- Plan 04-05: @pytest.mark.postgres marker + postgres_engine session-scoped fixture + per-test unique gtin keys chosen over BEGIN+ROLLBACK isolation — ROLLBACK defeats pessimistic-lock semantics because locks commit with the transaction
- Plan 04-05: CI psql CREATE DATABASE retry loop (5 attempts × 2s backoff) per INFO 12 — services.postgres healthcheck catches most readiness issues but first-boot parameter-group races can still surface
- Plan 04-05: docker-compose.test.yml uses port 5433 (not 5432) to avoid colliding with backend/docker-compose.yml dev Postgres — local devs can run both simultaneously
- Plan 04-06: No caller changes needed for lazy='raise' — audit found zero lazy consumers of build_list_parts/build_list_phases in app/, and BuildLogPost.author was already paired with selectinload by plan 04-03
- Plan 04-06: test_lazy_raise_callers.py uses first-access trigger (WARN 10) — no db_session.expire() hack; freshly-fetched entity without selectinload is already in 'unloaded' state
- Plan 04-06: AMBIGUOUS_STANDALONE_CODES docstring placed AFTER the frozenset (dangling-docstring idiom) to preserve frozenset literal contents
- Plan 04-06: 26 ambiguity vectors committed (>plan floor of 20) — 7 positive + 19 negative covering B4/B6/B8/B16/HI/NA/EVO/D2/V10/P1/HD/S1/OS/MD/XT/BP/RS/V/0.42
- Plan 04-06: Integration merge case seeds concrete DBPartListing row so find_part_by_product_url returns canon_b while find_part_by_gtin returns canon_a — exercises multi-canonical merge path on SQLite per WARN 7
- Plan 04-06: Round-trip script REVISION arg is REQUIRED (INFO 13) — silent head-defaulting disabled to force explicit reviewer-verifiable intent
- Plan 04-06: Final-cleanup task (stale imports) audit returned zero unused imports — Wave 4 sweep landed clean; no cleanup commit created

### Pending Todos

None yet.

### Blockers/Concerns

- **Backend coverage baseline measured and committed (plan 01-04).** `--cov-fail-under=51` landed in backend/pytest.ini (commit bbb5b22).
- **Postgres Docker test environment** — Phase 4 migration testing needs a `docker-compose` step for Postgres-specific CI validation. Decide at Phase 4 planning time.
- **`lazy="raise"` scope** — Full audit of all `relationship()` declarations across 22+ models needed at Phase 4 planning.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Phase 01 | SAFE-03: frontend vitest threshold enforcement | Deferred (target: plan 01-09): frontend coverage threshold enforcement | 2026-04-22 |
| Phase 01 | OAuth cassette recording: 2 OAuth characterization tests (signin, link) currently skip because cassettes are absent. A developer with Google sandbox creds must record them per 01-06-SUMMARY.md instructions, then confirm both tests move from SKIPPED → PASSED. | Deferred (manual) | 2026-04-22 |

## Session Continuity

Last session: --stopped-at
Stopped at: Phase 6 context gathered
Resume file: --resume-file

**Planned Phase:** 5 (Structural Router Splits) — 4 plans — 2026-04-23T07:55:21.335Z
