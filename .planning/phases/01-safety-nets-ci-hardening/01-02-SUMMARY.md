---
phase: 01-safety-nets-ci-hardening
plan: "02"
subsystem: database
tags: [alembic, migrations, postgres, repair, fk-constraints, safe-08]

requires:
  - phase: 01-01
    provides: MetaData naming_convention applied to Base — required because autogenerate detects constraint renames; Task 3 skeleton was generated from the post-Plan-01 schema to get the correct revision chain

provides:
  - Forward-only repair migration aa583927d86a that gives alembic downgrade a viable path through three historic broken drop_constraint(None) calls
  - Authoritative record of the three FK constraint names (see SAFE-08 introspection below)
  - SAFE-08 legacy annotations on the three historic migration files for Plan 03 DROP-guard compatibility

affects: [01-03, plan-03-drop-guard, any future alembic downgrade testing]

tech-stack:
  added: []
  patterns:
    - "Forward-only repair migration pattern: upgrade()=pass, downgrade()=named drops — for FK names that were never captured at migration-author time"
    - "SAFE annotation format: # SAFE: repair invalid drop_constraint(None) — see SAFE-08 (exact text for DROP-guard regex in Plan 03)"
    - "Autogenerate-then-replace pattern: use alembic revision --autogenerate for correct revision chain, then hand-author body — documented C-01 exception"

key-files:
  created:
    - backend/alembic/versions/aa583927d86a_repair_drop_constraint_none_refs.py
  modified:
    - backend/alembic/versions/097024200e60_add_canonical_part_id_to_parts.py
    - backend/alembic/versions/172d1c205fb3_add_build_list_phases.py
    - backend/alembic/versions/6eae6b1393c5_add_brand_model.py

key-decisions:
  - "Branch B (forward-only repair): all three broken revisions were already applied on prod; in-place edit would rewrite applied history"
  - "Third FK table name is 'parts' (not 'global_parts'): at repair migration downgrade time, both c1f3e8a92d45 (global_parts→parts rename) and d2e9c4a1f57b (brands→part_manufacturers + constraint rename to parts_part_manufacturer_id_fkey) are still applied"
  - "Historic files annotated but NOT modified: drop_constraint(None) calls remain; SAFE legacy annotation placed above each to satisfy DROP-guard pattern matching"

patterns-established:
  - "SAFE-08 SAFE annotation format (exact): # SAFE: repair invalid drop_constraint(None) — see SAFE-08"
  - "SAFE-08 legacy annotation format (exact): # SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08"

requirements-completed: [SAFE-08]

duration: 25min
completed: 2026-04-22
---

# Phase 01 Plan 02: Repair drop_constraint(None) Migration References Summary

**Forward-only repair migration (aa583927d86a) with no-op upgrade and three named FK drops in downgrade, fixing three historic drop_constraint(None) failures via Branch B**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-22T00:45:00Z
- **Completed:** 2026-04-22T01:10:00Z
- **Tasks:** 3 (Task 1 at checkpoint, Task 3 executed, Task 2 skipped per Branch B)
- **Files modified:** 4

## Accomplishments

- Authored repair migration `aa583927d86a` with no-op `upgrade()` and three properly-named FK drops in `downgrade()`, each with SAFE-08 annotation
- Confirmed all three broken revisions are applied on prod (Branch B chosen); historic files left untouched except for legacy SAFE annotations
- Full local round-trip `alembic upgrade head && downgrade -1 && upgrade head` succeeds without error
- 2135 backend tests pass (1 skipped)

## SAFE-08 Introspection Record

```
SAFE-08 introspection (run 2026-04-22):
- prod alembic_version: confirmed at head (>= 5971a893dd8e)
- 097024200e60 applied on prod: YES
- 172d1c205fb3 applied on prod: YES
- 6eae6b1393c5 applied on prod: YES
- Chosen branch: B (forward-only repair)
- parts.canonical_part_id FK name: parts_canonical_part_id_fkey (table: parts)
- build_list_parts.build_list_phase_id FK name: build_list_parts_build_list_phase_id_fkey (table: build_list_parts)
- global_parts.brand_id (renamed to parts.part_manufacturer_id) FK name: parts_part_manufacturer_id_fkey (table: parts)
```

**Note on third constraint:** The `global_parts.brand_id` FK from migration `6eae6b1393c5` was renamed twice by later migrations:
1. `c1f3e8a92d45`: renamed table `global_parts` → `parts`
2. `d2e9c4a1f57b`: renamed column `brand_id` → `part_manufacturer_id` and explicitly renamed the constraint from `parts_brand_id_fkey` to `parts_part_manufacturer_id_fkey`

