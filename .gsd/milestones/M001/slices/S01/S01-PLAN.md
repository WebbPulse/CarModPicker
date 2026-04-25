# S01: Safety Nets & CI Hardening

**Status:** ✅ completed 2026-04-23
**Goal:** Lock in coverage floors, characterization tests, and migration guards before touching anything structural.
**Demo:** CI fails on coverage drop, missing migration `# SAFE:` annotation, or broken auth/crawler characterization tests.

## Must-Haves

- Backend `--cov-fail-under` enforced; frontend vitest thresholds enforced
- Migration DROP-guard rejects unannotated drops
- 7 auth + 5 crawler-adapter characterization tests pinned in CI
- Three `op.drop_constraint(None, ...)` migrations repaired forward-only
- `MetaData(naming_convention=...)` applied to declarative Base
- Weekly Dependabot (pip + npm + github-actions)

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/01-safety-nets-ci-hardening/` (8 PLAN/SUMMARY pairs: 01-01 through 01-08).

## Files Likely Touched

`.github/workflows/`, `backend/alembic/`, `backend/app/`, `frontend/vitest.config.ts`, `.github/dependabot.yml`
