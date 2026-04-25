# S05: Structural Router Splits

**Status:** ✅ completed 2026-04-23
**Goal:** `admin.py` (2,055 LOC) → `admin/` package, then `auth.py` (1,195 LOC) → `auth/` package; PyJWT migration. Old code deleted in the same PR that adds new code — no double-maintenance window.
**Demo:** OpenAPI snapshot drift guard green; `chrome-extension/API_CONTRACT.md` regenerated and committed; `python-jose` removed from lockfile; admin + auth subpackages importable.

## Must-Haves

- `admin.py` → `admin/` subpackage (stats/jobs/crawlers/db_ops/parts) with parametrized 401/403 coverage
- `auth.py` → `auth/` subpackage (core/two_factor/webauthn/oauth/_helpers)
- `python-jose` → `PyJWT 2.12.1` migration (algorithm explicit on every decode)
- OpenAPI-driven `chrome-extension/API_CONTRACT.md` generator + drift-guard pytest
- `/api/auth/google/*` → `/api/auth/oauth/google/*` restructure (web frontend migrated same PR)

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/05-structural-router-splits/` (4 PLAN/SUMMARY pairs: 05-01 through 05-04).

## Files Likely Touched

`backend/app/api/endpoints/admin/`, `backend/app/api/endpoints/auth/`, `chrome-extension/API_CONTRACT.md`, `frontend/src/api/`, `backend/pyproject.toml`
