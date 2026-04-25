---
id: T02
parent: S03
milestone: M002
key_files:
  - backend/scripts/m002_s03_apply_category_targets.py
  - backend/app/crawlers/adapters/tier0_http/wilwood.py
  - backend/app/crawlers/adapters/tier0_http/girodisc.py
  - backend/app/crawlers/adapters/tier0_http/essexparts.py
  - backend/app/crawlers/adapters/tier0_http/stoptech.py
  - backend/app/crawlers/adapters/tier0_http/bcracing.py
  - backend/app/crawlers/adapters/tier0_http/tein.py
  - backend/app/crawlers/adapters/tier0_http/stanceusa.py
  - backend/app/crawlers/adapters/tier1_tls/kwsuspensions.py
  - backend/app/crawlers/adapters/tier1_tls/fortuneauto.py
  - backend/app/crawlers/adapters/tier0_http/atpturbo.py
  - backend/app/crawlers/adapters/tier0_http/fullrace.py
  - backend/app/crawlers/adapters/tier0_http/ (74 other tier0 catch-all files)
  - backend/app/crawlers/adapters/tier1_tls/ (13 other tier1 catch-all files)
  - backend/app/crawlers/adapters/tier2_browser/ (10 tier2 catch-all files)
key_decisions:
  - Owned the SPECIALIST_MAPPING in the committed helper script (not 108 hand-edited adapter files) so the brake/coilover/turbo assignments stay reviewable in one place and re-runnable.
  - Used `['universal']` as the floor for all 97 non-specialist adapters because the S02 category-name → sub-slug bridge routes any non-coilover/brake/turbo categorized payload to UniversalSpec — no need to declare every possible specialty per adapter at this stage.
  - Made the helper idempotent via a `^[ \t]*category_targets\s*[:=]` pre-scan so re-running the script (or running it after a partial failure) is a safe no-op.
  - Skipped re-validating slugs against default_registry inside the helper — base-class __init_subclass__ already does this at adapter import, and the post-script ADAPTER_REGISTRY load is the canonical proof.
  - Inserted `category_targets` immediately under ADAPTER_NAME (not at the bottom of the class body) so all class-level metadata clusters together — matches the existing convention where FETCHER_TIER / HEALTH_PROBE_URL / IS_FALLBACK live near the top of each adapter.
duration: 
verification_result: passed
completed_at: 2026-04-25T05:06:17.826Z
blocker_discovered: false
---

# T02: Retrofit category_targets ClassVar onto all 108 adapter modules via committed one-shot helper script (4 brake / 5 coilover / 2 turbo specialists + 97 ['universal'] catch-alls); compliance audit now reports 108/108.

**Retrofit category_targets ClassVar onto all 108 adapter modules via committed one-shot helper script (4 brake / 5 coilover / 2 turbo specialists + 97 ['universal'] catch-alls); compliance audit now reports 108/108.**

## What Happened

Wrote `backend/scripts/m002_s03_apply_category_targets.py` as the canonical, committed source-of-truth for the specialist mapping (brake: girodisc/essexparts/wilwood/stoptech; coilover: bcracing/tein/stanceusa/kwsuspensions/fortuneauto; turbo: atpturbo/fullrace) and ran it once. The script walks `app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/*.py` (skipping `__init__.py` / `base.py` / `generic.py` — none of the latter two exist in tier dirs today, but the skip set is defensive), regex-matches the `ADAPTER_NAME: ClassVar[str] = "<slug>"` line, and inserts `category_targets: ClassVar[list[str]] = [...]` at the same leading indentation directly underneath. SPECIALIST_MAPPING.get(slug, ["universal"]) supplies the value; the `["universal"]` floor is safe because the S02 category-name → sub-slug bridge already routes any non-coilover/brake/turbo categorized payload there.

Distribution after the retrofit (verified by enumerating ADAPTER_REGISTRY): 97 × ['universal'], 5 × ['coilover','universal'], 4 × ['brake','universal'], 2 × ['turbo','universal'] — totals exactly 108 and matches the planner's specialist sets. Spot-checked five representative diffs (tier0 specialist `wilwood`, tier0 catch-all `jltperformance`, tier1 specialist `kwsuspensions`, tier1 catch-all `turnermotorsport`, tier2 catch-all `jegs`) and confirmed insertion landed inside the class body at correct indentation, immediately under ADAPTER_NAME.

Idempotency proven by re-running the script: second invocation reports `108 already-present, 0 updated` (regex pre-scan on `^[ \t]*category_targets\s*[:=]` early-returns before the insertion path). No adapter logic, imports, or pre-existing ClassVars were touched — exactly one line added per file.

