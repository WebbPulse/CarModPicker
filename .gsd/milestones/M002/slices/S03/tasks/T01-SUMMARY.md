---
id: T01
parent: S03
milestone: M002
key_files:
  - backend/app/crawlers/compliance_audit.py
key_decisions:
  - Module-scope audit() + _classify_tier() helpers (not nested) so T03 tests can import and call them directly via capsys instead of spawning subprocesses — keeps the test suite parallel-safe and fast.
  - Skipped re-validating each declared slug against default_registry in the audit — RetailerCrawlerAdapter.__init_subclass__ already does that at import time. Audit's role is the binary compliance count; duplicating slug resolution would muddy responsibilities.
  - Hardcoded column widths (T0 (http):    etc.) and sorted-by-slug offender list keep stdout stable for S04 to grep against.
duration: 
verification_result: passed
completed_at: 2026-04-25T05:02:18.932Z
blocker_discovered: false
---

# T01: Add app/crawlers/compliance_audit.py with audit()/_classify_tier() helpers, per-tier breakdown stdout, and exit-1-with-offenders behavior

**Add app/crawlers/compliance_audit.py with audit()/_classify_tier() helpers, per-tier breakdown stdout, and exit-1-with-offenders behavior**

## What Happened

Wrote `backend/app/crawlers/compliance_audit.py` as a TDD-shaped script-as-test that pre-commits to the slice's compliance contract before T02 retrofits the adapters. The module imports `ADAPTER_REGISTRY` from `app.crawlers.adapters` (its discovery walk runs at import time and populates 108 entries), buckets each registered class by `cls.FETCHER_TIER` (`http`→T0, `tls`→T1, `browser`→T2), and checks each adapter's `category_targets` ClassVar.

Module shape matches the planner contract:
- `_classify_tier(cls) -> str` returns the canonical FETCHER_TIER string (defaults to `"http"` to mirror the base class default).
- `audit() -> int` runs the audit and prints the report; returns 0 when all compliant, 1 otherwise. Both helpers live at module scope so T03 tests can import and call them directly without subprocess overhead.
- `__main__` block calls `sys.exit(audit())`.

Compliance check uses the same gate `__init_subclass__` will accept: `getattr(cls, 'category_targets', [])` must be a `list`/`tuple` of length ≥1 with every entry a non-empty string. Per the planner notes, I deliberately did NOT re-validate slugs against `default_registry` — the base class's `__init_subclass__` already enforces that at import time, and re-running it in the audit would just duplicate work.

Stdout follows the contract S04 will consume: a `Non-compliant adapters:` block (only when offenders exist) listing `  - <slug> [<tier>]: declares no category_targets` per offender, followed by the `M002/S03 adapter compliance audit` header, three per-tier rows with hardcoded column widths, a `Total:` row, and (when 0 offenders) the `OK — every adapter declares at least one category_targets entry` trailer. Column widths are hardcoded for stable grep-ability; offenders are sorted by slug for deterministic output. Print goes to stdout (not stderr) so the gate command can pipe-capture cleanly. A defensive `??` row would surface any unknown FETCHER_TIER values if a new tier ever ships before this audit is updated; today none exist.

Today's run from `backend/` exits 1 and reports `0/83`, `0/15`, `0/10` (total 0/108) — exactly the pre-T02 baseline expected by the slice plan. After T02 retrofits each adapter, the same command will print `108/108 compliant` and exit 0.

## Verification

Ran the task plan's exact verify command from `backend/`: `python -m app.crawlers.compliance_audit` exited 1 (matches `test $? -eq 1`), and `python -m app.crawlers.compliance_audit | grep -q 'Non-compliant adapters:'` matched. Output reports `0/83 + 0/15 + 0/10 = 0/108` non-compliant, matching the pre-T02 baseline declared in the slice plan (T0:83, T1:15, T2:10). Smoke-tested module-level imports — `from app.crawlers.compliance_audit import audit, _classify_tier` succeeds, so T03 can import the helpers directly without subprocess. Pyright reports 0 errors / 0 warnings on the new file.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && python -m app.crawlers.compliance_audit` | 1 | pass (expected 1 pre-T02; reports 0/108 compliant with full offender list) | 1500ms |
| 2 | `python -m app.crawlers.compliance_audit | grep -q 'Non-compliant adapters:'` | 0 | pass | 1500ms |
| 3 | `python -c 'from app.crawlers.compliance_audit import audit, _classify_tier'` | 0 | pass (module-scope helpers importable for T03) | 800ms |
| 4 | `pyright app/crawlers/compliance_audit.py` | 0 | pass (0 errors, 0 warnings) | 4000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/app/crawlers/compliance_audit.py`
