# S03: 111-adapter compliance retrofit

**Goal:** Retrofit every concrete adapter under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/` (108 in `ADAPTER_REGISTRY`) to declare at least one entry in the `category_targets: ClassVar[list[str]]` ClassVar that S01 introduced, and ship a `python -m app.crawlers.compliance_audit` script + parametrized pytest gate so non-compliance fails loudly at PR time. Specialist adapters declare their concrete sub-slug (`brake` / `coilover` / `turbo`) plus `universal`; mixed-catalog adapters declare just `["universal"]`. The retrofit is purely a declaration of intent — runtime spec resolution still flows through the S02 category-name → sub-slug bridge — so this slice does not change ingest behavior, only completes the M002 schema-contract substrate so S04 can audit compliance as a binary signal.
**Demo:** Run python -m app.crawlers.compliance_audit. Output prints 111/111 compliant with per-tier breakdown (T0: 84/84, T1: 16/16, T2: 11/11). Each adapter declares at least one category_target. Spot-check 3 T0, 2 T1, 1 T2 adapter — verify category_targets attribute present and base-class universal extraction inherited.

## Must-Haves

- All 108 adapters in `ADAPTER_REGISTRY` declare a non-empty `category_targets`.
- Every declared `category_targets` entry resolves via `app.crawlers.specs.default_registry.resolve(slug)`.
- `python -m app.crawlers.compliance_audit` exits 0, prints `108/108 compliant` and a per-tier breakdown (T0: 83/83, T1: 15/15, T2: 10/10).
- A parametrized pytest in `backend/tests/crawlers/test_adapter_category_targets.py` ranges over `ADAPTER_REGISTRY` and asserts the same contract.
- Brake specialists (`girodisc`, `essexparts`, `wilwood`, `stoptech`) include `"brake"`.
- Coilover specialists (`bcracing`, `kwsuspensions`, `fortuneauto`, `tein`, `stanceusa`) include `"coilover"`.
- Turbo specialists (`atpturbo`, `fullrace`) include `"turbo"`.
- The full crawler test suite stays green: `pytest backend/tests/crawlers/ -n auto --rootdir=backend`.
- **Roadmap drift note:** the roadmap text still says "111 adapters" but `ADAPTER_REGISTRY` actually contains 108 today (83 tier0 + 15 tier1 + 10 tier2 by `FETCHER_TIER`). The audit script counts the live registry — its output is the source of truth for compliance. The roadmap will be corrected during S03 closer.

## Proof Level

- This slice proves: - This slice proves: contract (declarative retrofit + audit gate; no runtime behavior changes).
- Real runtime required: no — audit + tests run against the in-process registry, no live fetches.
- Human/UAT required: no — the audit script is the demo.

## Integration Closure

- Upstream surfaces consumed: `RetailerCrawlerAdapter.category_targets` ClassVar + `__init_subclass__` validation gate (S01/T02), `app.crawlers.specs.default_registry` (S01/T01), `ADAPTER_REGISTRY` discovery walk (`backend/app/crawlers/adapters/__init__.py`).
- New wiring introduced in this slice: `app/crawlers/compliance_audit.py` (script-as-test, runnable via `python -m`), `tests/crawlers/test_adapter_category_targets.py` (CI gate). No runtime call-site wiring — `category_targets` is declarative metadata; ingest behavior continues to flow through the S02 bridge.
- What remains before the milestone is truly usable end-to-end: S04 consumes this slice's output (audit data + per-tier breakdown) for the admin extraction-health endpoint and re-extraction backfill; price-history surfaces (S05–S07) and the design-system reset (S08–S12) are independent.

## Verification

- Runtime signals: none added at production runtime (declarative metadata only); compliance audit prints structured stdout (`108/108 compliant` + per-tier breakdown) and exits non-zero on miss with `<adapter_slug> [<tier>] declares no category_targets` per offending adapter.
- Inspection surfaces: `python -m app.crawlers.compliance_audit` (CLI), `pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto --rootdir=backend` (CI gate).
- Failure visibility: any future adapter PR that forgets `category_targets` fails the parametrized test by adapter slug, and the audit script exits non-zero so the M002 closer / S04 admin endpoint can surface the gap.
- Redaction constraints: none (slugs only, no PII).

## Tasks

- [x] **T01: Add `app/crawlers/compliance_audit.py` script-as-test that prints `<n>/<n> compliant` + per-tier breakdown and exits non-zero on miss** `est:45m`
  Write the audit script first (TDD-style) so the slice has an objective stopping condition: before T02 it fails with 108 non-compliant adapters, after T02 it passes 108/108. The script is the slice's primary demo gate — `python -m app.crawlers.compliance_audit` from `backend/` must be a one-liner anyone can run.

**Module shape:** put `audit() -> int` (returns exit code) and a small `_classify_tier(cls) -> str` helper at module scope so tests in T03 can import them directly without subprocess overhead. The `__main__` block calls `sys.exit(audit())`. `audit()` reads `ADAPTER_REGISTRY` from `app.crawlers.adapters` (importing it triggers the discovery walk), buckets each registered class by `cls.FETCHER_TIER` (`http` → T0, `tls` → T1, `browser` → T2), and for each adapter checks that `cls.category_targets` is a non-empty list/tuple of strings.

**Stdout contract** (consumed by S04 — keep it stable):
```
M002/S03 adapter compliance audit
  T0 (http):    <n0>/<total0> compliant
  T1 (tls):     <n1>/<total1> compliant
  T2 (browser): <n2>/<total2> compliant
  Total:        <n>/<total> compliant
