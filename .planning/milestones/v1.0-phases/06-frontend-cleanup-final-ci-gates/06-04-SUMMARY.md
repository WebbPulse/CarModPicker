---
phase: 06-frontend-cleanup-final-ci-gates
plan: 04
subsystem: infra
tags: [fastapi, pydantic, dependency-upgrade, openapi-snapshot, auth-characterization, qual-05, qual-06, pr-a]

# Dependency graph
requires:
  - phase: 03-non-breaking-internal-improvements
    provides: Pydantic v1 grep guard + catch_warnings PydanticDeprecatedSince20 round-trip test (plan 03-05) — guard for 2.13 deprecations
  - phase: 01-safety-nets-ci-hardening
    provides: SAFE-05 OpenAPI snapshot test + SAFE-06 7-flow auth characterization suite (signup, verify-email, login, 2FA-TOTP, WebAuthn, OAuth, password-reset)
  - phase: 06-frontend-cleanup-final-ci-gates
    provides: Plan 06-01 vitest grep guard frontend/src/test/extension-content-type.test.ts — static lock that chrome-extension fetch POST always sets Content-Type
provides:
  - QUAL-05 PR-A: FastAPI 0.128.0 -> 0.136.1 + Pydantic 2.11.3 -> 2.13.3 stack bump (highest-coupling pair of D-11 two-PR train)
  - Regenerated OpenAPI snapshot reflecting FastAPI 0.130+ contentMediaType and Pydantic 2.13 ValidationError ctx/input fields (D-13 SAFE-05 guard re-baselined)
  - QUAL-06 manual UAT checklist item for chrome-extension Content-Type runtime verification under FastAPI 0.136 (D-12b)
  - 06-HUMAN-UAT.md seeded with 4 sections — extension smoke test, Sentry route-group tags, Terraform QUAL-08 apply, parts-catalog placeholder
affects: [06-05, 06-06]  # PR-B (sqlalchemy/alembic/uvicorn + jose removal) follows; FE-07 polish references same UAT file

# Tech tracking
tech-stack:
  added: []  # No new libraries — version-only bumps
  patterns:
    - "Two-PR upgrade train (D-11): land high-coupling pair (FastAPI+Pydantic) separately from low-risk patch pair (SQLAlchemy+Alembic+Uvicorn) for bisect hygiene"
    - "OpenAPI snapshot regeneration policy: separate commit from version bump with explicit benign-diff documentation in commit message"
    - "Transitive-dep auto-bump rule: when a top-level pin forces another pinned transitive forward, bump the transitive to the minimum-required version (Rule 3 auto-fix)"

key-files:
  created:
    - ".planning/phases/06-frontend-cleanup-final-ci-gates/06-HUMAN-UAT.md"
  modified:
    - "backend/requirements.txt"
    - "backend/tests/fixtures/openapi_snapshot.json"

key-decisions:
  - "pydantic_core pin handling: option A (removal) — explicit pin removed; pydantic 2.13.3 pulls pydantic_core 2.46.3 transitively"
  - "OpenAPI snapshot drift was benign and regenerated in a separate commit (84f794b vs 8486a38) — diff review surface preserved per plan STEP 4b guidance"
  - "Pydantic 2.13.3 surfaced ZERO new v1 deprecation warnings on UserRead round-trip — no inline migration fixes were needed (catch_warnings guard green on first run)"
  - "Transitive deps bumped: typing-inspection 0.4.0->0.4.2 (fastapi 0.136.1 requires >=0.4.2); typing_extensions 4.13.1->4.14.1 (pydantic 2.13.3 requires >=4.14.1)"
  - "python-jose, sqlalchemy, alembic, uvicorn UNTOUCHED — Plan 06-05 (PR-B) owns those changes per D-11 / D-14"

patterns-established:
  - "OpenAPI snapshot regeneration commit pattern: 1 commit for source bump, 1 commit for snapshot regen, both reference each other for git-bisect clarity"
  - "Transitive-dep co-bump: when pip resolution fails because a top-level upgrade requires a newer pinned transitive, bump the transitive in requirements.txt rather than loosen its pin (preserves reproducibility)"
  - "Manual-UAT seeding pattern: phase-level 06-HUMAN-UAT.md drafted at the wave that introduces the change requiring manual verification; later plans append, never replace"

requirements-completed: [QUAL-05, QUAL-06]

# Metrics
duration: ~22min
completed: 2026-04-24
---

# Phase 6 Plan 4: PR-A FastAPI 0.136 + Pydantic 2.13 Upgrade Summary

