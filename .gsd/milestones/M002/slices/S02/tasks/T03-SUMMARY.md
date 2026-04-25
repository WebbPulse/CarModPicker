---
id: T03
parent: S02
milestone: M002
key_files:
  - backend/app/crawlers/specs/category_bridge.py
  - backend/app/crawlers/adapters/base.py
  - backend/app/crawlers/base.py
  - backend/tests/crawlers/test_category_slug_bridge.py
  - backend/tests/crawlers/test_ingest_spec_validation.py
key_decisions:
  - Parent-aware keyword gating in the bridge — keyword AND matching parent category both required for sub-slug resolution, otherwise fall through to universal. Prevents stray 'coilover' prose on a wheels-categorized part from validating against CoiloverSpec.
  - UNIVERSAL_FIELD_NAMES lives as a module-level frozenset on adapters/base.py rather than imported from parsing.py — keeps __init_subclass__ free of a parsing-import-at-class-creation-time concern and lets the validation read off a tight, explicit canonical set.
  - apply_universal_extraction returns the SAME payload instance (mutated in place) rather than a copy — call sites can use the canonical `payload = adapter.apply_universal_extraction(html, payload)` shape with no surprises around dataclass equality or downstream code holding the original reference.
  - Replaced the obsolete 'unregistered slug pass-through' test with a wheels-validates-against-universal test instead of deleting it — same shape (wheels category, free-form specs) now drops to None + emits metric, which is the actual contract change. Keeps the regression coverage but moves the assertion to the new behavior.
duration: 
verification_result: passed
completed_at: 2026-04-25T04:35:47.787Z
blocker_discovered: false
---

# T03: Add category-name → sub-slug bridge + base-class apply_universal_extraction hook + suppress_universal ClassVar + ingest update

**Add category-name → sub-slug bridge + base-class apply_universal_extraction hook + suppress_universal ClassVar + ingest update**

## What Happened

Built the four connected pieces that wire the universal extractor into the ingest path so the S01 validation hook actually fires in production.

(a) `app/crawlers/specs/category_bridge.py` (new). `category_to_subslug(category_name, *, name=None, description=None)` maps DB category names to SpecRegistry sub-slugs using parent-aware keyword scoring: 'suspension' + coilover keyword → 'coilover'; 'engine' + turbo keyword → 'turbo'; 'brakes' → 'brake' (single sub-slug, no keyword check); every other non-None DB category falls through to the 'universal' catch-all (registered to UniversalSpec by T02). When category_name is None, returns None so ingest preserves S01 pass-through. Parent-category gating prevents stray 'coilover'/'turbo' prose from hijacking the schema on a wheels/exhaust part — both keyword AND matching parent are required for keyword-gated sub-slugs. Mirrors the keyword-scoring shape of `app/core/category_inference.py`.

(b) `RetailerCrawlerAdapter.apply_universal_extraction(html, payload)` in `app/crawlers/adapters/base.py`. Lazy-imports `extract_universal_fields` from parsing.py (the dependency direction stays one-way — parsing.py imports ScrapedPayload from crawlers.base, so this hook imports parsing only at call time). Filters out adapter-suppressed fields, builds a flat `{<field>: value, <field>_confidence: conf}` shape, and merges into `payload.specifications` with adapter-wins semantics (only fills keys the adapter didn't already set). Emits a DEBUG log per merged field so future agents can grep an archive rerun for which extractor populated what. None payloads short-circuit; empty extractions return the payload unchanged. Returns the same payload instance so call sites can write `payload = adapter.apply_universal_extraction(html, payload)` reflexively.

(c) `suppress_universal: ClassVar[list[str]] = []` on `RetailerCrawlerAdapter`. `__init_subclass__` validates entries against the new module-level `UNIVERSAL_FIELD_NAMES` frozenset at class-definition time, raising TypeError with the offending adapter qualname on typos. Default empty so every adapter gets all five universal fields auto-extracted unless it opts out.

(d) `ingest_payload` in `app/crawlers/base.py`. Replaced the bare `default_registry.resolve(inferred_name)` with a two-step: lazy-import `category_to_subslug`, call it with `inferred_name`, payload.name, payload.description; then `default_registry.resolve(bridged_subslug)`. The WARN log now includes both the inferred DB category and the bridged sub-slug (`category=suspension subslug=coilover`) so S04's admin endpoint can show per-sub-category failure rates. Pass-through still triggers when payload.specifications is None, when inferred_name is None, or when the bridge returns None — all preserving the S01 fail-soft contract.

Tests: created `backend/tests/crawlers/test_category_slug_bridge.py` with branch-by-branch coverage of every mapping branch (None, empty, suspension+coilover variants, suspension without coilover → universal, brakes always → brake, engine+turbo, engine without turbo → universal, every non-mapped DB category → universal, parent-mismatched keyword → universal) plus a parametrized round-trip test that confirms every non-None bridge result resolves to a CategorySpec subclass in default_registry. Updated `test_ingest_spec_validation.py`: extended the WARN-log assertion to require the bridged subslug; replaced the now-obsolete "unregistered slug pass-through" test with a wheels-validates-against-universal test (same payload now drops to None + emits metric — that's the contract change that makes the hook fire across the catalog); added a positive UniversalSpec acceptance test (a payload composed only of universal fields validates and persists); added a new `TestIngestUsesBridgeToResolveSubslug` class with two tests proving the bridge fires in production (coilover-keyword payload validates against CoiloverSpec; coilover-spec field on a wheels payload drops to None via UniversalSpec).

Captured three memories for future agents: MEM022 (the bridge architecture), MEM023 (apply_universal_extraction adapter-wins merge pattern), MEM024 (the contract-change gotcha — pass-through only happens when category_name is None now).

## Verification

Ran the slice-prescribed verify command and the broader crawler suite. All bridge branches, ingest-validation paths, adapter-discovery guards, and 1300+ existing crawler tests pass without drift.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py backend/tests/crawlers/test_adapter_discovery.py -n auto --rootdir=backend` | 0 | ✅ pass | 9420ms |
| 2 | `pytest backend/tests/crawlers/ -n auto --rootdir=backend -q (broad regression check)` | 0 | ✅ pass — 1303 passed, 1 skipped | 11180ms |

## Deviations

"Created test_category_slug_bridge.py and updated test_ingest_spec_validation.py during T03 even though the slice plan attributes both to T05. The T03 verify command requires both files to exist and pass, and the bridge change inherently breaks the old 'unregistered slug pass-through' assertion — staging the test changes outside T03 would have left the verify gate red. T05 will extend test_category_slug_bridge.py with deeper coverage and add the remaining test files (test_universal_extractor.py, test_universal_extraction_hook.py, demo CLI subprocess test)."

## Known Issues

"None — the four pieces are complete and test-locked. T04 still has to wire `apply_universal_extraction` into the runner.py / archive_rescrape.py / api/endpoints/crawled_pages.py call sites; until then the hook is reachable but not invoked from production paths."

## Files Created/Modified

- `backend/app/crawlers/specs/category_bridge.py`
- `backend/app/crawlers/adapters/base.py`
- `backend/app/crawlers/base.py`
- `backend/tests/crawlers/test_category_slug_bridge.py`
- `backend/tests/crawlers/test_ingest_spec_validation.py`
