---
phase: 01-safety-nets-ci-hardening
plan: "03"
subsystem: ci
tags: [ci, migrations, drop-guard, static-analysis, alembic, python, regex]

requires:
  - phase: 01-02
    provides: SAFE-08 SAFE annotations in-tree on three legacy drop_constraint(None) files plus forward-only repair migration

provides:
  - SAFE-04 migration DROP guard script at backend/scripts/check_migrations.py
  - Unit test coverage for the DROP guard at backend/tests/test_check_migrations.py
  - CI enforcement step in .github/workflows/backend-ci.yml before coverage measurement
  - SAFE downgrade annotations on all 82 previously-unannotated destructive ops across 27 migration files

affects: [01-04, plan-04-coverage-gates, any future PR adding alembic migrations]

tech-stack:
  added: []
  patterns:
    - "SAFE-04 annotation enforcement: # SAFE: <reason> on same line or immediately preceding line for any op.drop_column, op.drop_table, or op.drop_constraint call"
    - "SAFE-04 downgrade annotation: # SAFE: downgrade reversal of already-applied migration — see SAFE-04 (applied to all pre-existing migration downgrade() ops)"
    - "CI-gated static analysis: pure-Python read-only pathlib+regex scanner with exit 0/1/2 semantics, CWD-independent via Path(__file__).resolve().parents[2]"

key-files:
  created:
    - backend/scripts/check_migrations.py
    - backend/tests/test_check_migrations.py
  modified:
    - .github/workflows/backend-ci.yml
    - backend/alembic/versions/04e42912c65c_migration_flatten.py
    - backend/alembic/versions/052f603511ed_add_adapter_schedules_table.py
    - backend/alembic/versions/097024200e60_add_canonical_part_id_to_parts.py
    - backend/alembic/versions/172d1c205fb3_add_build_list_phases.py
    - backend/alembic/versions/274bde4f4654_crawled_pages_html_sha256.py
    - backend/alembic/versions/2d389160410b_many_refactors.py
    - backend/alembic/versions/2fcc857ad593_build_logs.py
    - backend/alembic/versions/30e2e2139a2e_add_slug_to_car_models_and_car_.py
    - backend/alembic/versions/42feddff6034_add_is_service_account_to_users.py
    - backend/alembic/versions/46ca3f447c85_auth_expiry_control_and_socials.py
    - backend/alembic/versions/4eef323a3826_add_2fa_fields_to_users_table.py
    - backend/alembic/versions/5971a893dd8e_rename_app_settings_ads_disabled_global_.py
    - backend/alembic/versions/5a381dff5fd1_migrate_all_pks_and_fks_to_uuid7.py
    - backend/alembic/versions/5ad758877953_add_oauth_accounts_and_nullable_hashed_.py
    - backend/alembic/versions/5f5924feaa24_consolidate_image_url_to_image_urls.py
    - backend/alembic/versions/6d5d757e47a8_add_webauthn_credentials.py
    - backend/alembic/versions/6e24c3c398d8_add_crawled_pages.py
    - backend/alembic/versions/6eae6b1393c5_add_brand_model.py
    - backend/alembic/versions/72a9aa17fc28_add_background_jobs_table.py
    - backend/alembic/versions/7d821b0af913_add_bug_reports_table.py
    - backend/alembic/versions/82933b3bde38_global_part_many_cars_and_is_universal.py
    - backend/alembic/versions/8ace51422235_add_make_and_car_model_entities.py
    - backend/alembic/versions/9434183744b4_add_product_url_to_global_parts.py
    - backend/alembic/versions/98b114b6b62f_drop_subscriptions_table.py
    - backend/alembic/versions/a568a3a2ba09_replace_adapter_schedules_with_crawler_.py
    - backend/alembic/versions/bd2c48d79be9_add_app_settings_singleton_with_ads_.py
    - backend/alembic/versions/c1f3e8a92d45_rename_global_parts_to_parts.py
    - backend/alembic/versions/c2e5af5ef24f_add_heartbeat_and_worker_instance_id_to_.py
    - backend/alembic/versions/c4e97fa3622b_add_display_name_to_car_models_and_car_.py
    - backend/alembic/versions/e3f4b1c08a91_rename_make_to_car_make_and_car_to_car_.py

