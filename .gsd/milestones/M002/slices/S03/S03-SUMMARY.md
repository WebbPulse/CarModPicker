---
id: S03
parent: M002
milestone: M002
provides:
  - ["backend/app/crawlers/compliance_audit.py — script-as-test consumed by S04 admin extraction-health endpoint", "backend/scripts/m002_s03_apply_category_targets.py — committed source-of-truth for specialist mapping (future adapter additions)", "backend/tests/crawlers/test_adapter_category_targets.py + test_compliance_audit.py — PR-time CI gate enforcing the contract", "All 108 adapters in ADAPTER_REGISTRY now declare a non-empty category_targets ClassVar (4 brake / 5 coilover / 2 turbo specialists + 97 universal catch-alls)", "Stable stdout contract for S04 to grep: 'M002/S03 adapter compliance audit' header + per-tier rows + Total + OK/Non-compliant trailer"]
requires:
  - slice: S01
    provides: RetailerCrawlerAdapter.category_targets ClassVar + __init_subclass__ slug-resolution validation, default_registry singleton
  - slice: S02
    provides: Universal-field extraction post-hook in base class — adapters inherit without changes
affects:
  - ["backend/app/crawlers/adapters/ — 108 adapter files now declare category_targets", "backend/tests/crawlers/ — two new test modules (218 + 3 = 221 tests added)", "S04 — gains canonical compliance signal (108/108) for admin extraction-health endpoint", "S13 — gains audit script as final integration verification surface"]
key_files:
  - ["backend/app/crawlers/compliance_audit.py", "backend/scripts/m002_s03_apply_category_targets.py", "backend/tests/crawlers/test_adapter_category_targets.py", "backend/tests/crawlers/test_compliance_audit.py", "backend/app/crawlers/adapters/tier0_http/", "backend/app/crawlers/adapters/tier1_tls/", "backend/app/crawlers/adapters/tier2_browser/"]
key_decisions:
  - ["TDD-shape the audit script first (T01) so T02's retrofit has an objective stopping condition: 0/108 pre-T02, 108/108 post-T02.", "Module-scope audit() + _classify_tier() helpers (not nested) so T03 tests import and call them via capsys instead of subprocess — keeps tests parallel-safe and ~10x faster.", "Skip re-validating each declared slug against default_registry inside the audit — RetailerCrawlerAdapter.__init_subclass__ already enforces it at import; duplicating the check would muddy responsibilities.", "Own the SPECIALIST_MAPPING in a single committed helper script rather than 108 hand-edited adapter files — keeps the brake/coilover/turbo assignments reviewable in one place, idempotent (regex pre-scan) and re-runnable as evidence.", "Use ['universal'] as the floor for all 97 non-specialist adapters because the S02 category-name → sub-slug bridge already routes any non-coilover/brake/turbo categorized payload to UniversalSpec.", "Insert category_targets immediately under ADAPTER_NAME (not at class-body bottom) so all class-level metadata clusters together — preserves existing convention.", "Use pytest.mark.parametrize ids=lambda nc: nc[0] so a CI failure reads [<adapter_slug>] FAILED verbatim — turns 'which adapter forgot' into a one-glance read.", "Mock the bad-adapter fixture with types.SimpleNamespace, not a RetailerCrawlerAdapter subclass — avoids __init_subclass__'s ADAPTER_NAME enforcement and global registry pollution (per MEM025).", "Patch compliance_audit.ADAPTER_REGISTRY at the import site (per MEM017), not app.crawlers.adapters.ADAPTER_REGISTRY at the source.", "Assert dynamic Total: <n>/<n> using len(ADAPTER_REGISTRY) instead of hardcoding 108 — keeps T03 stable when adapters are added/removed.", "Surface the roadmap drift (108 not 111 adapters) in T02-SUMMARY's Deviations and as MEM037 — downstream slices (S04 admin extraction-health, S13) treat 108 as canonical."]
patterns_established:
  - ["Script-as-test gate pattern: module-scope audit() returning exit code, importable helpers, __main__ calling sys.exit() — testable via capsys without subprocess overhead.", "Bulk-edit retrofit pattern: own the mapping in a committed one-shot helper script with regex-based idempotent edits; run once, commit script + edits together; helper stays in repo as evidence.", "Parametrized PR-time gate pattern: pytest.mark.parametrize over the live registry with ids=lambda over the slug — failures surface the offender by name in pytest output.", "ClassVar metadata clustering convention: new declarative class-level attributes go directly under ADAPTER_NAME, alongside FETCHER_TIER/HEALTH_PROBE_URL/IS_FALLBACK."]
