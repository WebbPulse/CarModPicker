---
phase: 07-v1-residue-cleanup
fixed_at: 2026-04-24T07:30:00Z
review_path: .planning/phases/07-v1-residue-cleanup/07-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 7
skipped: 1
status: partial
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-04-24T07:30:00Z
**Source review:** `.planning/phases/07-v1-residue-cleanup/07-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (2 warnings + 6 info)
- Fixed: 7
- Skipped: 1 (explicitly marked "No action required" by reviewer)

## Fixed Issues

### WR-01: IN-03 re-export leaves a semantically-divergent duplicate `validate_pagination_params`

**Files modified:** `backend/app/api/utils/endpoint_decorators.py`, `backend/app/api/utils/common_operations.py`, `backend/app/api/utils/common_patterns.py`
**Commit:** `b7376a3`
**Applied fix (documentation-only variant):** Added cross-referencing docstrings on both `validate_pagination_params` definitions explaining the divergent contracts and extended the IN-03 comment in `common_patterns.py` to point at the deeper duplication.

**Why documentation-only rather than Option A consolidation:**
Picking one contract and migrating the ~20 call sites across 12+ modules (build_lists, parts, car_generations, categories, part_manufacturers, build_logs, search, users, base_crud_service, car_generation_service, and their tests) is a non-trivial refactor that changes error-handling behaviour for every paginated endpoint — callers currently do `skip, limit = validate_pagination_params(skip, limit)` and rely on clamping, while service-layer callers use the raising variant and discard the return value. Collapsing one into the other without auditing all call sites would silently break pagination error handling. The reviewer's "at minimum, add a comment" fallback was applied here. The consolidation itself is deferred to a dedicated refactor pass — **requires architectural decision**.

### WR-02: New per-adapter alarms silently fan out without `actions_enabled` control

**Files modified:** `terraform/monitoring.tf`, `terraform/variables.tf`
**Commit:** `2f95868`
**Applied fix:** Added `variable "enable_per_adapter_alarms"` (bool, default true) and wired it to the `actions_enabled` attribute on the `crawler_parse_failure_per_adapter` resource. Operators can now silence the entire 108-alarm fan-out with a single variable flip during a retailer-wide outage without tearing down alarm resources or losing CloudWatch alarm history.
**Verification:** `terraform fmt -check` passes; `terraform validate` reports 0 errors, 0 warnings.

### IN-01: Pre-existing tautology in `test_copy_build_list_ownership`

**Files modified:** `backend/tests/api/endpoints/test_build_lists.py`
**Commit:** `78fc31d`
**Applied fix:** Changed `copied_build_list["user_id"] != original_owner.id` to `!= str(original_owner.id)` so the comparison is str-vs-str (both sides) and actually tests the intended invariant rather than being a tautology across incompatible types.
**Verification:** `pytest -n auto -k test_copy_build_list_ownership` passes.

### IN-02: `test_copy_free_tier_cap` hard-codes line-number references

**Files modified:** `backend/tests/api/endpoints/test_build_lists.py`
**Commit:** `b25fdc7`
**Applied fix:** Replaced two bit-rot-prone line-number breadcrumbs (`build_list_service.py:281-292`, `error_handler.py:105`) with function-name anchors (`copy_build_list`, `handle_http_exception`). Function names survive line shifts from unrelated edits. Verified `handle_http_exception` exists at the cited path before committing.
**Verification:** `pytest -n auto -k test_copy_free_tier_cap` passes.

### IN-03: `test_lifespan_bg_log_context` does not assert `user_id_var`

**Files modified:** `backend/tests/test_lifespan_bg_log_context.py`
**Commit:** `6c949c2`
**Applied fix:** Both sweep tests now capture `(request_id_var.get(), user_id_var.get())` as a tuple rather than just `request_id_var`, and assert on `[(expected_request_id, "bg")]`. A future refactor that silently drops the `user_id_var.set("bg")` assignment inside `bg_log_context` will now trip these regression guards.
**Verification:** All 3 tests in the file pass.

### IN-04: `test_build_lists_in01_helper.py` relies on substring matching

**Files modified:** `backend/tests/test_build_lists_in01_helper.py`
**Commit:** `e832125`
**Applied fix:** Rewrote the helper-existence and call-site tests to use `ast.parse` + walk. `test_apply_build_list_filters_helper_exists` now asserts exactly 1 `FunctionDef` node; `test_helper_invoked_from_both_count_and_main_select` asserts exactly 2 `Call` nodes. This eliminates the false-positive path where a docstring or comment mentioning `_apply_build_list_filters` could satisfy the old `>=3 occurrences` threshold even if real call sites regressed from 2 to 1.
**Verification:** All 3 tests in the file pass.

### IN-05: `adapter_names.txt` format convention is implicit

**Files modified:** `terraform/monitoring.tf`, `terraform/README.md`
**Commit:** `86b0cfb`
**Applied fix:** Added a defensive `_adapter_names_clean` locals filter that trims each line and drops empty entries before `setsubtract(...)`. Bad input (blank mid-lines, trailing whitespace, stray `\r` from Windows line endings) now fails loudly at plan time or produces a clean adapter set rather than a malformed alarm name like `...-crawler-parse-failure-` (empty suffix, rejected by CloudWatch) or `...-crawler-parse-failure-adro\r` (dimension-mismatch failure). Also documented the canonical format in `terraform/README.md` next to the regeneration command (lowercase, one-per-line, trailing newline, no blank lines, no trailing whitespace, LF-only).
**Verification:** `terraform fmt -check` passes; `terraform validate` reports 0 errors.

## Skipped Issues

### IN-06: `test_env_fallback_accepts_uuid_string` does not cover the `UUID(...)` call-site error path explicitly

**File:** `backend/tests/crawlers/test_crawler_user_fallback.py:75-89`
**Reason:** Skipped by design — reviewer explicitly wrote **"No action required"** in the Fix section. The review body notes that the full test set (positive + negative) already covers the intended behaviour; the observation is recorded for future test-set audits as guidance ("when pinning 'function X uses parser Y instead of parser Z', prefer asserting parser type via monkeypatch or observing a value only parser Y produces") rather than a concrete deficiency to repair.
**Original issue:** The positive test relies on error-message matching for the negative case. In theory, a buggy variant using `int(raw)` could raise with a matching message and pass the negative test. In practice, `_get_crawler_user` explicitly catches `ValueError` and re-raises as `CrawlerConfigError("must be a valid UUID")`, so the test suite is airtight.

---

_Fixed: 2026-04-24T07:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
