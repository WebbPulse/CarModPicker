---
id: T03
parent: S03
milestone: M002
key_files:
  - backend/tests/crawlers/test_adapter_category_targets.py
  - backend/tests/crawlers/test_compliance_audit.py
key_decisions:
  - Used pytest.mark.parametrize ids=lambda nc: nc[0] so the failing line reads [<adapter_slug>] verbatim — turns the 'which adapter forgot category_targets' question into a one-glance read of the CI failure output.
  - Mocked the bad-adapter fixture with types.SimpleNamespace instead of declaring a RetailerCrawlerAdapter subclass — avoids __init_subclass__'s ADAPTER_NAME enforcement and any cross-test global registry side effects (per MEM025).
  - Patched compliance_audit.ADAPTER_REGISTRY at the import site (per MEM017), not app.crawlers.adapters.ADAPTER_REGISTRY at the source — the audit module binds the name at import, so the patch must hit the bound name where it's actually read.
  - Asserted the dynamic Total line as `Total: <n>/<n>` using len(ADAPTER_REGISTRY) instead of hardcoding 108 — keeps the test stable when adapters are added/removed without churning T03 every time.
duration: 
verification_result: passed
completed_at: 2026-04-25T05:10:09.580Z
blocker_discovered: false
---

# T03: Add parametrized adapter category_targets gate + compliance_audit stdout-contract tests so PR-time CI fails by adapter slug on non-compliance

**Add parametrized adapter category_targets gate + compliance_audit stdout-contract tests so PR-time CI fails by adapter slug on non-compliance**

## What Happened

Wrote two test modules that pin the M002/S03 schema-contract substrate at PR time:

1. `backend/tests/crawlers/test_adapter_category_targets.py` — four tests:
   - `test_every_adapter_declares_category_targets` parametrized over `sorted(ADAPTER_REGISTRY.items())` with `ids=lambda nc: nc[0]` so a violation surfaces as `[<adapter_slug>] FAILED` directly.
   - `test_every_category_target_resolves_via_registry` (also parametrized) — belt-and-suspenders for `__init_subclass__`'s slug-resolution check; restates the contract in pytest output instead of as an opaque import-time TypeError.
   - `test_specialist_adapters_declare_concrete_slugs` — explicit spot-check per the S03 demo for the brake (girodisc/essexparts/wilwood), coilover (bcracing/kwsuspensions/fortuneauto/tein/stanceusa), and turbo (atpturbo/fullrace) mappings.
   - `test_total_compliance_count_matches_registry` — catches a future PR that removes `category_targets` from one adapter without dropping the adapter.

2. `backend/tests/crawlers/test_compliance_audit.py` — three tests pinning the `audit()` script-as-test:
   - `test_audit_passes_when_all_compliant(capsys)` — calls `audit()` directly, asserts return code 0 and the dynamic `Total: <n>/<n> compliant` line plus the OK banner.
   - `test_audit_per_tier_breakdown_in_stdout(capsys)` — asserts `T0 (http):`, `T1 (tls):`, `T2 (browser):` each appear exactly once.
   - `test_audit_reports_offenders_when_non_compliant(monkeypatch, capsys)` — patches `compliance_audit.ADAPTER_REGISTRY` (the import site, per MEM017) with a `{good, bad}` SimpleNamespace fixture, asserts return code 1, the `Non-compliant adapters:` block names `_t03_bad_adapter`, the compliant slug stays out of the offenders block, and the totals line reflects `1/2`.

Per MEM025 the bad-adapter fixture is a `types.SimpleNamespace`, not an ad-hoc `RetailerCrawlerAdapter` subclass — declaring a subclass would trip `__init_subclass__`'s non-empty `ADAPTER_NAME` check. Per MEM017 the patch target is `app.crawlers.compliance_audit.ADAPTER_REGISTRY`, not `app.crawlers.adapters.ADAPTER_REGISTRY` — Python resolves the bound name at the call site inside the audit module. Per MEM019 the slice verify line stays a single pytest invocation (no `&&`).

Note on the prior verification failure: the gate previously ran `python scripts/m002_s03_apply_category_targets.py` (wrong path — the helper is `backend/scripts/m002_s03_apply_category_targets.py`) and `python -m app.crawlers.compliance_audit` from the repo root (the module requires `cwd=backend/`). Those were transient verify-line artifacts, not source bugs — the audit script itself ran cleanly from `backend/` and reported `108/108 compliant`. T03 is the test-writing task; the verify line in the slice plan is `pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto --rootdir=backend`, which now passes.

## Verification

Ran the task's specified verify command from the repo root:

`pytest backend/tests/crawlers/test_adapter_category_targets.py backend/tests/crawlers/test_compliance_audit.py -n auto -v --rootdir=backend` → 221 passed in 8.56s (108 declarations + 108 resolutions + 1 specialist spot-check + 1 total-count + 3 audit-stdout = 221).

Also re-ran the slice-level CI gate `pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto --rootdir=backend` → 218 passed in 8.52s.

Manual sanity check: `python -m app.crawlers.compliance_audit` from `backend/` exits 0 and prints `Total: 108/108 compliant` with the `T0 (http): 83/83`, `T1 (tls): 15/15`, `T2 (browser): 10/10` per-tier breakdown.

Pure-import assertions only — no fixtures from `.gsd/` or other gitignored paths. Both modules import only from `app.crawlers.*`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest backend/tests/crawlers/test_adapter_category_targets.py backend/tests/crawlers/test_compliance_audit.py -n auto -v --rootdir=backend` | 0 | ✅ pass | 8560ms |
| 2 | `pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto --rootdir=backend` | 0 | ✅ pass | 8520ms |
| 3 | `python -m app.crawlers.compliance_audit (from backend/)` | 0 | ✅ pass | 600ms |

## Deviations

None — followed the inlined task plan verbatim. The four-test split in test_adapter_category_targets.py and three-test split in test_compliance_audit.py match exactly. Only adaptation: asserted the per-tier-count line uses `len(ADAPTER_REGISTRY)` rather than the hardcoded `108` count from the slice plan goal sentence, so future adapter additions don't churn this test.

## Known Issues

None. The slice goal-line mentions `111/111 compliant` and a per-tier breakdown of `T0: 84/84, T1: 16/16, T2: 11/11`, but the actual ADAPTER_REGISTRY at HEAD is 108 (T0:83 / T1:15 / T2:10) — matches T01's verified output and the spec assertions in test_adapter_discovery.py. The `111` looks like an early-S03 estimate that wasn't updated when the registry settled at 108. Tests assert dynamically against `len(ADAPTER_REGISTRY)` so this doesn't matter for correctness.

## Files Created/Modified

- `backend/tests/crawlers/test_adapter_category_targets.py`
- `backend/tests/crawlers/test_compliance_audit.py`
