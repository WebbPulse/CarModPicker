---
phase: 05-structural-router-splits
plan: 03
subsystem: api
tags: [openapi, chrome-extension, contract-testing, drift-guard, fastapi, pytest]

# Dependency graph
requires:
  - phase: 05-01-admin-split
    provides: Confirmed BaseEndpointRouter + EndpointRegistry patterns for sub-package routers; wave-1 gate (stable main before wave-2 parallel plans run)
  - phase: 01-safety-nets-ci-hardening
    provides: test_openapi_snapshot.py pattern (function-scope app import + TESTING/ENABLE_RATE_LIMITING env gate) — mirrored by this plan's drift guard
provides:
  - Chrome-extension API contract generator (OpenAPI → Markdown, 16-endpoint allow-list) with --stdout flag
  - Committed chrome-extension/API_CONTRACT.md (initial generated artifact, 2,012 lines / 37,344 chars)
  - Drift-guard pytest (subprocess-invokes generator, no Python import of the script)
  - AUTH-05 post-deploy human UAT checklist (5 steps)
affects: [05-04-auth-split, future-chrome-extension-api-changes, future-extension-auth-changes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subprocess-invoke drift guard: tests that need script-under-test output use subprocess.run([sys.executable, script, '--stdout']) instead of Python import, avoiding backend/scripts __init__.py absence"
    - "sys.path bootstrap inside script: scripts that import from app.main insert parents[1] into sys.path at function-scope so invocation works regardless of cwd"
    - "OpenAPI env gate for schema-consuming tools: TESTING=true + ENABLE_RATE_LIMITING=false before any app.main import to avoid rate-limiter schema pollution"
    - "Deterministic Markdown generation: json.dumps(sort_keys=True) + fixed-order tuple iteration + sys.stdout.write (no trailing newline) for byte-identical regeneration"

key-files:
  created:
    - backend/scripts/generate_ext_api_contract.py
    - backend/tests/test_ext_api_contract_up_to_date.py
    - chrome-extension/API_CONTRACT.md
    - .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md
  modified: []

key-decisions:
  - "Subprocess-invocation drift guard (not Python import) chosen over adding backend/scripts/__init__.py — avoids touching package structure, mirrors test_openapi_snapshot.py which also avoids importing scripts"
  - "sys.path.insert(0, backend_dir) inserted inside generate_markdown() rather than at module top — keeps the script runnable from any cwd without wrapper scripts or PYTHONPATH env requirement"
  - "--stdout mode uses sys.stdout.write(md) not print(md) to avoid the extra trailing newline that would break byte-for-byte equality with the committed file"
  - "Cwd=str(SCRIPT_PATH.parent.parent) passed to subprocess.run in the drift-guard test so the child process launches with backend/ as cwd (no behavioural difference since the script is cwd-independent, but matches documented invocation pattern)"

patterns-established:
  - "Pattern: generator script with dual-mode CLI (default = write to committed path, --stdout = emit to stdout for test diffing) — reusable template for future OpenAPI-derived documentation"
  - "Pattern: drift-guard test subprocess-invokes a CLI script — works with scripts that are not Python packages, no import gymnastics"

requirements-completed: [AUTH-05, AUTH-06]

# Metrics
duration: 6min
completed: 2026-04-23
---

# Phase 05 Plan 03: Chrome Extension API Contract Generator Summary

**Shipped an OpenAPI-derived Chrome-extension contract generator with pytest drift guard and committed the initial 16-endpoint Markdown artifact — parallel-safe with Plan 02 (zero file overlap with PyJWT migration).**

## Performance

- **Duration:** ~6 min (wall-clock)
- **Started:** 2026-04-23T16:09:38Z
- **Completed:** 2026-04-23T16:14:57Z
- **Tasks:** 2 (both TDD — RED + GREEN split into separate commits for Task 1)
- **Files created:** 4 (zero files modified — greenfield plan)

## Accomplishments

- `backend/scripts/generate_ext_api_contract.py` (227 lines) walks `app.openapi()` for the 16 EXTENSION_ENDPOINTS allow-list (sourced from `chrome-extension/src/background.ts`), flattens `$ref` references up to depth 3, and emits human-readable Markdown with parameters, request bodies, and responses. Supports `--stdout` flag (emits to stdout for test consumption) and default file-write mode.
- `chrome-extension/API_CONTRACT.md` (2,012 lines / 37,344 chars) committed with all 16 endpoints documented — first line `# Chrome Extension API Contract`, no `/auth` or `/admin` paths leaked (scope discipline per T-05-03-01).
- `backend/tests/test_ext_api_contract_up_to_date.py` drift guard: subprocess-invokes the generator with `--stdout`, diffs against the committed `.md` byte-for-byte. Fails CI if the doc is stale. Mirrors `test_openapi_snapshot.py`'s "no script import" pattern (backend/scripts has no `__init__.py`).
- `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` 5-step AUTH-05 post-deploy checklist recorded for Plan 04 (auth-split) validation window.
- Determinism verified: two successive generator invocations produce byte-identical output (`md5sum` before/after match).

## Task Commits

1. **Task 1 RED: Drift-guard test (failing)** — `0e20884` (test)
   - Added `backend/tests/test_ext_api_contract_up_to_date.py` before generator existed → test fails with `CalledProcessError: non-zero exit status 2` as expected.
2. **Task 1 GREEN: Generator + UAT + test-docstring cleanup** — `41eb597` (feat)
   - Added `backend/scripts/generate_ext_api_contract.py` with 16-endpoint allow-list, `--stdout` flag, depth-3 schema flattening, deterministic JSON serialization.
   - Added `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`.
   - Minor docstring tweak in the drift-guard test so the file no longer contains a literal `from backend.scripts` substring (plan acceptance check V11).
3. **Task 2 GREEN: Initial generated contract committed** — `8e2fa0b` (feat)
   - Ran `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py` to produce the committed `chrome-extension/API_CONTRACT.md`.
   - `pytest -n auto backend/tests/test_ext_api_contract_up_to_date.py` passes (drift guard is live).

_Note: Task 1 used standard TDD split (RED test commit → GREEN implementation commit). Task 2 was single-commit since it only produces a generated artifact._

## Files Created/Modified

- `backend/scripts/generate_ext_api_contract.py` (227 lines) — OpenAPI → Markdown generator with 16-tuple EXTENSION_ENDPOINTS allow-list; dual-mode CLI (`--stdout` vs default file-write); depth-3 `$ref` flattening; deterministic output.
- `backend/tests/test_ext_api_contract_up_to_date.py` (69 lines) — pytest drift guard; subprocess-invokes the generator with `TESTING=true ENABLE_RATE_LIMITING=false` and diffs `stdout` against the committed `.md`.
- `chrome-extension/API_CONTRACT.md` (2,012 lines) — initial generated contract, committed as-is.
- `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` (25 lines) — AUTH-05 5-step staging UAT checklist for post-Plan-04 validation.

## Decisions Made

- **Subprocess-invocation over Python import for the drift guard.** `backend/scripts/__init__.py` does not exist, `backend/` is not on `sys.path` as a package, and `pytest.ini` sets `testpaths = tests` with rootdir at `backend/`. A `from backend.scripts...` import would raise `ModuleNotFoundError`. Using `subprocess.run([sys.executable, str(SCRIPT_PATH), "--stdout"])` avoids this entirely — same philosophy as `test_openapi_snapshot.py` which calls `app.openapi()` directly rather than importing any script. Alternative (adding `__init__.py` to scripts/) was rejected as out-of-scope creep.
- **`sys.path.insert(0, backend_dir)` inside the script** rather than requiring `PYTHONPATH=.` at every invocation. Python puts `scripts/` (the directory of the script) on `sys.path[0]`, not `backend/`. The drift-guard test runs the child with `cwd=backend/` but python's sys.path bootstrap is the script's directory either way. Inlining the path fix makes the script cwd-independent and matches the plan's test shape exactly (no env-var plumbing beyond `TESTING`/`ENABLE_RATE_LIMITING`).
- **`sys.stdout.write(md)` not `print(md)`** in `--stdout` mode. `print` appends a trailing newline that would break byte-for-byte equality with the committed file written via `OUTPUT_PATH.write_text(md, ...)`. Both paths now call `generate_markdown()` once and produce identical bytes. Determinism check confirms.
- **16 endpoints sourced verbatim from the plan's `<interfaces>` block** (which in turn references RESEARCH.md Finding 3). Did not re-derive from `background.ts` — the plan's RESEARCH phase already verified the inventory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added sys.path bootstrap to generator script**
- **Found during:** Task 1 initial `--stdout` smoke test
- **Issue:** Running `python scripts/generate_ext_api_contract.py --stdout` from `backend/` raised `ModuleNotFoundError: No module named 'app'`. Python's `sys.path[0]` is the script's parent directory (`scripts/`), not the cwd (`backend/`), so `from app.main import app` failed. This is a pre-existing pattern issue also present in `backend/scripts/export_car_generations.py`, which normally requires `PYTHONPATH=.`.
- **Fix:** Inside `generate_markdown()`, before the function-scope `from app.main import app` import, insert `str(Path(__file__).resolve().parents[1])` (i.e., `backend/`) into `sys.path` if not already present. Keeps the fix local to the script, makes the script cwd-independent, and avoids forcing every caller (including the drift-guard test) to set `PYTHONPATH`.
- **Files modified:** `backend/scripts/generate_ext_api_contract.py` (lines 98-103)
- **Verification:** `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout` exits 0; drift-guard pytest passes.
- **Committed in:** `41eb597` (Task 1 GREEN)

**2. [Rule 3 - Blocking] Tightened drift-guard test docstring**
- **Found during:** Task 1 acceptance check V11 (`grep "from backend.scripts" ... ; test $? -eq 1`)
- **Issue:** The test's docstring explained why Python-level imports of the generator would fail and in doing so contained the literal substring `from backend.scripts.generate_ext_api_contract import ...`. A naive `grep` for `"from backend.scripts"` matched the docstring, failing plan acceptance check V11 even though no actual import statement existed.
- **Fix:** Rephrased the docstring to "A Python-level import of the generator would raise `ModuleNotFoundError`" — preserves the explanatory content without the exact literal pattern.
- **Files modified:** `backend/tests/test_ext_api_contract_up_to_date.py` (lines 7-14)
- **Verification:** `grep "from backend.scripts" backend/tests/test_ext_api_contract_up_to_date.py ; echo $?` → `1` (no match).
- **Committed in:** `41eb597` (Task 1 GREEN, same commit as generator fix)

---

**Total deviations:** 2 auto-fixed (both Rule 3 blocking). No architectural changes, no scope creep.
**Impact on plan:** Both deviations were mechanical blockers discovered during verification; neither changed the design or introduced new surface. The plan's `<interfaces>` block anticipated the `sys.path` issue in spirit (it assumed `from app.main import app` would work under cwd=backend/), and the docstring tweak was purely cosmetic to satisfy an overly literal grep assertion.

## Issues Encountered

- The `USER_IMAGES_BUCKET not configured. Image uploads will be disabled.` log line emitted by `app.main` on import goes to stderr (not stdout), so it does not pollute the generator's `--stdout` output or break byte-for-byte equality with the committed `.md`. No action needed.

## Verification Evidence

All plan `<verification>` commands run green:

- `pytest -n auto tests/test_ext_api_contract_up_to_date.py -x` → 1 passed
- `pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x` → 4 passed (regression guards preserved)
- `grep -E '/(auth|admin)' chrome-extension/API_CONTRACT.md ; test $? -eq 1` → exit 1 (no leak, scope discipline confirmed for T-05-03-01)
- Determinism: two successive `python scripts/generate_ext_api_contract.py` invocations produced identical `md5sum` on `chrome-extension/API_CONTRACT.md`.
- All 16 endpoint section headers present: `grep -c '^## \`'` → 16.

## Threat Flags

None. The generator operates inside the existing threat model (T-05-03-01 through T-05-03-04 in the plan) with no new network/auth/filesystem surface introduced. Allow-list is manually curated and does not expose `/auth` or `/admin` endpoints.

## Parallel-Safety with Plan 02 (PyJWT migration)

Confirmed zero file overlap:

- Plan 03 touched: `backend/scripts/generate_ext_api_contract.py`, `backend/tests/test_ext_api_contract_up_to_date.py`, `chrome-extension/API_CONTRACT.md`, `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`.
- Plan 02 (per plan frontmatter) touches: `backend/requirements.txt`, `backend/app/api/dependencies/auth.py`, and related test files.

No shared files. The two worktrees can merge in either order.

## Drift-Guard Pattern Note

The drift-guard test deliberately uses `subprocess.run([sys.executable, str(SCRIPT_PATH), "--stdout"])` rather than a Python import of the generator. This mirrors `backend/tests/test_openapi_snapshot.py`, which avoids script-imports by calling `app.openapi()` directly in-process. `backend/scripts/` has no `__init__.py` and is not installed as a package, so a Python import would fail with `ModuleNotFoundError`. Future script-drift guards in this codebase should follow the same subprocess-invocation pattern unless the scripts are first packaged (future cleanup).

## Next Phase Readiness

- **Plan 05-04 (auth split) reviewer gets a vetted, CI-guarded extension surface:** `chrome-extension/API_CONTRACT.md` lists exactly the 16 endpoints the extension calls. The auth-split review can verify no auth dependencies change on these endpoints without touching the extension's request/response shapes.
- **AUTH-05 UAT checklist ready for post-Plan-04 deploy:** `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` is the deterministic acceptance artifact. Fill in the sign-off fields after staging validation.
- **No blockers for Plan 04.**

## Self-Check: PASSED

- **Files created:**
  - `backend/scripts/generate_ext_api_contract.py` — FOUND
  - `backend/tests/test_ext_api_contract_up_to_date.py` — FOUND
  - `chrome-extension/API_CONTRACT.md` — FOUND
  - `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` — FOUND
- **Commits verified in git log:**
  - `0e20884` (test: RED drift guard) — FOUND
  - `41eb597` (feat: generator + UAT) — FOUND
  - `8e2fa0b` (feat: committed initial API_CONTRACT.md) — FOUND
- **All plan success criteria met** (6/6):
  1. Generator exists with `--stdout` + env-gate support ✓
  2. `API_CONTRACT.md` has 16 sections, deterministic ✓
  3. Drift guard passes (subprocess-invoke, no Python import) ✓
  4. `05-HUMAN-UAT.md` exists with 5-step AUTH-05 checklist ✓
  5. No `/admin` or `/auth` endpoints in contract ✓
  6. Zero file overlap with Plan 02 ✓

---
*Phase: 05-structural-router-splits*
*Completed: 2026-04-23*
