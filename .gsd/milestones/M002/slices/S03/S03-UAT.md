# S03: 108-adapter category_targets compliance retrofit + audit + PR-time gate — UAT

**Milestone:** M002
**Written:** 2026-04-25T05:14:05.471Z

# S03 UAT — 108-adapter compliance retrofit + audit gate

## Preconditions

- Working directory: `/home/tyler-webb/Documents/Github/CarModPicker`
- Python env active (Python 3.13 with backend deps installed)
- HEAD includes the three S03 commits (T01 audit script, T02 retrofit, T03 pytest gates)
- No live network or DB needed — all checks run against in-process registry

## Test 1: Compliance audit runs clean (slice demo)

**Steps:**
1. `cd backend && python -m app.crawlers.compliance_audit`

**Expected:**
- Exit code 0
- Stdout contains:
  ```
  M002/S03 adapter compliance audit
    T0 (http):    83/83 compliant
    T1 (tls):     15/15 compliant
    T2 (browser): 10/10 compliant
    Total:        108/108 compliant
  OK — every adapter declares at least one category_targets entry
  ```

## Test 2: Spot-check specialist adapters declare concrete slugs

**Steps:**
1. `cd backend && python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; print('wilwood:', ADAPTER_REGISTRY['wilwood'].category_targets); print('bcracing:', ADAPTER_REGISTRY['bcracing'].category_targets); print('atpturbo:', ADAPTER_REGISTRY['atpturbo'].category_targets); print('jegs:', ADAPTER_REGISTRY['jegs'].category_targets)"`

**Expected:**
- `wilwood: ['brake', 'universal']`
- `bcracing: ['coilover', 'universal']`
- `atpturbo: ['turbo', 'universal']`
- `jegs: ['universal']` (mixed-catalog reseller, gets the floor)

## Test 3: Parametrized pytest gate fails by adapter slug

**Steps:**
1. `pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto --rootdir=backend`

**Expected:**
- Exit 0
- 218 tests pass (108 declarations + 108 resolutions + 1 specialist spot-check + 1 total-count)
- Test ids include the adapter slug (e.g. `test_every_adapter_declares_category_targets[wilwood]`) so any future failure points at the offending adapter directly

## Test 4: compliance_audit stdout-contract tests

**Steps:**
1. `pytest backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend`

**Expected:**
- Exit 0
- 3 tests pass: passes-when-all-compliant, per-tier-breakdown-in-stdout, reports-offenders-when-non-compliant

## Test 5: Helper script is idempotent

**Steps:**
1. `cd backend && python scripts/m002_s03_apply_category_targets.py`

**Expected:**
- Exit 0
- Reports `0 updated, 108 already-present` (or equivalent — no adapter file modified on re-run)

## Test 6: Full crawler test suite stays green

**Steps:**
1. `pytest backend/tests/crawlers/ -n auto --rootdir=backend`

**Expected:**
- Exit 0
- 1585 passed, 1 skipped (no regressions from the 108-file retrofit)

## Test 7: Negative case — synthetic non-compliance is reported

**Steps:**
1. Create a temp branch
2. Hand-edit one adapter (e.g. `backend/app/crawlers/adapters/tier0_http/jegs.py`) and remove its `category_targets: ClassVar[list[str]] = ["universal"]` line
3. Run `cd backend && python -m app.crawlers.compliance_audit`

**Expected:**
- Exit code 1
- Stdout begins with `Non-compliant adapters:` followed by `  - jegs [http]: declares no category_targets`
- The Total line reads `Total: 107/108 compliant`
- Restore the line; audit returns to 108/108 / exit 0

## Edge Cases Covered

- **Specialists declare `[<concrete>, "universal"]`** — never just the concrete slug alone, so even if a specialist's part doesn't categorize as the specialty (e.g. a Wilwood master cylinder kit) the universal floor still applies.
- **Mixed-catalog adapters get `["universal"]`** — safe because the S02 category-name → sub-slug bridge routes any non-coilover/brake/turbo payload to UniversalSpec.
- **Registry is 108, not 111** — the IS_FALLBACK GenericHtmlParser per tier (3 total) is excluded from `ADAPTER_REGISTRY` by `__init_subclass__` per D-03; audit and tests treat 108 as canonical.
- **Helper script is the source of truth for the specialist mapping** — committed under `backend/scripts/m002_s03_apply_category_targets.py`. Future specialist adapters should be added to `SPECIALIST_MAPPING` there before the per-file edit.