Adapter import succeeds cleanly: `__init_subclass__` validates each declared slug against `default_registry` at class-definition time, so all 108 adapters loaded without TypeError, confirming every inserted slug resolves. No new runtime signals — declarative metadata only, as the Observability Impact section specified. The compliance audit is now the canonical inspection surface for binary compliance and reports `T0: 83/83, T1: 15/15, T2: 10/10, Total: 108/108 compliant` (counts reflect ADAPTER_REGISTRY membership, which excludes the IS_FALLBACK GenericHtmlParser per D-03; the slice plan's 84/16/11 demo numbers appear to include those fallbacks).

Slice-level verification status (per S03-PLAN.md Verification section): `python -m app.crawlers.compliance_audit` passes (108/108, exit 0). The pytest gate `tests/crawlers/test_adapter_category_targets.py` is T03's deliverable and is not yet present — expected, since the slice plan says intermediate tasks may show partial passes.

## Verification

Ran the task plan's exact verify chain from `backend/`: (1) the helper script exits 0 and reports `108 updated, 0 already-present` on first run, then `0 updated, 108 already-present` on re-run (idempotent); (2) `python -m app.crawlers.compliance_audit` exits 0 with `T0 83/83, T1 15/15, T2 10/10, Total 108/108 compliant` and the `OK — every adapter declares at least one category_targets entry` trailer; (3) the inline registry sanity-check from the plan (`assert len(ADAPTER_REGISTRY) == 108 and all(getattr(c, 'category_targets', []) for c in ...)`) passes. Pyright on the helper plus two touched adapter files reports 0 errors / 0 warnings. Distribution matches the plan: 4 brake + 5 coilover + 2 turbo + 97 catch-all = 108.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && python scripts/m002_s03_apply_category_targets.py` | 0 | pass (108 updated on first run; idempotent re-run reports 108 already-present, 0 updated) | 1200ms |
| 2 | `cd backend && python -m app.crawlers.compliance_audit` | 0 | pass (T0 83/83, T1 15/15, T2 10/10, Total 108/108 compliant; OK trailer printed) | 1500ms |
| 3 | `cd backend && python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; assert len(ADAPTER_REGISTRY) == 108; assert all(getattr(c, 'category_targets', []) for c in ADAPTER_REGISTRY.values())"` | 0 | pass (registry size 108; every adapter declares non-empty category_targets — base class __init_subclass__ also validated each slug at import) | 900ms |
| 4 | `cd backend && pyright scripts/m002_s03_apply_category_targets.py app/crawlers/adapters/tier0_http/wilwood.py app/crawlers/adapters/tier1_tls/kwsuspensions.py` | 0 | pass (0 errors, 0 warnings, 0 informations) | 5000ms |

## Deviations

Slice plan's demo line claims `T0: 84/84, T1: 16/16, T2: 11/11` (total 111). Live ADAPTER_REGISTRY has 108 (T0 83 / T1 15 / T2 10) — the difference is the three IS_FALLBACK GenericHtmlParser instances per tier, which `__init_subclass__` excludes from registry per D-03 and which the audit therefore can't see. The 108/108 result satisfies the slice's stated goal (108 in ADAPTER_REGISTRY, T01-SUMMARY pre-T02 baseline of 0/108) and the verify command's `len(ADAPTER_REGISTRY) == 108` assertion. No code change needed for this discrepancy; flagged here for the M002 closer to update the demo prose if desired.

## Known Issues

None.

## Files Created/Modified

- `backend/scripts/m002_s03_apply_category_targets.py`
- `backend/app/crawlers/adapters/tier0_http/wilwood.py`
- `backend/app/crawlers/adapters/tier0_http/girodisc.py`
- `backend/app/crawlers/adapters/tier0_http/essexparts.py`
- `backend/app/crawlers/adapters/tier0_http/stoptech.py`
- `backend/app/crawlers/adapters/tier0_http/bcracing.py`
- `backend/app/crawlers/adapters/tier0_http/tein.py`
- `backend/app/crawlers/adapters/tier0_http/stanceusa.py`
- `backend/app/crawlers/adapters/tier1_tls/kwsuspensions.py`
- `backend/app/crawlers/adapters/tier1_tls/fortuneauto.py`
- `backend/app/crawlers/adapters/tier0_http/atpturbo.py`
- `backend/app/crawlers/adapters/tier0_http/fullrace.py`
- `backend/app/crawlers/adapters/tier0_http/ (74 other tier0 catch-all files)`
- `backend/app/crawlers/adapters/tier1_tls/ (13 other tier1 catch-all files)`
- `backend/app/crawlers/adapters/tier2_browser/ (10 tier2 catch-all files)`