```
When all compliant, append `OK — every adapter declares at least one category_targets entry` and exit 0. When non-compliant, prepend a `Non-compliant adapters:` block listing each offender as `  - <adapter_slug> [<tier>]: declares no category_targets` and exit 1.

**Implementation notes:**
- Do NOT re-validate that each declared slug resolves via `default_registry` — `RetailerCrawlerAdapter.__init_subclass__` already does that at import time; if a bad slug shipped, `ADAPTER_REGISTRY` would be empty/the import would have raised. The audit's job is the binary compliance count.
- Use `getattr(cls, 'category_targets', [])` defensively, then check `isinstance(value, (list, tuple))` and `len(value) >= 1` — exactly the same check `__init_subclass__` will accept.
- Print to stdout (not stderr) so the gate command can pipe-capture cleanly.
- Hardcode the column widths (e.g. `T0 (http):    `) for stable grep-ability.

**Why TDD-shape this task first:** the script becomes the verify command for T02 — running it after the retrofit must print `108/108 compliant`. Writing T02 first would leave us without an objective signal for whether the retrofit is complete.
  - Files: `backend/app/crawlers/compliance_audit.py`
  - Verify: cd backend && python -m app.crawlers.compliance_audit; test $? -eq 1 && python -m app.crawlers.compliance_audit | grep -q 'Non-compliant adapters:'

- [x] **T02: Retrofit `category_targets` ClassVar onto all 108 adapter modules (specialists get concrete slug + universal; everyone else gets `["universal"]`)** `est:1h30m`
  Apply the canonical mapping to every adapter file under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/`. The retrofit is mechanical but must be auditable, so do it via a tracked one-shot helper script under `backend/scripts/m002_s03_apply_category_targets.py` that owns the mapping; run the script, then commit the script *and* the resulting adapter edits in this task. The helper stays in the repo as evidence (and so the mapping is reviewable in one place rather than spread across 108 diffs).

**Canonical category_targets mapping** (every entry must already be a registered slug — `coilover`, `brake`, `turbo`, or `universal`; nothing else exists in `default_registry` today):

*Brake specialists* (declare `["brake", "universal"]`):
- `girodisc` (tier0) — two-piece track rotor specialist
- `essexparts` (tier0) — AP Racing distributor (BBKs/pads/rotors/fluid)
- `wilwood` (tier0) — first-party brake manufacturer (calipers/rotors/pads/master cylinders)
- `stoptech` (tier0) — stub adapter, brake sub-brand

*Coilover specialists* (declare `["coilover", "universal"]`):
- `bcracing` (tier0) — first-party coilover manufacturer
- `tein` (tier0) — Japanese coilover/damper house brand
- `stanceusa` (tier0) — Stance Suspension USA, coilover-only catalog
- `kwsuspensions` (tier1) — premium coilover brand
- `fortuneauto` (tier1) — coilover series catalog

*Turbo specialists* (declare `["turbo", "universal"]`):
- `atpturbo` (tier0) — Garrett aftermarket distributor
- `fullrace` (tier0) — turbo manifold + drop-in turbo specialist

