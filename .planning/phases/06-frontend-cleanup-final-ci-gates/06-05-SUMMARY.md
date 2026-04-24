---
phase: 06-frontend-cleanup-final-ci-gates
plan: 05
subsystem: infra
tags: [sqlalchemy, alembic, uvicorn, pyjwt, python-jose, requirements-pin, dependency-bump, qual-05, ci-gates]

# Dependency graph
requires:
  - phase: 06-frontend-cleanup-final-ci-gates
    provides: "Plan 06-04 (PR-A) FastAPI 0.136.1 + Pydantic 2.13.3 baseline; intentionally landed before this PR-B per D-11 ordering."
  - phase: 04-postgres-prod-readiness
    provides: "scripts/test_migration_round_trip.sh — Alembic round-trip canary used here as the Alembic 1.18 gate (D-13)."
  - phase: 05-auth-hardening
    provides: "PyJWT migration (AUTH-04 D-06) — production canonical JWT lib already in place (app/api/dependencies/auth.py:7), so this plan only needed to retire the parallel jose installation."
provides:
  - "sqlalchemy 2.0.49, alembic 1.18.4, uvicorn 0.45.0 pinned in backend/requirements.txt"
  - "python-jose + 3-line comment block + ecdsa transitive removed (CVE-2024-23342 surface eliminated)"
  - "test_pyjwt_migration.py deleted (no longer guards a live invariant after jose removal)"
  - "test_auth_utils.py migrated to PyJWT (last remaining jose consumer per D-23)"
  - "Backend test suite green under upgraded stack: 2363 passed, 8 skipped"
  - "Alembic 1.18.4 round-trip canary (upgrade -> downgrade -1 -> upgrade head) green against Postgres 16"
affects: [phase-06 plans 06-06+, future phases that pin requirements.txt, future Alembic migrations]

# Tech tracking
tech-stack:
  added: []  # No new libraries; this is a version-bump + removal plan.
  patterns:
    - "PR-B of two-PR upgrade train (D-11): patch-level bumps land AFTER FastAPI/Pydantic minor bump for clean bisect isolation."
    - "Dependency removal protocol: edit requirements.txt -> pip uninstall package + transitive CVE deps -> grep verify zero imports remain -> delete dead test."

key-files:
  created:
    - ".planning/phases/06-frontend-cleanup-final-ci-gates/06-05-SUMMARY.md"
  modified:
    - "backend/requirements.txt"
    - "backend/tests/dependencies/test_auth_utils.py"
  deleted:
    - "backend/tests/test_pyjwt_migration.py"

key-decisions:
  - "Did NOT bump uvicorn to 0.46 — D-11 explicitly targets 0.45 (matches QUAL-05 spec exactly); 0.46 exists but is out of scope."
  - "Pinned alembic==1.18.4 (latest 1.18 patch per RESEARCH.md verification 2026-04-23); did not jump to 1.19 minor."
  - "Explicit `pip uninstall python-jose ecdsa` after requirements.txt edit — `pip install -r` only adds/upgrades, it does not remove packages absent from the file. Required to validate the CVE-2024-23342 (ecdsa) surface is actually gone from the local environment."
  - "Used dev Postgres (carmodpicker_persistant_volume_db on :5432) for round-trip canary. No dedicated test DB needed; the round-trip script is non-destructive (upgrade -> downgrade -1 -> upgrade head ends at the same revision)."

patterns-established:
  - "Two-PR upgrade train (PR-A high-risk, PR-B patch-bumps + cleanup) — D-11 ordering preserved across worktrees."
  - "jose -> PyJWT migration recipe for HS256: only the import statement changes (`from jose import jwt` -> `import jwt`); `jwt.encode/jwt.decode` HS256 API is signature-identical."

requirements-completed: [QUAL-05]

# Metrics
duration: ~22min
completed: 2026-04-24
---

# Phase 06 Plan 05: SQLAlchemy 2.0.49 + Alembic 1.18.4 + Uvicorn 0.45.0 + python-jose retirement Summary