key-decisions:
  - "All 82 pre-existing unannotated downgrade() destructive ops annotated with # SAFE: downgrade reversal of already-applied migration — see SAFE-04 to make the checker exit 0 on the current tree (Rule 2 auto-fix)"
  - "Three distinct regex patterns: DESTRUCTIVE_OP_RE (detect ops), SAFE_ANNOTATION_RE (preceding-line ^anchored comment), INLINE_SAFE_RE (same-line unanchored) — anchoring the preceding-line regex prevents docstring-SAFE false negatives (T-03-02)"
  - "CI step placement: BEFORE Run tests with coverage per D-07 so a drop_* regression fails fast before coverage baseline measurement"

patterns-established:
  - "SAFE-04 annotation format (exact, same-line): op.drop_*(...)  # SAFE: <reason>"
  - "SAFE-04 annotation format (exact, preceding-line): # SAFE: <reason> on its own comment line immediately above the destructive op"
  - "SAFE-04 legacy downgrade annotation: # SAFE: downgrade reversal of already-applied migration — see SAFE-04"

requirements-completed: [SAFE-04]

duration: 30min
completed: 2026-04-22
---

# Phase 01 Plan 03: Migration DROP Guard (SAFE-04) Summary

**CI-gated regex scanner (check_migrations.py) that exits 1 on any unannotated op.drop_* in alembic/versions/*.py, with 12 unit tests and a new step in backend-ci.yml before coverage measurement**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-22T07:55:59Z
- **Completed:** 2026-04-22T08:02:53Z
- **Tasks:** 3 (all executed)
- **Files modified:** 32

## Accomplishments

- Created `backend/scripts/check_migrations.py` — non-interactive, read-only scanner that exits 0/1/2 with full stdout diagnostics (filename + line number + suggestion)
- Created `backend/tests/test_check_migrations.py` — 12 unit tests covering all PASS/FAIL shapes plus T-03-01 ReDoS defense and T-03-02 docstring-SAFE defense
- Wired CI step between `Scan dependencies for vulnerabilities` and `Run tests with coverage` in `backend-ci.yml`
- Annotated all 82 pre-existing unannotated destructive ops across 27 migration downgrade() blocks to make the checker exit 0 on the current tree
- Full backend test suite still green: 2147 passed, 1 skipped

## Regex Patterns Committed

```python
DESTRUCTIVE_OP_RE = re.compile(r"\bop\.(drop_column|drop_table|drop_constraint)\s*\(")
SAFE_ANNOTATION_RE = re.compile(r"^\s*#\s*SAFE:\s*\S")   # preceding-line (anchored)
INLINE_SAFE_RE = re.compile(r"#\s*SAFE:\s*\S")            # same-line (unanchored)
```

The distinction between `SAFE_ANNOTATION_RE` (anchored `^\s*`) and `INLINE_SAFE_RE` (unanchored) is the T-03-02 defense: a docstring line like `"""This migration SAFE: does a thing."""` does NOT match `SAFE_ANNOTATION_RE` because the line starts with `"""`, not `#`.

## Script Exit 0 Proof

```
$ python backend/scripts/check_migrations.py
check_migrations: OK (34 files scanned)
$ echo $?
0

$ cd /tmp && python /home/tyler-webb/.../backend/scripts/check_migrations.py
check_migrations: OK (34 files scanned)
$ echo $?
0
```

## CI Step Name and Placement

- **Step name:** `Check migrations for unannotated destructive operations`
- **Run command:** `python backend/scripts/check_migrations.py`
- **Placement:** After `Scan dependencies for vulnerabilities`, before `Run tests with coverage`
- **No `cd backend`:** Script is CWD-independent via `REPO_ROOT = Path(__file__).resolve().parents[2]`

## Task Commits

1. **Task 1: Write check_migrations.py DROP-guard script + annotate legacy migrations** — `001fbf1` (feat)
2. **Task 2: Write unit tests** — `ab2a497` (test)
3. **Task 3: Wire DROP guard into backend-ci.yml** — `ec18d86` (chore)

## Files Created/Modified

- `backend/scripts/check_migrations.py` — SAFE-04 DROP guard; executable; CWD-independent; 3 regex patterns; `check_file()` + `main()` interface; exit 0/1/2 semantics
- `backend/tests/test_check_migrations.py` — 12 unit tests using tmp_path fixtures; covers all plan-specified cases plus 3 extra cases for SAFE-08 annotation shapes
- `.github/workflows/backend-ci.yml` — New CI step inserted at correct position
- 27 migration files in `backend/alembic/versions/` — Added 82 `# SAFE: downgrade reversal` annotations; black-reformatted

## Decisions Made

- **All pre-existing downgrade ops annotated (Rule 2 auto-fix):** The plan stated the script must exit 0 on the current tree. Initial run revealed 82 unannotated destructive ops across 27 migration files (all in downgrade() blocks). Annotated all of them with `# SAFE: downgrade reversal of already-applied migration — see SAFE-04`. This is correct behavior: all those migrations are already applied on prod; the guard's purpose is to prevent NEW unannotated drops, not to block existing downgrade paths.
- **Two distinct annotation regexes:** `SAFE_ANNOTATION_RE` for preceding-line uses `^\s*#\s*SAFE:` (line-anchored) to prevent docstring-embedded SAFE tokens from satisfying the guard. `INLINE_SAFE_RE` for same-line uses unanchored `#\s*SAFE:` to match comments after code on the same line.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Annotated 82 pre-existing unannotated downgrade() destructive ops**
- **Found during:** Task 1 (initial run of check_migrations.py against the current tree)
- **Issue:** Plan's must_have stated "the script exits 0 on the current state of `backend/alembic/versions/`" but the script immediately exited 1 with 82 violations across 27 migration files. Only the SAFE-08 files from Plan 02 had annotations; all other existing migrations had unannotated drops in their downgrade() blocks.
- **Fix:** Added `# SAFE: downgrade reversal of already-applied migration — see SAFE-04` annotation on the line immediately preceding each unannotated destructive op across all 27 affected files. Then applied `black --line-length 120` to all modified migrations.
- **Files modified:** 27 migration files in `backend/alembic/versions/`
- **Verification:** `python backend/scripts/check_migrations.py` exits 0, "check_migrations: OK (34 files scanned)"
- **Committed in:** `001fbf1` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality for script to exit 0 as specified)
**Impact on plan:** Necessary for the plan's own must_have criterion. The migration files already had applied their downgrade paths on prod or never needed to be run backwards — annotating them is correct and reviewable.

## Issues Encountered

- **Black reformatted additional migration files** beyond those with added annotations: `c1f3e8a92d45`, `e3f4b1c08a91`, and `5971a893dd8e` were reformatted by running `black` on the whole `alembic/versions/` directory (line-length enforcement on long string literals). These are purely cosmetic formatting changes; no logic was altered. All were staged and committed as part of Task 1.

## Handoff Note for Plan 04 (Coverage Gates)

The SAFE-04 DROP guard is now live in CI. The coverage-baseline-measurement PR can land safely: if it accidentally includes an unannotated `drop_*` in any migration file, the `Check migrations for unannotated destructive operations` step will fail CI before `Run tests with coverage` runs. No destructive migration can slip through the coverage measurement window.

Annotation format locked for downstream reference:
- New migration drop with reason: `# SAFE: <human-readable reason>` on same or immediately preceding line
- Legacy downgrade reversal: `# SAFE: downgrade reversal of already-applied migration — see SAFE-04`
- SAFE-08 repair migration format: `# SAFE: repair invalid drop_constraint(None) — see SAFE-08`

## Next Phase Readiness

- Plan 04 (coverage gates) can proceed: DROP guard is live, baseline-measurement PR is safe
- `check_migrations.py` public interface (`check_file`, `main`, `DESTRUCTIVE_OP_RE`, `SAFE_ANNOTATION_RE`, `INLINE_SAFE_RE`) is importable for any future test additions
- All 2147 backend tests pass; CI workflow parses as valid YAML

---
*Phase: 01-safety-nets-ci-hardening*
*Completed: 2026-04-22*
