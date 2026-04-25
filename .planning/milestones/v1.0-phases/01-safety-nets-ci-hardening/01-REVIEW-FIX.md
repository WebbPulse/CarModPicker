---
phase: 01-safety-nets-ci-hardening
fixed_at: 2026-04-23T05:48:16Z
review_path: .planning/phases/01-safety-nets-ci-hardening/01-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 6
skipped: 3
status: partial
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-23T05:48:16Z
**Source review:** .planning/phases/01-safety-nets-ci-hardening/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (4 Warning + 5 Info, `fix_scope: all`)
- Fixed: 6 (4 from prior run, 2 new in this run)
- Skipped: 3 (all Info, advisory-only or intentional trade-off)

Re-run of the fixer against Phase 01 with `--all` flag so Info findings are in
scope. The four Warning findings were already fixed in a prior iteration; their
fixes have been re-verified in place and are listed under **Already-Fixed** so
the report accurately reflects the full 9-finding scope.

## Already-Fixed (from prior run)

These four fixes were committed in an earlier code-review-fix iteration. I
re-read each target file to confirm the fixes are still in place (they are —
no drift from the prior report).

### WR-01: pytest.ini `testpaths` points at non-existent directory

**Files modified:** `backend/pytest.ini`
**Commit:** 4382475
**Verified:** Line 2 reads `testpaths = tests`.

### WR-02: Backend CI passes Black args that duplicate pyproject.toml

**Files modified:** `.github/workflows/backend-ci.yml`
**Commit:** 248c33c (combined with WR-03)
**Verified:** Line 38 is `black --config pyproject.toml --check --diff .` — the
redundant `--line-length 120 --target-version py311` flags have been removed.

### WR-03: `bandit -r app -ll` runs twice

**Files modified:** `.github/workflows/backend-ci.yml`
**Commit:** 248c33c (combined with WR-02)
**Verified:** The "Run security scan" step at lines 50-58 contains a single
`bandit -r app -ll` call; the prior informational `|| true` pass has been
removed.

### WR-04: REDACTED meta-guard false-fails on cassettes with no scrub-eligible fields

**Files modified:** `backend/tests/test_cassette_secret_audit.py`
**Commit:** f050a8a
**Verified:** `test_cassette_audit_redacted_markers_present_when_cassettes_exist`
at lines 146-186 now gates the `REDACTED` assertion on presence of any
scrub-eligible key (`authorization`, `cookie`, `set-cookie`, `client_secret`,
`refresh_token`, `api_key`, `access_token`) in the combined cassette text.

## Fixed Issues

### IN-02: `test_metadata_naming_convention.py` imports inside the test function

**Files modified:** `backend/tests/test_metadata_naming_convention.py`
**Commit:** 3ed7c31
**Applied fix:** Moved `from app.db.base_class import Base` from the two
function bodies to a single module-top import below `from __future__ import
annotations`. Both test functions now reference the module-level `Base`.
Verified with `python -m pytest -n auto tests/test_metadata_naming_convention.py
--no-cov` — 2 passed.

### IN-05: Event listeners in `conftest.py` use `# type: ignore[no-untyped-def]`

**Files modified:** `backend/tests/conftest.py`
**Commit:** 575724d
**Applied fix:** Replaced the two `# type: ignore[no-untyped-def]` comments
on `_disable_pysqlite_autobegin` and `_emit_begin` with explicit `Any`
annotations on their positional params and `-> None` return types. `Any` was
already imported from `typing` at line 6 — no new import needed. SQLAlchemy's
event-callback signature is dynamic, so `Any` is the correct annotation.
Verified with `pyright tests/conftest.py` (0 errors, 0 warnings) and
`pytest -n auto tests/test_metadata_naming_convention.py --no-cov` (2 passed,
confirming conftest still loads).

## Skipped Issues

### IN-01: `backend/tests/auth/__init__.py` is empty

**File:** `backend/tests/auth/__init__.py:1`
**Reason:** Advisory-only; review explicitly marks "No change required for this
review." Consistency check: `backend/tests/__init__.py` and
`backend/tests/crawlers/__init__.py` are also empty, so the empty
`auth/__init__.py` matches the existing convention. Deleting it would create
inconsistency with sibling test packages. Leaving as-is.

### IN-03: Duplicated parse-test scaffolding across 5 crawler characterization tests

**Files:** `backend/tests/crawlers/test_characterization_{amsperformance,briantooleyracing,cobbtuning,subispeed,texasspeed}.py`
**Reason:** Advisory-only; the review itself notes "Keeping the per-adapter
test-file layout may be intentional so that each adapter's regeneration
one-liner is co-located with its test — if so, the duplication is a deliberate
trade-off. No action required if the duplication is intentional." This is a
judgment-call refactor that the review explicitly flags as non-obligatory.
Co-located regen comments have operational value (a developer regenerating
one adapter's fixtures sees the exact command next to the test). Skipping so
the trade-off remains the developer's choice rather than being eliminated by
the fixer.

### IN-04: `open-pull-requests-limit: 10` in dependabot.yml

**File:** `.github/dependabot.yml:25,42,55`
**Reason:** Advisory-only; review says "No change required if the current
defaults are acceptable." This is purely a tuning preference (PR-noise vs.
backlog-clearing rate), not a correctness or security issue. No action taken.

---

_Fixed: 2026-04-23T05:48:16Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
