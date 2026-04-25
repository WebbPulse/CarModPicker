---
phase: 01-safety-nets-ci-hardening
plan: "01"
subsystem: database
tags: [sqlalchemy, metadata, naming-convention, alembic, orm]

# Dependency graph
requires: []
provides:
  - "declarative Base with MetaData(naming_convention=5-key SQLAlchemy convention) at backend/app/db/base_class.py"
  - "unit test pinning all 5 naming_convention keys and template strings at backend/tests/test_metadata_naming_convention.py"
affects:
  - "01-02-PLAN (SAFE-08: repair migrations reference this naming foundation)"
  - "any future alembic autogenerate (inherits naming convention via Base.metadata)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLAlchemy MetaData(naming_convention=...) attached to declarative_base — forward-only convention for new constraints"

key-files:
  created:
    - "backend/tests/test_metadata_naming_convention.py"
  modified:
    - "backend/app/db/base_class.py"

key-decisions:
  - "Forward-only convention (D-12): no alembic revision --autogenerate run; no migration file produced in this plan"
  - "5-key SQLAlchemy-recommended convention (D-11): ix, uq, ck, fk, pk with standard templates"
  - "Function-scope imports in test file for conftest env-var ordering safety"

patterns-established:
  - "base_class.py: NAMING_CONVENTION dict + MetaData(naming_convention=...) + declarative_base(metadata=metadata)"
  - "Unit test pins both key set AND individual template strings to catch any future drift"

requirements-completed:
  - SAFE-09

# Metrics
duration: 2min
completed: "2026-04-22"
---

# Phase 01 Plan 01: SQLAlchemy MetaData Naming Convention Summary

**SQLAlchemy declarative Base extended with 5-key MetaData naming convention (ix/uq/ck/fk/pk), pinned by a 2-test unit test asserting both key set and template strings.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-22T07:40:54Z
- **Completed:** 2026-04-22T07:43:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extended `backend/app/db/base_class.py` from 3 lines to 32 lines with `NAMING_CONVENTION` dict + `MetaData(naming_convention=NAMING_CONVENTION)` + `declarative_base(metadata=metadata)`
- Created `backend/tests/test_metadata_naming_convention.py` with 2 tests that pin all 5 convention keys and each template string value
- Full backend test suite (2135 tests) remains green with no regressions

## Convention Dict Committed

```python
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

## Task Commits

Each task was committed atomically:

1. **Task 1: Apply MetaData(naming_convention=...) to Base in base_class.py** - `04fc7d3` (feat)
2. **Task 2: Add unit test asserting the 5 naming_convention keys** - `68a4ca9` (test)

**Plan metadata:** committed with SUMMARY.md (docs)

## Files Created/Modified

- `backend/app/db/base_class.py` — Extended from 3 lines (bare `declarative_base()`) to 32 lines with full `NAMING_CONVENTION` dict and `MetaData(naming_convention=NAMING_CONVENTION)` wired to `declarative_base(metadata=metadata)`
- `backend/tests/test_metadata_naming_convention.py` — New test file with `test_metadata_naming_convention_has_five_expected_keys` and `test_metadata_naming_convention_fk_template_is_sqlalchemy_recommended`

## Decisions Made

- **Forward-only (D-12):** No `alembic revision --autogenerate` was run. Running it would produce a rename-avalanche migration trying to apply the new convention to all ~30+ existing constraints — that migration must be discarded. Per plan specification, this change takes effect only for genuinely new schema objects.
- **No migration file produced:** This is intentional. The naming convention is purely forward-looking; no schema DDL is changed by this plan.
- **Black reformatted the test set assertion:** The `assert set(convention.keys()) == {"ix", "uq", "ck", "fk", "pk"}` expression was reformatted by black to expand the set literal across multiple lines (line-length 120 constraint). Applied black's output verbatim.

## Deviations from Plan

None — plan executed exactly as written. Black formatting applied one minor style change to the test set literal (multi-line expansion), which is expected behavior for black and does not constitute a deviation.

## Issues Encountered

None.

## Handoff Note for Plan 02 (SAFE-08: Repair Migrations)

- The naming convention is now active for all future `alembic revision --autogenerate` runs
- Repair migrations for the three broken `drop_constraint(None, ...)` files may cite the new convention names in comments, but the actual constraint names inspected from live RDS will be the Postgres auto-generated names (e.g., `parts_canonical_part_id_fkey`), NOT the new-convention names (e.g., `fk_parts_canonical_part_id_parts`)
- Do NOT reference `NAMING_CONVENTION` values when naming constraints in repair migrations — use `SELECT conname FROM pg_constraint` introspection against the live DB to get actual names

## Known Stubs

None — no stubs, placeholders, or hardcoded empty values introduced.

## Threat Flags

None — this plan makes no network changes, no new endpoints, no auth path changes. Pure ORM configuration change with a unit test.

## Next Phase Readiness

- SAFE-09 complete: naming convention foundation is in place
- Plan 02 (SAFE-08) can now proceed to repair the three broken `drop_constraint(None, ...)` migration files, knowing the naming convention context
- The unit test will catch any future drift in the convention (drop a key → CI fails in < 2s)

---
*Phase: 01-safety-nets-ci-hardening*
*Completed: 2026-04-22*
