---
phase: 01-safety-nets-ci-hardening
fixed_at: 2026-04-22T09:20:11Z
review_path: .planning/phases/01-safety-nets-ci-hardening/01-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-22T09:20:11Z
**Source review:** .planning/phases/01-safety-nets-ci-hardening/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (WR-01 through WR-04; Info findings excluded per fix_scope)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: pytest.ini `testpaths` points at non-existent directory

**Files modified:** `backend/pytest.ini`
**Commit:** 4382475
**Applied fix:** Changed `testpaths = app/tests` to `testpaths = tests` (Option B from review). Verified pytest still collects 2165 tests after the change.

### WR-02: Backend CI passes Black args that duplicate pyproject.toml

**Files modified:** `.github/workflows/backend-ci.yml`
**Commit:** 248c33c
**Applied fix:** Removed `--line-length 120 --target-version py311` from the Black step. `pyproject.toml` is now the sole source of truth for those values. YAML syntax validated with `python3 -c "import yaml; yaml.safe_load(...)"`.

### WR-03: `bandit -r app -ll` runs twice

**Files modified:** `.github/workflows/backend-ci.yml`
**Commit:** 248c33c
**Applied fix:** Removed the first informational pass (`bandit -r app -ll || true`) and the surrounding echo noise. A single `bandit -r app -ll` call remains. Committed together with WR-02 since both edits touch the same file. YAML syntax validated.

### WR-04: REDACTED meta-guard false-fails on cassettes with no scrub-eligible fields

**Files modified:** `backend/tests/test_cassette_secret_audit.py`
**Commit:** f050a8a
**Applied fix:** Added a `scrub_eligible_keys` check before the `assert "REDACTED" in combined` assertion. The guard now skips (via `pytest.skip`) when none of the known scrub-eligible header/field names (`authorization`, `cookie`, `set-cookie`, `client_secret`, `refresh_token`, `api_key`, `access_token`) appear anywhere in the committed cassette tree. The REDACTED assertion is still enforced whenever scrub-eligible content IS present. Verified with `pytest -n auto -q tests/test_cassette_secret_audit.py` — 2 passed, 2 skipped (correct: detection and scrubbed-cassette meta-guards pass; the no-cassettes and no-scrub-eligible-fields paths skip as expected).

---

_Fixed: 2026-04-22T09:20:11Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
