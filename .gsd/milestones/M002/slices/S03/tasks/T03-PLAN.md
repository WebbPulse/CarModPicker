---
estimated_steps: 16
estimated_files: 2
skills_used: []
---

# T03: Add `tests/crawlers/test_adapter_category_targets.py` parametrized over `ADAPTER_REGISTRY` + `tests/crawlers/test_compliance_audit.py` (PR-time gate)

Pin the contract so any future adapter PR that forgets `category_targets` fails CI by adapter slug. Two test modules:

**1. `backend/tests/crawlers/test_adapter_category_targets.py`** — parametrized over the live registry, runs in milliseconds:

- `test_every_adapter_declares_category_targets(adapter_name, adapter_cls)` — `pytest.mark.parametrize` over `sorted(ADAPTER_REGISTRY.items())` with `ids=lambda nc: nc[0]`. Asserts `getattr(adapter_cls, 'category_targets', [])` is a non-empty list/tuple of strings. The pytest id surfaces the offending adapter slug directly in the failure line.
- `test_every_category_target_resolves_via_registry(adapter_name, adapter_cls)` — same parametrize. For each entry in `category_targets`, asserts `default_registry.resolve(entry) is not None`. Belt-and-suspenders for `__init_subclass__` (which runs at import time but doesn't run again on test-fixture-defined subclasses); makes the contract explicit in pytest output.
- `test_specialist_adapters_declare_concrete_slugs()` — explicit spot-checks (per S03 demo): asserts `'brake'` is in `ADAPTER_REGISTRY['girodisc'].category_targets`, `ADAPTER_REGISTRY['essexparts'].category_targets`, `ADAPTER_REGISTRY['wilwood'].category_targets`; `'coilover'` in `ADAPTER_REGISTRY['bcracing'].category_targets`, `kwsuspensions`, `fortuneauto`, `tein`, `stanceusa`; `'turbo'` in `atpturbo`, `fullrace`.
- `test_total_compliance_count_matches_registry()` — asserts `len(ADAPTER_REGISTRY) == sum(1 for c in ADAPTER_REGISTRY.values() if c.category_targets)`. Catches the case where a future PR removes the declaration from one adapter.

**2. `backend/tests/crawlers/test_compliance_audit.py`** — pins the script-as-test:

- `test_audit_passes_when_all_compliant(capsys)` — calls `audit()` directly (not subprocess), asserts return code 0 and stdout contains `108/108 compliant`. Uses captured stdout.
- `test_audit_per_tier_breakdown_in_stdout(capsys)` — calls `audit()`, asserts each of `T0 (http):`, `T1 (tls):`, `T2 (browser):` appears once in stdout.
- `test_audit_reports_offenders_when_non_compliant(monkeypatch, capsys)` — patches `app.crawlers.compliance_audit.ADAPTER_REGISTRY` to a small fixture dict with one good and one stub-bad adapter, asserts return code 1 and stdout contains `Non-compliant adapters:` plus the bad adapter's slug. Use `unittest.mock.patch.object` or monkeypatch on the module's bound name (per MEM017 pattern: patch the import site, not the source).

**Pitfalls / pattern conformance:**
- Per MEM025: do not declare ad-hoc `RetailerCrawlerAdapter` subclasses inside test files for the offender-fixture — they get registered via `__init_subclass__` and must declare a non-empty `ADAPTER_NAME`. Use a plain Mock or a `types.SimpleNamespace` with `category_targets=[]` and `FETCHER_TIER='http'` for the bad-adapter fixture instead.
- Per MEM017: when patching the offender registry, patch `app.crawlers.compliance_audit.ADAPTER_REGISTRY` (the import site inside the audit module), not `app.crawlers.adapters.ADAPTER_REGISTRY` (the source) — Python resolves bound names at the call site.
- Per MEM019: keep the slice's verify command as a single pytest invocation; don't chain with `&&` (the gate splits there).
- Test files must only read from paths tracked in git — both files import from `app.crawlers.*`, no fixtures from `.gsd/`.

**No fixture refresh needed:** characterization tests under `tests/crawlers/test_characterization_*.py` exercise `parse_product_page()` directly against archived HTML and don't read `category_targets`, so adding the ClassVar to all 108 adapters in T02 doesn't drift any snapshot.

## Inputs

- ``backend/app/crawlers/compliance_audit.py` — `audit()` + `_classify_tier()` (T01) — imported and called directly`
- ``backend/app/crawlers/adapters/__init__.py` — `ADAPTER_REGISTRY` (parametrize source)`
- ``backend/app/crawlers/specs/__init__.py` — `default_registry` (resolution check)`
- ``backend/app/crawlers/adapters/base.py` — `RetailerCrawlerAdapter.category_targets` declaration (contract under test)`

## Expected Output

- ``backend/tests/crawlers/test_adapter_category_targets.py` — 4 tests: 2 parametrized over registry (108 cases each), 1 specialist-spot-check, 1 total-count cross-check; runs in <2s`
- ``backend/tests/crawlers/test_compliance_audit.py` — 3 tests pinning audit script's stdout contract and offender-reporting branch`

## Verification

pytest backend/tests/crawlers/test_adapter_category_targets.py backend/tests/crawlers/test_compliance_audit.py -n auto -v --rootdir=backend