**FastAPI bumped 0.128.0 to 0.136.1 + Pydantic bumped 2.11.3 to 2.13.3 with full backend test suite green (2365 passed, 8 skipped), OpenAPI snapshot regenerated for benign FastAPI 0.130 contentMediaType + Pydantic 2.13 ValidationError schema additions, and 06-HUMAN-UAT.md seeded with chrome-extension Content-Type smoke test for runtime QUAL-06 verification.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-24T03:39Z (approx)
- **Completed:** 2026-04-24T04:01Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)
- **Commits:** 3 (2 task commits + 1 separate snapshot regeneration commit)

## Accomplishments

- **PR-A version bump landed cleanly.** FastAPI 0.128.0 -> 0.136.1, Pydantic 2.11.3 -> 2.13.3, pydantic_core explicit pin removed (option A — let pydantic pin its own pydantic_core transitively). Full backend test suite passes: 2365 / 8 skipped / 0 failed under upgraded stack with coverage at 51% (matches baseline; no regression).
- **Three D-13 guards green on first run after upgrade.** Pydantic v1 regression test (test_pydantic_v1_regression.py: forbidden-pattern grep + catch_warnings UserRead round-trip) reported zero new PydanticDeprecatedSince20 warnings under 2.13 — meaning the Phase 3 plan 03-05 cleanup was complete enough that 2.13's expanded deprecation surface caught nothing new. Auth characterization 7-flow suite (5 passed, 2 skipped — OAuth cassettes still pending per STATE.md deferred items) green, confirming FastAPI 0.136 strict-Content-Type changes did NOT regress login/2FA/WebAuthn/password-reset flows.
- **OpenAPI snapshot regenerated with reviewable benign diff.** 9 lines added, 2 lines removed across the entire 469KB schema. All deltas are upstream schema vocabulary upgrades: file-upload responses moved from OpenAPI 3.0 `format: "binary"` to OpenAPI 3.1 `contentMediaType: "application/octet-stream"` (FastAPI 0.130 change, identical wire semantics); Pydantic 2.13 added `ctx` and `input` fields to ValidationError schema (pure error-payload enrichment, additive only). No removed routes, no changed status codes, no altered required fields. Committed in a separate commit (8486a38) from the version bump (84f794b) per plan STEP 4b for git-bisect clarity.
- **06-HUMAN-UAT.md drafted with 4 manual verification gates.** Sections: (1) chrome-extension smoke test against FastAPI 0.136 local backend covering QUAL-06 D-12b runtime verification — login + crawl POST round-trip, no 400/415 Content-Type errors; (2) Sentry route-group tag verification in staging covering FE-03/OBS-05 pipeline — 4 distinct events with route_group=admin|authentication|builder|public tags; (3) Terraform QUAL-08 apply confirmation for crawl-data Glacier Deep Archive lifecycle (user-images bucket explicitly untouched per D-19); (4) parts-catalog polish placeholder forward-referencing Plan 06-06.

## Task Commits

Each task was committed atomically:

1. **Task 1: Bump fastapi + pydantic in requirements.txt; reinstall; run full test gauntlet**
   - `84f794b` (chore) — `chore(06-04): bump fastapi 0.128.0->0.136.1, pydantic 2.11.3->2.13.3`
   - `8486a38` (chore) — `chore(06-04): regenerate OpenAPI snapshot for FastAPI 0.136 + Pydantic 2.13` (separate snapshot regeneration per plan STEP 4b)
2. **Task 2: Seed 06-HUMAN-UAT.md with QUAL-06 extension smoke test + route-group Sentry manual items**
   - `09110be` (docs) — `docs(06-04): seed 06-HUMAN-UAT.md with 4 manual verification items`

_Note: Task 1 produced two commits because OpenAPI snapshot regeneration was needed and per plan STEP 4b must land in a SEPARATE commit from the version bump for reviewer-inspectable diff visibility._

## Files Created/Modified

- `backend/requirements.txt` — fastapi 0.128.0->0.136.1, pydantic 2.11.3->2.13.3, pydantic_core==2.33.1 explicit pin REMOVED (option A), typing-inspection 0.4.0->0.4.2 (transitive co-bump), typing_extensions 4.13.1->4.14.1 (transitive co-bump). sqlalchemy, alembic, uvicorn, python-jose UNTOUCHED.
- `backend/tests/fixtures/openapi_snapshot.json` — regenerated under FastAPI 0.136.1 + Pydantic 2.13.3 via documented `TESTING=true ENABLE_RATE_LIMITING=false python -c "..."` procedure; net delta +9 / -2 lines (file-upload contentMediaType + ValidationError ctx/input).
- `.planning/phases/06-frontend-cleanup-final-ci-gates/06-HUMAN-UAT.md` — NEW — phase-level human-only verification checklist with 4 sections (89 lines).

## Decisions Made