**PR-B of the two-PR upgrade train (D-11): patch bumps for sqlalchemy/alembic/uvicorn plus full python-jose retirement (D-14) and last-consumer migration (D-23). Backend test suite (2363 passed) and Alembic 1.18 round-trip canary both green; CVE-2024-23342 (ecdsa transitive) attack surface eliminated.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-24T03:51:00Z (approx — branch reset to phase base)
- **Completed:** 2026-04-24T04:12:50Z
- **Tasks:** 2
- **Files modified:** 2 (backend/requirements.txt, backend/tests/dependencies/test_auth_utils.py)
- **Files deleted:** 1 (backend/tests/test_pyjwt_migration.py)

## Accomplishments
- sqlalchemy 2.0.41 -> 2.0.49 (patch-range bug fixes; no API surface change since Phase 4 plan 04-04 already migrated `session.query()` -> `select()`)
- alembic 1.16.2 -> 1.18.4 (round-trip canary green; no inline migration fixes required)
- uvicorn 0.34.0 -> 0.45.0 (lifespan + ASGI 3.0 stable across the version gap; no code changes needed)
- python-jose[cryptography]==3.5.0 + 3-line comment block deleted from requirements.txt
- ecdsa transitive (CVE-2024-23342) uninstalled from local environment along with jose
- backend/tests/test_pyjwt_migration.py deleted (no longer guards a live invariant — PyJWT was already production canonical)
- backend/tests/dependencies/test_auth_utils.py migrated from `from jose import jwt` to `import jwt` (D-23 closed)
- Plan 06-04 pins (fastapi==0.136.1, pydantic==2.13.3) explicitly preserved
- Zero `from jose|import jose` hits remain anywhere under backend/

## Task Commits

Each task was committed atomically on branch `worktree-agent-a1095481f53949f2a`:

1. **Task 1: Migrate test_auth_utils.py from python-jose to PyJWT (D-23)** — `274c360` (refactor)
2. **Task 2: Bump sqlalchemy/alembic/uvicorn; delete python-jose + test_pyjwt_migration.py; full gauntlet** — `8ed5e28` (chore)

**Plan metadata:** SUMMARY committed in a follow-up `docs(06-05)` commit (this file) on the same branch.

## Files Created/Modified
- `backend/requirements.txt` — sqlalchemy/alembic/uvicorn pin bumps + python-jose pin and 3-line comment block removed (net: -3 lines deleted, 3 lines edited)
- `backend/tests/dependencies/test_auth_utils.py` — single line edit: `from jose import jwt` -> `import jwt`. No call-site changes; jwt.encode/jwt.decode HS256 API is signature-identical between jose and PyJWT.
- `backend/tests/test_pyjwt_migration.py` — DELETED. Existed solely to prove byte-identity parity between jose-signed and PyJWT-signed HS256 tokens during the Phase 5 AUTH-04 migration. With PyJWT in prod and no pre-migration tokens in flight, the test guards no live invariant. D-14 closes.

## Decisions Made
- **Two-PR upgrade train (D-11) ordering preserved:** Plan 06-04 (PR-A: FastAPI 0.136.1 + Pydantic 2.13.3) landed first; this PR-B is the patch-bump train. If a regression surfaces in production, bisect cleanly attributes the breakage to one of the two PRs without ambiguity.
- **`pip uninstall python-jose ecdsa` was explicit:** `pip install -r requirements.txt` only adds and upgrades packages — it does NOT remove packages no longer listed in the file. Without the explicit uninstall, jose would remain importable from the local venv and the post-removal grep / `pip show python-jose` checks would mask the real removal. Did this for ecdsa too because it was the CVE-2024-23342 carrier.
- **Used existing dev Postgres for round-trip canary:** carmodpicker_persistant_volume_db on :5432 was already running (docker-compose dev DB). The round-trip script (upgrade -> downgrade -1 -> upgrade head) is non-destructive — it lands on the same revision it started on, leaving the dev DB schema unchanged.
- **Did not bump uvicorn to 0.46:** D-11 targets 0.45.0 explicitly (matches QUAL-05 spec). 0.46 exists but is out of scope for this plan.