*Everyone else* (the remaining 97 adapters): declare `["universal"]`. This includes mixed-catalog resellers (ecstuning/jegs/summitracing/tirerack/americanmuscle), wheel houses (fifteen52/rotiform/titan7/hrewheels/apexwheels/forgeline), tuning houses (cobbtuning/ktuner/hondata/ecutek/openflashperformance/linkecu/aemelectronics/haltech), and platform-specific shops (a90shop/csfrace/iagperformance/etc.). Each gets a `category_targets` declaration so compliance audit passes — `universal` is the safe floor since the S02 bridge already routes any non-coilover/brake/turbo categorized payload there.

**Helper script contract** (`backend/scripts/m002_s03_apply_category_targets.py`):
1. Define `SPECIALIST_MAPPING: dict[str, list[str]]` with the brake/coilover/turbo sets above.
2. Walk `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/*.py` (excluding `__init__.py`, `base.py`, `generic.py`).
3. For each adapter file, read it, locate the `ADAPTER_NAME: ClassVar[str] = "<slug>"` line, and insert `category_targets: ClassVar[list[str]] = [...]` exactly *after* the `ADAPTER_NAME` line at the same indentation. Use the SPECIALIST_MAPPING value if present, otherwise `["universal"]`.
4. Idempotent: skip files that already declare `category_targets =` (regex match on the keyword) so re-running the helper is safe.
5. Print a one-line-per-adapter summary (`tier0_http/wilwood.py: category_targets = ['brake', 'universal']`) and a final count.

**Edit shape inside each adapter file** — the inserted line lives directly under `ADAPTER_NAME` so all class-level ClassVars cluster together (matches the existing convention where `FETCHER_TIER` / `HEALTH_PROBE_URL` / `IS_FALLBACK` sit near the top of the class body):

```python
    ADAPTER_NAME: ClassVar[str] = "wilwood"
    category_targets: ClassVar[list[str]] = ["brake", "universal"]
```

**Constraints / pitfalls:**
- Do NOT change adapter logic, imports, or any existing ClassVars. Only insert one new line per file.
- The `ClassVar[list[str]]` type annotation is required (matches the base class declaration) so pyright stays clean.
- Some adapter files declare ADAPTER_NAME with a comment on the same line — use a regex that anchors on the literal `ADAPTER_NAME: ClassVar[str] =` and inserts on the next physical line, preserving any inline comments.
- After running the helper, manually spot-check 5 representative diffs (one tier0 specialist, one tier0 catch-all, one tier1 specialist, one tier1 catch-all, one tier2 catch-all) to confirm the insertion landed inside the class body, not at module scope.
- Run `pyright` (or at minimum `python -c 'from app.crawlers.adapters import ADAPTER_REGISTRY; print(len(ADAPTER_REGISTRY))'`) afterward — `__init_subclass__` validates each declared slug at import, so a typo would surface as a TypeError during discovery.
  - Files: `backend/scripts/m002_s03_apply_category_targets.py`, `backend/app/crawlers/adapters/tier0_http/*.py`, `backend/app/crawlers/adapters/tier1_tls/*.py`, `backend/app/crawlers/adapters/tier2_browser/*.py`
  - Verify: cd backend && python scripts/m002_s03_apply_category_targets.py && python -m app.crawlers.compliance_audit && python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; assert len(ADAPTER_REGISTRY) == 108, len(ADAPTER_REGISTRY); assert all(getattr(c, 'category_targets', []) for c in ADAPTER_REGISTRY.values())"

- [ ] **T03: Add `tests/crawlers/test_adapter_category_targets.py` parametrized over `ADAPTER_REGISTRY` + `tests/crawlers/test_compliance_audit.py` (PR-time gate)** `est:1h`
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
  - Files: `backend/tests/crawlers/test_adapter_category_targets.py`, `backend/tests/crawlers/test_compliance_audit.py`
  - Verify: pytest backend/tests/crawlers/test_adapter_category_targets.py backend/tests/crawlers/test_compliance_audit.py -n auto -v --rootdir=backend

## Files Likely Touched

- backend/app/crawlers/compliance_audit.py
- backend/scripts/m002_s03_apply_category_targets.py
- backend/app/crawlers/adapters/tier0_http/*.py
- backend/app/crawlers/adapters/tier1_tls/*.py
- backend/app/crawlers/adapters/tier2_browser/*.py
- backend/tests/crawlers/test_adapter_category_targets.py
- backend/tests/crawlers/test_compliance_audit.py