- **pydantic_core pin handling: option A (removal).** The explicit `pydantic_core==2.33.1` line was deleted; Pydantic 2.13.3 pulls `pydantic_core==2.46.3` transitively. Plan called this the recommended choice — fewer manual pins is healthier; the one-pin-per-top-level-dep convention reduces drift surface.
- **OpenAPI snapshot regenerated rather than escalated.** Diff inspection (16 lines total: 9 additions, 2 deletions, surrounding context) showed only upstream FastAPI 0.130 schema vocabulary change (`format: binary` -> `contentMediaType`) and Pydantic 2.13 ValidationError additive fields (`ctx`, `input`). Per plan STEP 4b regeneration is appropriate when diff is "only additive (new properties, new examples, no breaking changes)"; this diff is even stricter than that bar (substitution of one OpenAPI keyword for its 3.1 equivalent + additive error fields). Regeneration committed separately (8486a38) from version bump (84f794b) for git-bisect hygiene.
- **No inline Pydantic v2 deprecation fixes were needed.** Phase 3 plan 03-05 left the codebase fully migrated; Pydantic 2.13's expanded deprecation surface caught zero new patterns on the catch_warnings UserRead round-trip. test_pydantic_v1_regression.py both subtests passed cleanly (forbidden-pattern grep + round-trip-under-error-filter).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bumped typing-inspection 0.4.0 -> 0.4.2 (transitive dep)**
- **Found during:** Task 1, STEP 3 (`pip install -r requirements.txt`)
- **Issue:** First install attempt failed with `ResolutionImpossible: fastapi 0.136.1 depends on typing-inspection>=0.4.2`. Plan only spec'd fastapi + pydantic + pydantic_core changes; the transitive `typing-inspection==0.4.0` pin (line 16 of pre-bump requirements.txt) was incompatible with fastapi 0.136.1's stricter floor.
- **Fix:** Bumped `typing-inspection==0.4.0` -> `typing-inspection==0.4.2` (minimum required by fastapi 0.136.1; latest available is 0.4.2). No semantics change.
- **Files modified:** backend/requirements.txt
- **Verification:** Re-ran `pip install -r requirements.txt`; resolution proceeded past this conflict.
- **Committed in:** 84f794b (Task 1 main bump commit)