## Deviations from Plan

None - plan executed exactly as written.

The plan's verification gauntlet (test_auth_utils.py -> Alembic round-trip -> full pytest) executed in the documented order. No additional bug fixes, missing functionality, or blocking issues encountered. test_auth_utils.py had no jose-specific exception handlers (PATTERNS.md scan was correct), so the migration was a clean one-line import swap.

**Total deviations:** 0
**Impact on plan:** Zero scope creep; clean PR-B execution per D-11 ordering.

## Issues Encountered

**Worktree path edit hiccup (recovered, no commit impact):** First Edit on test_auth_utils.py used the main-repo absolute path (`/home/.../CarModPicker/backend/...`) rather than the worktree-relative path (`/home/.../worktrees/agent-a1095481f53949f2a/backend/...`). Detected immediately when `git status` in the worktree returned empty — reverted the main-repo file via `git checkout --` and re-applied the edit to the worktree path. No commits were affected; the worktree branch only contains the correct edit.

## Verification (gates passed)

1. **`grep -rn "from jose\|import jose" backend/`** — zero hits (D-14 static check)
2. **`pip show python-jose`** — `WARNING: Package(s) not found: python-jose` (uninstall confirmed)
3. **`python -c "import sqlalchemy; print(sqlalchemy.__version__)"`** — `2.0.49`
4. **`python -c "import alembic; print(alembic.__version__)"`** — `1.18.4`
5. **`pip show uvicorn | grep Version`** — `Version: 0.45.0`
6. **`grep -q '^fastapi==0.136' backend/requirements.txt`** — exit 0 (Plan 06-04 preserved)
7. **`grep -q '^pydantic==2.13' backend/requirements.txt`** — exit 0 (Plan 06-04 preserved)
8. **`pytest -n auto tests/dependencies/test_auth_utils.py`** — 6 passed in 9.89s (PyJWT migration green)
9. **`pytest -n auto`** — 2363 passed, 8 skipped, 1031 warnings in 32.49s under upgraded stack (test_pyjwt_migration.py deletion accounts for the 2 lost test cases vs prior baseline; total collected = 2371)
10. **`bash scripts/test_migration_round_trip.sh head`** against dev Postgres — `==> Round-trip successful.` (Alembic 1.18 canary green; D-13 closed)

## User Setup Required

None — no external service configuration required. All changes are local to backend/requirements.txt and tests/.

## Next Phase Readiness

- QUAL-05 PR-B complete; the entire two-PR upgrade train (PR-A from 06-04 + PR-B from 06-05) is now in main once the worktree is merged.
- D-14 (python-jose removal) and D-23 (test_auth_utils.py PyJWT migration) closed.
- D-13 (Alembic 1.18 round-trip canary) green under the upgraded stack — confirms the Phase 4 plan 04-06 canary is robust enough to gate future Alembic minor bumps.
- Plan 06-06 (final phase plan) can proceed without dependency-bump distractions.

## Threat Flags

None — no new network endpoints, auth surfaces, file-access patterns, or trust-boundary schema changes introduced. The CVE-2024-23342 (ecdsa transitive via python-jose) attack surface is REMOVED, not added.

## Self-Check: PASSED

- backend/requirements.txt: contains `sqlalchemy==2.0.49`, `alembic==1.18.4`, `uvicorn==0.45.0`; no `python-jose` line — VERIFIED via grep above.
- backend/tests/dependencies/test_auth_utils.py: line 3 = `import jwt`; zero jose references — VERIFIED.
- backend/tests/test_pyjwt_migration.py: file does not exist; deletion staged in commit `8ed5e28` — VERIFIED via `test ! -f`.
- Commit 274c360: present in `git log --oneline` — VERIFIED.
- Commit 8ed5e28: present in `git log --oneline` — VERIFIED.

---
*Phase: 06-frontend-cleanup-final-ci-gates*
*Plan: 05*
*Completed: 2026-04-24*
