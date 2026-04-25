# S04: DB & Parts Hardening

**Status:** ✅ completed 2026-04-23
**Goal:** N+1 fix, part-link concurrency, FK index audit, session API migration, build-log eager creation — all under real Postgres in CI.
**Demo:** build-logs detail page issues 2 queries (was N+1); 13 FK indexes present; 10-thread postgres concurrency CI green; pytest grep shows zero `session.query(` in `backend/app/`.

## Must-Haves

- N+1 fix in build_logs via `selectinload(BuildLogPost.author)` + 2-query regression test
- 13 FK indexes added across 22 models
- `with_for_update()` row locks on link_new_part/reelect_canonical/unlink_part
- 10-thread postgres concurrency CI job (postgres:16 sidecar)
- 304-site `session.query()` → `select()` + `session.scalars()` sweep
- `lazy="raise"` on hot relationships; `pool_recycle=1800`
- Transactional part linking with concurrency invariants (no orphans, no cycles, exactly-one-canonical)

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/04-db-parts-hardening/` (6 PLAN/SUMMARY pairs: 04-01 through 04-06).

## Files Likely Touched

`backend/app/api/models/`, `backend/app/api/services/`, `backend/alembic/versions/`, `.github/workflows/backend-ci.yml`
