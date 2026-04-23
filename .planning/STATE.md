---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 04-02
last_updated: "2026-04-23T03:52:22.128Z"
last_activity: 2026-04-23
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 24
  completed_plans: 20
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.
**Current focus:** Phase 04 — db-parts-hardening

## Current Position

Phase: 04 (db-parts-hardening) — EXECUTING
Plan: 3 of 6
Status: Ready to execute
Last activity: 2026-04-23

Progress: [████████░░] 83%

## Performance Metrics

**Velocity:**

- Total plans completed: 18
- Average duration: — min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 8 | - | - |
| 03 | 5 | - | - |
| 02 | 5 | - | - |

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

Last session: 2026-04-23T03:52:22.124Z
Stopped at: Completed 04-02
Resume file: None

**Planned Phase:** 04 (db-parts-hardening) — 6 plans — 2026-04-23T03:29:38.710Z
