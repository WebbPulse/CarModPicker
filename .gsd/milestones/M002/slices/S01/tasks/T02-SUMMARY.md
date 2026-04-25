---
id: T02
parent: S01
milestone: M002
key_files:
  - backend/app/crawlers/adapters/base.py
  - backend/app/crawlers/base.py
key_decisions:
  - Lazy-import default_registry inside __init_subclass__ (not at module top) to keep the dependency direction one-way: adapters/ depends on specs/ at runtime, but specs/ never imports adapters/ — preserves the safe-to-import-in-isolation property of spec modules (MEM007).
  - Validate empty-string and non-string entries with their own TypeError ('invalid ... non-empty string') distinct from the unknown-slug TypeError. The plan only mandated the unknown-slug case; the additional check costs one isinstance() and prevents a confusing 'unknown slug ' error if someone types `category_targets = ['']` by accident.
  - Gate the loop with `if targets:` so the import-time cost on the 108 existing adapters (which all keep the default `[]`) is exactly one getattr + one truthiness check — no registry lookup, no import of specs.
  - Register category_targets with type `ClassVar[list[str]]` to match the existing ClassVar pattern on the base, so pyright/IDE see it as a class-level attribute rather than an instance default.
duration: 
verification_result: passed
completed_at: 2026-04-25T03:35:11.242Z
blocker_discovered: false
---

# T02: Add category_targets ClassVar on adapter base with import-time validation against default_registry, plus specifications field on ScrapedPayload

**Add category_targets ClassVar on adapter base with import-time validation against default_registry, plus specifications field on ScrapedPayload**

## What Happened

Extended the two foundation types so adapters can declare which category schemas they target end-to-end:

**`backend/app/crawlers/adapters/base.py`** — Added `category_targets: ClassVar[list[str]] = []` next to the existing ClassVars (ADAPTER_NAME, IS_FALLBACK, HEALTH_PROBE_URL, FETCHER_TIER) and extended `__init_subclass__` with per-entry validation. After the existing ADAPTER_NAME check, the hook lazily imports `default_registry` from `app.crawlers.specs` (one-directional: specs/ does not import adapters/) and iterates `cls.category_targets`. Each entry must be a non-empty string and must resolve via `default_registry.resolve()`. Empty/non-string entries raise `TypeError(... "declares invalid category_targets entry ...; each entry must be a non-empty string.")`. Unknown slugs raise `TypeError(... "declares unknown category_targets entry 'X'; not registered in default_registry")`. Both messages include the adapter qualname so the source is immediate during the S03 retrofit.

**`backend/app/crawlers/base.py`** — Added `specifications: Optional[Dict[str, Any]] = None` to `ScrapedPayload`. `Dict` and `Any` were already in the typing import line; no import changes required. The field's docstring notes the JSON shape matches `Part.specifications` and `PartCreate.specifications`, populated by adapters or universal extraction (S02) when a category schema applies, left None when the category has no registered schema or extraction failed validation.

**Notes / minor deviation from plan:**
- The plan estimate said "all 113 adapters still import"; the actual ADAPTER_REGISTRY count pinned by `test_adapter_count_baseline` is 108 (83 tier0 + 15 tier1 + 10 tier2). This is a planner-side count drift, not a real regression — the test passes, all 108 adapters still import cleanly with the new hook.
- The discovery test asserts on `ADAPTER_REGISTRY` content/count, not on the base class's attribute set, so it required no changes (per the plan's conditional).
- `__init_subclass__` runs on every subclass including still-abstract intermediate bases (e.g., Shopify/WooCommerce mixins). Those return early via the existing `__abstractmethods__` short-circuit *before* the new `category_targets` check, so they won't trip on inherited empty-list defaults — but since the new check is gated by `if targets:`, the empty-default case is also a no-op for them. Either guard alone would be sufficient; both being in place is defense in depth.

**Verification (all three must-haves explicitly checked):**
- `RetailerCrawlerAdapter.category_targets == []` at base — ✅
- Subclass with `category_targets=['coilover']` (registered) — ✅ no raise
- Subclass with `category_targets=['nonsense_slug']` — ✅ raises `TypeError` with adapter qualname + bad slug
- Subclass with `category_targets=['']` — ✅ raises `TypeError` (extra defense beyond plan)
- `ScrapedPayload(..., specifications={'spring_rate_front': 600}).specifications == {'spring_rate_front': 600}` — ✅
- `pytest tests/crawlers/test_adapter_discovery.py -n auto` → 4 passed (no adapter import regresses) — ✅

The rails are now in place for S02 (universal extraction populating `payload.specifications`) and S03 (concrete adapters opting in via `category_targets`).

## Verification

Ran the full verify command from the task plan plus an extended check covering all three must-haves on category_targets validation:

1. `pytest tests/crawlers/test_adapter_discovery.py -n auto` — 4/4 passed in ~8.5s (CRAWL-01 count baseline, CRAWL-03 import errors, CRAWL-02 ADAPTER_NAME presence + uniqueness). Confirms all 108 registered adapters import cleanly with the new __init_subclass__ check; default empty `category_targets` doesn't trigger the validation hook.
2. `python -c "... assert RetailerCrawlerAdapter.category_targets == []; p = ScrapedPayload(..., specifications={'spring_rate_front': 600}); assert p.specifications == {'spring_rate_front': 600}; print('ok')"` — printed `ok` (TESTING=true to suppress S3 head_bucket on import per MEM008).
3. Extended check with three subclasses: GoodAdapter (`['coilover']`) defines without raising; BadAdapter (`['nonsense_slug']`) raises TypeError with both qualname and slug in message; EmptyAdapter (`['']`) raises TypeError with the "invalid ... non-empty string" message. All three branches of the validation hook exercised.

No existing adapter, no test, and no other module needed changing — the addition is purely additive on optional fields with safe defaults.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest tests/crawlers/test_adapter_discovery.py -n auto` | 0 | ✅ pass | 8810ms |
| 2 | `TESTING=true python -c "... assert RetailerCrawlerAdapter.category_targets == []; assert ScrapedPayload(..., specifications={'spring_rate_front': 600}).specifications == {'spring_rate_front': 600}"` | 0 | ✅ pass | 1200ms |
| 3 | `TESTING=true python -c "<good/bad/empty subclass scenarios>"` | 0 | ✅ pass | 1300ms |

## Deviations

Plan said 'all 113 adapters still import' in the verification step description; actual ADAPTER_REGISTRY count is 108 per test_adapter_count_baseline (the canonical CI guard). This is plan-snapshot drift, not a regression — the test still passes.

## Known Issues

None.

## Files Created/Modified

- `backend/app/crawlers/adapters/base.py`
- `backend/app/crawlers/base.py`