**2. [Rule 3 - Blocking] Bumped typing_extensions 4.13.1 -> 4.14.1 (transitive dep)**
- **Found during:** Task 1, STEP 3 (second `pip install` attempt after fix #1)
- **Issue:** Second install attempt failed with `ResolutionImpossible: pydantic 2.13.3 depends on typing-extensions>=4.14.1`. The transitive `typing_extensions==4.13.1` pin (line 17 of pre-bump requirements.txt) was incompatible with pydantic 2.13.3's stricter floor.
- **Fix:** Bumped `typing_extensions==4.13.1` -> `typing_extensions==4.14.1` (minimum required by pydantic 2.13.3; latest available is 4.15.0 but minimum-required keeps surface area small).
- **Files modified:** backend/requirements.txt
- **Verification:** Re-ran `pip install -r requirements.txt`; install completed successfully — `Successfully installed fastapi-0.136.1 pydantic-2.13.3 pydantic-core-2.46.3 typing-inspection-0.4.2 typing_extensions-4.14.1`.
- **Committed in:** 84f794b (Task 1 main bump commit, alongside fix #1)

---

**Total deviations:** 2 auto-fixed (both Rule 3 blocking — transitive-dep version-floor conflicts).
**Impact on plan:** Both auto-fixes were strictly required to install the fastapi 0.136.1 + pydantic 2.13.3 pair. No scope creep — both transitive deps bumped to their minimum-compatible versions only. The pattern of co-bumping pinned transitive deps when their owning top-level deps move is documented as a new pattern in this summary's frontmatter (`patterns-established` line 3).

## Issues Encountered

- **OpenAPI snapshot drift detected on first run** (anticipated by plan STEP 4b). FastAPI 0.130 introduced a schema vocabulary change for binary file uploads (`format: "binary"` -> `contentMediaType: "application/octet-stream"`) and Pydantic 2.13 added `ctx` and `input` fields to the ValidationError schema. Diff inspection showed it was benign (16 lines total, all upstream schema enrichment, no removed routes / changed status codes / altered required fields). Resolved by regenerating the snapshot per the documented procedure in `test_openapi_snapshot.py` docstring and committing the regeneration in a SEPARATE commit (8486a38) from the version bump (84f794b) for reviewer-inspectable diff hygiene per plan STEP 4b.
- **No other issues** — auth characterization suite green on first run (5 passed, 2 skipped — OAuth cassettes are a documented STATE.md deferred item from Phase 1 plan 01-06, unrelated to this plan), full backend suite green on first run (2365 passed, 8 skipped, 51% coverage), Pydantic v1 regression guard green on first run (zero new 2.13 deprecation warnings).

## TDD Gate Compliance

N/A — this plan is `type: execute` (not `type: tdd`); the underlying TDD compliance is provided by the existing Phase 1 SAFE-06 auth characterization suite + Phase 3 plan 03-05 Pydantic v1 regression guard, both pinned BEFORE this upgrade and re-run AFTER as the gate.

## User Setup Required

**External services require no manual configuration for this plan.** However, **manual UAT items in 06-HUMAN-UAT.md are required before phase merge.** See `.planning/phases/06-frontend-cleanup-final-ci-gates/06-HUMAN-UAT.md` Section 1 for the chrome-extension smoke test against the upgraded backend (operator-only, no automation possible per VALIDATION.md Manual-Only Verifications and D-39 deferred Playwright-with-extensions).

## Threat Model Disposition

All four `mitigate` threats from the plan's `<threat_model>` are addressed:

| Threat ID | Disposition | How mitigated |
|-----------|-------------|---------------|
| T-06-16 (Pydantic v1 deprecation creep) | mitigate | test_pydantic_v1_regression.py + catch_warnings round-trip both green under 2.13 — zero new deprecations surfaced, no inline fixes needed |
| T-06-17 (FastAPI route metadata drift) | mitigate | OpenAPI snapshot regenerated separately (8486a38); diff documented as benign upstream schema vocabulary changes; no removed routes / no breaking changes |
| T-06-18 (Chrome extension Content-Type DoS) | mitigate | Plan 06-01 vitest grep guard still passes statically (background.ts:90 still sets `Content-Type: application/json`); UAT item 1 captures the runtime verification gate |
| T-06-19 (Auth flow regression under FastAPI 0.136) | mitigate | SAFE-06 7-flow auth characterization suite (signup/verify-email/login/2FA-TOTP/WebAuthn/OAuth/password-reset) green under upgraded stack; 5 passed, 2 skipped (OAuth cassettes — pre-existing STATE.md deferred) |
| T-06-20 (pydantic_core pin drift) | accept | Option A taken — explicit pin removed; Pydantic 2.13.3 pulls pydantic_core 2.46.3 transitively. Pydantic itself pins pydantic_core precisely per release; transitive resolution is safe. |

No new security-relevant surface introduced; no `threat_flag` items required.

## Next Phase Readiness

- **PR-A merged-ready.** All 10 verification points in plan `<verification>` block satisfied:
  1. Full suite (2365 passed, 8 skipped, coverage 51%) — exit 0
  2. Pydantic v1 regression guard — exit 0
  3. OpenAPI snapshot guard — exit 0 (post-regeneration)
  4. Auth characterization — exit 0 (5 passed, 2 skipped — OAuth cassettes pre-existing skip)
  5. `^fastapi==0.136` in requirements.txt — exit 0
  6. `^pydantic==2.13` in requirements.txt — exit 0
  7. `^sqlalchemy==2.0.41` UNTOUCHED — exit 0
  8. `^python-jose` UNTOUCHED — exit 0
  9. 06-HUMAN-UAT.md exists with 4 numbered sections — exit 0
  10. Frontend extension-content-type vitest guard (Plan 06-01) still applies (no source changes needed; static guard unchanged)
- **Plan 06-05 (PR-B) unblocked.** SQLAlchemy 2.0.41 -> 2.0.49, Alembic 1.16.2 -> 1.18.x, Uvicorn 0.34.0 -> 0.45.0, and python-jose removal can now proceed — they were sequenced behind PR-A per D-11 to keep bisect surfaces clean.
- **Manual UAT pending.** 06-HUMAN-UAT.md Section 1 (chrome-extension smoke test) is the runtime confirmation gate for QUAL-06 / D-12b. It cannot be automated per D-39 (Playwright-with-extensions deferred); operator runs it before phase final merge.
- **No new blockers.** OAuth characterization cassettes remain a Phase 1 deferred item (STATE.md "Deferred Items" table) — not a Phase 6 concern.

## Self-Check: PASSED

Verifications run after writing this SUMMARY:

**File existence:**
- FOUND: backend/requirements.txt (modified)
- FOUND: backend/tests/fixtures/openapi_snapshot.json (modified)
- FOUND: .planning/phases/06-frontend-cleanup-final-ci-gates/06-HUMAN-UAT.md (created)

**Commits exist in git log:**
- FOUND: 84f794b chore(06-04): bump fastapi 0.128.0->0.136.1, pydantic 2.11.3->2.13.3
- FOUND: 8486a38 chore(06-04): regenerate OpenAPI snapshot for FastAPI 0.136 + Pydantic 2.13
- FOUND: 09110be docs(06-04): seed 06-HUMAN-UAT.md with 4 manual verification items

---
*Phase: 06-frontend-cleanup-final-ci-gates*
*Completed: 2026-04-24*