observability_surfaces:
  - ["python -m app.crawlers.compliance_audit — CLI gate, prints structured stdout (`108/108 compliant` + per-tier breakdown), exits non-zero on miss with `<adapter_slug> [<tier>] declares no category_targets` per offender", "pytest backend/tests/crawlers/test_adapter_category_targets.py -n auto — PR-time CI gate; failures surface adapter slug as test id"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T05:14:05.471Z
blocker_discovered: false
---

# S03: 108-adapter category_targets compliance retrofit + audit + PR-time gate

**All 108 adapters in ADAPTER_REGISTRY now declare category_targets; compliance_audit script + parametrized pytest gate pin 108/108 compliance at PR time as a binary signal for S04 admin extraction-health.**

## What Happened

S03 closes the M002 schema-contract substrate by retrofitting `category_targets: ClassVar[list[str]]` onto every concrete adapter under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/` and shipping a CI gate that fails any future PR which forgets the declaration.

**T01** wrote `backend/app/crawlers/compliance_audit.py` first, TDD-style. The module exposes module-scope `audit() -> int` and `_classify_tier(cls) -> str` helpers (importable for unit tests, no subprocess overhead) plus a `__main__` block that calls `sys.exit(audit())`. The audit imports `ADAPTER_REGISTRY` from `app.crawlers.adapters` (its discovery walk runs at import time), buckets each registered class by `cls.FETCHER_TIER` (`http`→T0, `tls`→T1, `browser`→T2), and checks each adapter's `category_targets` ClassVar is a non-empty list/tuple of strings. Stdout follows a stable contract S04 will grep against (`M002/S03 adapter compliance audit` header + three hardcoded-width per-tier rows + `Total:` row + `OK` trailer when compliant; `Non-compliant adapters:` block listing offenders by slug+tier when not). Pre-T02 baseline run reported 0/108 — exactly as the slice plan predicted.

**T02** retrofitted all 108 adapters via a tracked one-shot helper at `backend/scripts/m002_s03_apply_category_targets.py`. The helper owns the `SPECIALIST_MAPPING` dict in one reviewable place, walks each tier directory (skipping `__init__.py`/`base.py`/`generic.py`), regex-matches the `ADAPTER_NAME: ClassVar[str] = "<slug>"` line in each adapter, and inserts `category_targets: ClassVar[list[str]] = [...]` at matching indentation directly underneath. Specialists got concrete sub-slug + `"universal"` (4 brake: girodisc/essexparts/wilwood/stoptech; 5 coilover: bcracing/tein/stanceusa/kwsuspensions/fortuneauto; 2 turbo: atpturbo/fullrace); the remaining 97 mixed-catalog adapters got `["universal"]` as the safe floor (the S02 category-name → sub-slug bridge already routes any non-coilover/brake/turbo categorized payload to UniversalSpec). The helper is idempotent via a `^[ \t]*category_targets\s*[:=]` pre-scan — re-running it reports `0 updated, 108 already-present`. Five representative diffs were spot-checked across tier0/tier1/tier2 and specialist/catch-all; all insertions landed inside the class body at correct indentation. After the retrofit, `__init_subclass__`'s slug-resolution check passed for all 108 adapters at import time, and `python -m app.crawlers.compliance_audit` reported `T0: 83/83, T1: 15/15, T2: 10/10, Total: 108/108 compliant`.

**T03** wrote two test modules pinning the contract at PR time. `backend/tests/crawlers/test_adapter_category_targets.py` parametrizes over `sorted(ADAPTER_REGISTRY.items())` with `ids=lambda nc: nc[0]` so violations surface as `[<adapter_slug>] FAILED` directly — turns the "which adapter forgot category_targets" question into a one-glance read of CI output. Four tests: every adapter declares non-empty category_targets; every entry resolves via `default_registry`; specialist spot-checks for the brake/coilover/turbo mappings; total-count matches `len(ADAPTER_REGISTRY)`. `backend/tests/crawlers/test_compliance_audit.py` pins the script-as-test stdout contract via three tests calling `audit()` directly with capsys: passes-when-all-compliant (return code 0, dynamic `Total: <n>/<n> compliant` line), per-tier-breakdown-in-stdout, and reports-offenders-when-non-compliant (monkeypatches `compliance_audit.ADAPTER_REGISTRY` at the import site per MEM017, with a `types.SimpleNamespace` bad-adapter fixture per MEM025 to avoid `__init_subclass__` registry pollution). 221 tests pass.

**Roadmap drift surfaced:** roadmap text says "111 adapters" but `ADAPTER_REGISTRY` actually contains 108 (T0:83 / T1:15 / T2:10). The 3-adapter delta is the IS_FALLBACK GenericHtmlParser instances per tier, which `__init_subclass__` excludes from the registry per D-03. Audit reports 108/108 against the live registry — that count is canonical for S04, S13, and milestone close. Captured as MEM037 for downstream slices.

This slice is purely a declaration of intent — no runtime ingest behavior changes. S04 (admin extraction-health) and S13 (final integration) consume the binary compliance signal directly; the script-as-test is the demo gate.

## Verification

All slice-level verification checks defined in S03-PLAN.md passed:

1. **Compliance audit (slice demo gate):** `cd backend && python -m app.crawlers.compliance_audit` exits 0, prints `T0 (http): 83/83 compliant`, `T1 (tls): 15/15 compliant`, `T2 (browser): 10/10 compliant`, `Total: 108/108 compliant`, and the `OK — every adapter declares at least one category_targets entry` trailer.

2. **Specialist spot-check:** Confirmed via T03 tests + manual ADAPTER_REGISTRY enumeration: brake (girodisc/essexparts/wilwood/stoptech), coilover (bcracing/kwsuspensions/fortuneauto/tein/stanceusa), and turbo (atpturbo/fullrace) all declare their concrete sub-slug + 'universal'.

3. **Parametrized pytest gate:** `pytest backend/tests/crawlers/test_adapter_category_targets.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend` → 221 passed in 8.59s.

4. **Full crawler test suite green:** `pytest backend/tests/crawlers/ -n auto --rootdir=backend` → 1585 passed, 1 skipped in 11.90s. No regressions from the 108-file retrofit.

5. **Registry sanity check:** `python -c 'from app.crawlers.adapters import ADAPTER_REGISTRY; assert len(ADAPTER_REGISTRY) == 108; assert all(getattr(c, "category_targets", []) for c in ADAPTER_REGISTRY.values())'` → exit 0. Every adapter declares non-empty category_targets; base class `__init_subclass__` validated each declared slug against `default_registry` at import time.

6. **Idempotency:** Re-running the helper script reports `0 updated, 108 already-present` — safe to re-run on partial-failure recovery.

7. **Distribution:** 97 × ['universal'], 5 × ['coilover','universal'], 4 × ['brake','universal'], 2 × ['turbo','universal'] — totals 108 and matches the planner's specialist sets.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"None from the slice plan. Minor adaptation in T03: the per-tier-count test asserts the dynamic Total: <n>/<n> line using len(ADAPTER_REGISTRY) instead of hardcoded 108 — keeps the test stable when adapters are added/removed without churning T03. The slice plan's demo line citing T0:84 / T1:16 / T2:11 (total 111) was treated as drift against the live registry (108); audit and tests assert against the live count, and PROJECT.md was updated to reflect 108."

## Known Limitations

"Roadmap text and slice plan demo line still say '111 adapters' (T0:84 / T1:16 / T2:11). Live ADAPTER_REGISTRY has 108 (T0:83 / T1:15 / T2:10) — the 3-adapter delta is the IS_FALLBACK GenericHtmlParser instances per tier, which __init_subclass__ excludes from the registry per D-03. Audit reports 108/108; tests assert dynamically against len(ADAPTER_REGISTRY). Captured as MEM037 for S04/S13 — they should treat 108 as canonical, not 111."

## Follow-ups

"None required for slice closure. The roadmap text drift (111 → 108) is annotated in PROJECT.md and captured in memory; S04 + S13 consume the live audit count, not the roadmap prose. If a future adapter PR adds a non-fallback adapter, the parametrized pytest gate will pin it automatically; the helper script's SPECIALIST_MAPPING is the canonical place to declare it as a specialist."

## Files Created/Modified

- `backend/app/crawlers/compliance_audit.py` — New: script-as-test with audit()/_classify_tier() helpers, per-tier stdout contract, exit-1-with-offenders behavior
- `backend/scripts/m002_s03_apply_category_targets.py` — New: committed one-shot helper owning SPECIALIST_MAPPING; regex-based idempotent insertion of category_targets ClassVar under ADAPTER_NAME
- `backend/tests/crawlers/test_adapter_category_targets.py` — New: 218 parametrized tests pinning every-adapter-declares + every-target-resolves + specialist spot-check + total-count contracts
- `backend/tests/crawlers/test_compliance_audit.py` — New: 3 capsys-based tests pinning compliance_audit stdout contract (passes/per-tier/offenders)
- `backend/app/crawlers/adapters/tier0_http/*.py` — Retrofit: 83 tier0 adapters now declare category_targets (4 brake + 3 coilover + 2 turbo specialists + 74 universal catch-alls)
- `backend/app/crawlers/adapters/tier1_tls/*.py` — Retrofit: 15 tier1 adapters now declare category_targets (2 coilover specialists + 13 universal catch-alls)
- `backend/app/crawlers/adapters/tier2_browser/*.py` — Retrofit: 10 tier2 adapters now declare category_targets (all 10 universal catch-alls)
- `.gsd/PROJECT.md` — Updated milestone sequence: marked S02 + S03 complete; corrected adapter count from 111 to 108