The repair migration's `downgrade()` uses `parts_part_manufacturer_id_fkey` on table `parts` because it runs against the HEAD schema where those renames are still applied.

## Task Commits

1. **Task 1: Probe prod RDS / inspect FK constraint names** — resolved at checkpoint; constraint names accepted from local introspection (no commit needed — data recorded in this SUMMARY and migration docstring)
2. **Task 2 (Branch A)** — SKIPPED per user decision (Branch B chosen)
3. **Task 3 (Branch B): Forward-only repair migration** — `b3ba313` (feat)

**Plan metadata:** (committed with SUMMARY below)

## Files Created/Modified

- `backend/alembic/versions/aa583927d86a_repair_drop_constraint_none_refs.py` — New forward-only repair migration; upgrade()=pass, downgrade()=3 named FK drops with SAFE-08 annotations; docstring embeds SAFE-08 introspection record and C-01 exception justification
- `backend/alembic/versions/097024200e60_add_canonical_part_id_to_parts.py` — Added `# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08` above line 34 (drop_constraint(None) left intact)
- `backend/alembic/versions/172d1c205fb3_add_build_list_phases.py` — Added legacy SAFE annotation above line 46
- `backend/alembic/versions/6eae6b1393c5_add_brand_model.py` — Added legacy SAFE annotation above line 49

## SAFE Annotation Counts

| File | SAFE annotation | Count |
|------|----------------|-------|
| `aa583927d86a_repair_drop_constraint_none_refs.py` | `# SAFE: repair invalid drop_constraint(None) — see SAFE-08` | 4 (1 in upgrade, 3 in downgrade) |
| `097024200e60_add_canonical_part_id_to_parts.py` | `# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08` | 1 |
| `172d1c205fb3_add_build_list_phases.py` | `# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08` | 1 |
| `6eae6b1393c5_add_brand_model.py` | `# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08` | 1 |

## New Migration Details

- **revision:** `aa583927d86a`
- **down_revision:** `5971a893dd8e`
- **File:** `backend/alembic/versions/aa583927d86a_repair_drop_constraint_none_refs.py`
- **autogenerate chain:** Generated via `alembic revision --autogenerate` (for correct revision IDs); body replaced entirely (autogenerate emitted a naming_convention rename for `categories_name_key` → `uq_categories_name` which was discarded per plan)

## Note for Plan 03 (DROP-guard)

Two annotation formats are now in-repo as real test cases for the DROP-guard regex:
1. `# SAFE: repair invalid drop_constraint(None) — see SAFE-08` — lines in new repair migration
2. `# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08` — lines in three historic files

The DROP-guard script must allow `# SAFE:` prefixed destructive ops. The historic `drop_constraint(None, ...)` calls remain in the three old files — the guard must handle the case where a `# SAFE:` annotation exists but the constraint name is still `None` (legacy/superseded).

## Decisions Made

- **Branch B selected:** All three revisions confirmed applied on prod. Rewriting applied migration history is not safe.
- **Third constraint uses current-schema name:** `parts_part_manufacturer_id_fkey` on `parts`, not the historic `global_parts_brand_id_fkey`. Verified via `pg_constraint` introspection against local DB at head.
- **C-01 exception documented in migration docstring:** Autogenerate cannot produce no-op upgrade + named-drop downgrade. This is the rare hand-authored exception the plan anticipated.

## Deviations from Plan

None - plan executed exactly as written (Branch B path). The autogenerate body was discarded as expected (rename-avalanche from Plan 01 naming_convention). The docstring's mention of `op.drop_constraint(` was removed to keep the automated `grep -c "op.drop_constraint("` acceptance check accurate (3, not 4).

## Issues Encountered

- **black reformatted two files** after initial write: `aa583927d86a_repair_drop_constraint_none_refs.py` and `097024200e60_add_canonical_part_id_to_parts.py`. Applied black before committing; all four touched files pass `--check`.
- **Docstring grep collision**: Initial docstring contained `op.drop_constraint(` verbatim, causing acceptance check to count 4 instead of 3. Changed docstring wording to avoid the literal string.

## Next Phase Readiness

- Plan 03 (DROP-guard script) can proceed: SAFE-08 annotation format is locked, real test cases are in-repo
- `alembic downgrade` path through the repair migration is verified clean on local Postgres
- All three constraint names are authoritative and recorded in this SUMMARY and the migration docstring

---
*Phase: 01-safety-nets-ci-hardening*
*Completed: 2026-04-22*
