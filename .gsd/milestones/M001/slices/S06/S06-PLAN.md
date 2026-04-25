# S06: Frontend Cleanup & Final CI Gates

**Status:** ✅ completed 2026-04-23
**Goal:** ESLint strict mode, type-safety, Tailwind v4 patterns, error boundaries, bandit/dep upgrades.
**Demo:** ESLint passes with `no-explicit-any: error` + `no-unsafe-*`; 4 lazy route groups wrapped with `RouteGroupBoundary`; bandit HIGH gate green in CI; FastAPI / Pydantic / SQLAlchemy / Alembic / Uvicorn upgraded to target versions.

## Must-Haves

- `services/Api.ts` (1,520 LOC) → 20 per-domain modules under `frontend/src/api/*`
- ESLint strict (`@typescript-eslint/no-explicit-any: error` + `no-unsafe-*`)
- `RouteGroupBoundary` on 4 lazy route groups (admin/authentication/builder/public)
- Tailwind v3 → v4 gradient codemod
- madge circular-import CI; bandit HIGH gate
- Stack patch upgrades: FastAPI 0.136, Pydantic 2.13, SQLAlchemy 2.0.49, Alembic 1.18, Uvicorn 0.45
- Glacier 90d lifecycle on `carmodpicker-production-crawl-data`

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/06-frontend-cleanup-final-ci-gates/` (6 PLAN/SUMMARY pairs: 06-01 through 06-06).

## Files Likely Touched

`frontend/src/api/`, `frontend/eslint.config.js`, `frontend/src/components/RouteGroupBoundary.tsx`, `backend/pyproject.toml`, `terraform/`
