# S08: Frontend Coverage Expansion (SAFE-03)

**Status:** ✅ completed 2026-04-24
**Goal:** Lift frontend test coverage from 0.43% baseline to D-06 targets (60/50/50/60) and enforce thresholds in CI.
**Demo:** `frontend/vitest.config.ts` enforces 60/50/50/60 thresholds; CI fail-force proof captured; no `.skip` left unaccounted for.

## Must-Haves

- Frontend coverage 0.43% baseline → 60% statements / 50% branches / 50% functions / 60% lines
- Thresholds enforced in `frontend/vitest.config.ts`
- CI fail-force proof captured (PR that drops coverage fails)
- 20 plans across page/component/hook/api-module testing

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/08-frontend-coverage-expansion/` (20 PLAN/SUMMARY pairs: 08-01 through 08-20).

## Files Likely Touched

`frontend/src/**/*.test.tsx`, `frontend/vitest.config.ts`
