---
id: S02
parent: M002
milestone: M002
provides:
  - ["backend/app/crawlers/parsing.py: extract_weight, extract_material, extract_finish, extract_warranty, extract_fitment_notes, extract_universal_fields aggregator", "backend/app/crawlers/specs/base.py: 5 universal value+confidence field pairs on CategorySpec base (inherited by all concrete specs)", "backend/app/crawlers/specs/universal.py: UniversalSpec(CategorySpec) catch-all registered under 'universal' slug", "backend/app/crawlers/specs/category_bridge.py: category_to_subslug() — DB category name → SpecRegistry sub-slug bridge with 'universal' fallback", "backend/app/crawlers/adapters/base.py: RetailerCrawlerAdapter.apply_universal_extraction(html, payload) post-hook + suppress_universal: ClassVar[list[str]] override + UNIVERSAL_FIELD_NAMES frozenset + __init_subclass__ validation gate", "backend/app/crawlers/base.py: ingest_payload uses category_to_subslug for two-step slug resolution; WARN log includes inferred + bridged subslug", "backend/app/crawlers/runner.py / archive_rescrape.py / api/endpoints/crawled_pages.py: apply_universal_extraction wired between parse_product_page and ingest at all 3 production call sites", "backend/app/crawlers/universal_extractor_demo.py: runnable CLI module that walks the 5 tracked adapter fixtures and prints per-fixture extracted-fields summaries"]
requires:
  - slice: S01
    provides: SpecRegistry, CategorySpec base, ScrapedPayload.specifications, ingest_payload validation hook, RetailerCrawlerAdapter base + category_targets ClassVar, S3-archived HTML test fixture infrastructure
affects:
  - ["S03: must propagate category_targets declarations to all 111 adapters; will use the S02 universal layer as the auto-extraction floor (every adapter inherits all 5 universal fields unless it suppresses)", "S04: admin extraction-health endpoint will distinguish binary compliance (S03) from universal-field coverage gradient (this slice's per-extractor signal); compliance audit will count adapters whose archived HTML produces ≥1 universal field as 'covered'", "S04: backfill job will exercise the universal-extraction path against archived HTML — adapter-wins merge means re-extracting an existing part won't overwrite adapter-specific fields"]
key_files:
  - ["backend/app/crawlers/parsing.py", "backend/app/crawlers/specs/base.py", "backend/app/crawlers/specs/universal.py", "backend/app/crawlers/specs/__init__.py", "backend/app/crawlers/specs/category_bridge.py", "backend/app/crawlers/adapters/base.py", "backend/app/crawlers/base.py", "backend/app/crawlers/universal_extractor_demo.py", "backend/tests/crawlers/test_universal_extractor.py", "backend/tests/crawlers/test_universal_extraction_hook.py", "backend/tests/crawlers/test_category_slug_bridge.py", "backend/tests/crawlers/test_ingest_spec_validation.py"]
key_decisions:
  - ["Universal value+confidence pairs declared on CategorySpec base (not via metaclass/mixin) — keeps schemas trivially readable and JSON-Schema-exportable, concrete subclasses inherit automatically with zero per-spec churn.", "UniversalSpec adds zero fields beyond the inherited universal set — extra='forbid' carries through so unmapped-category extras still raise. Surface area exactly equals the universal extractor's output contract.", "Parent-aware keyword gating in category_bridge — keyword AND matching parent are both required for keyword-gated sub-slugs (coilover, turbo). Prevents stray prose on a wheels-categorized part from validating against CoiloverSpec.", "apply_universal_extraction returns the SAME payload instance (mutated in place) rather than a copy — call sites use the canonical reflexive `payload = adapter.apply_universal_extraction(html, payload)` shape with no surprises around dataclass equality or held references.", "Adapter-wins merge: hook only fills keys the adapter didn't already set. Universal layer is a floor, not a ceiling — adapter-specific extractors trump regex universals.", "UNIVERSAL_FIELD_NAMES lives as a module-level frozenset on adapters/base.py rather than imported from parsing.py — keeps __init_subclass__ free of a parsing-import-at-class-creation-time concern.", "ReDoS guard requires bounded numeric/whitespace runs (\\d{1,8}, \\s{0,4}) IN ADDITION to the 50KB input cap — unbounded greedy quantifiers backtrack catastrophically inside a capped window when no terminator appears. Caught a real ReDoS during smoke testing (CPU pegged for minutes on '1' * 50_000).", "BeautifulSoup .decompose() of shipping-info DOM blocks before the body-text weight fallback — DOM-aware strip is more robust across adapter shapes than a single regex assertion.", "Finish lexicon split into treatments (anodized/polished/...) and colors (black/red/...) with treatments always preferred — a 'red anodized' page does not score a low-confidence color hit when a high-confidence treatment is available.", "Bundled the demo CLI subprocess test inside test_universal_extractor.py (rather than a sixth file) so the slice's verify line stays a single pytest invocation per MEM019 — the gate splits on '&&' and would lose the cd.", "No fixture refresh required: characterization tests target parse_product_page() directly via the adapter registry and bypass apply_universal_extraction entirely — expected.json snapshots remain accurate against unchanged parser output."]
patterns_established:
  - ["Universal-field auto-merge architecture: parsing.py extractors return (value, confidence) tuples → base-class hook builds {field, field_confidence} dict → merges into payload.specifications with adapter-wins semantics → three call sites invoke the hook between parse_product_page and ingest_payload.", "Category-name → sub-slug bridge with 'universal' fallback: makes the S01 validation hook fire across the entire catalog by ensuring every non-None DB category resolves to at least UniversalSpec.", "Per-field suppression via ClassVar[list[str]] validated at __init_subclass__ time against a canonical frozenset — typos fail at class-creation, not at extraction-time.", "Lazy-import inside hook methods to break otherwise-circular module graphs (parsing.py imports ScrapedPayload from base; hook in adapters/base imports parsing only at call time).", "Bounded greedy quantifiers + input cap as the dual ReDoS guard for HTML extractors (MEM029).", "Reflexive call-site shape `payload = adapter.method(html, payload)` for in-place-mutating hooks — keeps grep stable and matches downstream copy-friendly call patterns.", "Sentinel stdout lines for CLI demos when an adapter's parse_product_page returns None — keeps subprocess test contracts (exit 0 + slug present) decoupled from parser-coverage gaps."]
observability_surfaces:
  - ["DEBUG log per merged field: `universal_extraction: adapter=<adapter> field=<field> confidence=<conf>` — emitted at hook time so future agents can grep an archive rerun for which extractor populated what.", "WARN log on UniversalSpec/CategorySpec validation failure now includes both the inferred DB category AND the bridged sub-slug (`category=suspension subslug=coilover`) so S04's admin extraction-health endpoint can show per-sub-category failure rates.", "ExtractionFailureRate EMF metric continues to increment on validation drop — now firing across the whole catalog because the bridge ensures every non-None DB category resolves to at least UniversalSpec (was previously silent because no category resolved to a registry slug).", "TypeError raised at class-definition time when an adapter declares suppress_universal with an unknown field name — fails at import, before any crawl runs.", "CLI demo (`python -m app.crawlers.universal_extractor_demo`) prints per-fixture extracted-fields summary to stdout — sanity surface for the universal extractor on real archived HTML."]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T04:52:45.610Z
blocker_discovered: false
---

# S02: Universal-field extractor + base-class auto-run

**Five universal-field extractors + base-class apply_universal_extraction hook + category→sub-slug bridge wired into all three production call sites — S01 validation hook now fires across the catalog.**

## What Happened

S02 graduates the M002 extraction substrate from "S01 schemas exist but the validation hook never fires" to "every ingested part with universal-field content gets validated and the universal floor is auto-merged at every call site." Five connected pieces:

**(1) Five universal-field extractors in `app/crawlers/parsing.py` (T01).** `extract_weight`, `extract_material`, `extract_finish`, `extract_warranty`, `extract_fitment_notes` plus an `extract_universal_fields(html)` aggregator. Each returns `(value, confidence_literal)` or `None`. Tiered confidence: JSON-LD Product properties → high; labeled spec-table rows → medium; body-text fallback → low. Weight normalizes to grams via a g/kg/lb/oz unit table plus UN/CEFACT codes; material has a longest-prefix lexicon with aluminium→aluminum and carbon-fiber→carbon fiber canonicalization; finish splits the lexicon into treatments (anodized/polished/...) preferred over color-only matches; warranty converts (year|month|day) tokens into a sortable float number-of-days; fitment_notes captures the first sentence with both chassis code + year range. Every regex bounds its numeric/whitespace runs (`\d{1,8}`, `\s{0,4}`) — caught a real ReDoS during smoke testing where unbounded `\d+` pegged a CPU core for minutes on `'1' * 50_000` despite the 50KB input cap (MEM021/MEM029). Shipping-info DOM blocks are decomposed via BeautifulSoup before the body-text weight fallback so a "Shipping Weight" row never beats the real spec.

**(2) CategorySpec base + UniversalSpec catch-all (T02).** Declared the five universal value fields plus their `_confidence` companions on `CategorySpec` itself in `specs/base.py` so CoiloverSpec/BrakeSpec/TurboSpec inherit them automatically with zero per-spec churn. Created `UniversalSpec(CategorySpec)` in a new `specs/universal.py` module that adds no fields beyond the inherited universal set; registered under the `'universal'` slug in `specs/__init__.py`. `extra='forbid'` carries through, so an unmapped category that hands a category-specific field into UniversalSpec validation still raises ValidationError — the catch-all only validates the five universal fields, not arbitrary keys.

**(3) Category→sub-slug bridge (T03).** New `specs/category_bridge.py` exposes `category_to_subslug(category_name, *, name=None, description=None)` that maps DB category names to SpecRegistry slugs via parent-aware keyword scoring: `'suspension'` + coilover keyword → `'coilover'`; `'engine'` + turbo keyword → `'turbo'`; `'brakes'` always → `'brake'`; every other non-None DB category falls through to `'universal'` (UniversalSpec catch-all). Parent-category gating prevents stray 'coilover'/'turbo' prose from hijacking the schema on a wheels/exhaust part — both keyword AND matching parent are required for keyword-gated sub-slugs. When `category_name is None`, returns None so ingest preserves S01's fail-soft pass-through.

**(4) Base-class auto-run hook + suppression (T03).** `RetailerCrawlerAdapter.apply_universal_extraction(html, payload)` lazy-imports the aggregator, filters via `suppress_universal: ClassVar[list[str]] = []`, builds a flat `{<field>: value, <field>_confidence: conf}` shape, and merges into `payload.specifications` with **adapter-wins** semantics — the hook only fills keys the adapter didn't already set. Same payload instance is mutated and returned, so call sites use the canonical reflexive shape. `__init_subclass__` validates `suppress_universal` entries against a module-level `UNIVERSAL_FIELD_NAMES` frozenset at class-creation time — typos fail loudly with TypeError carrying the offending adapter qualname. Per-merge DEBUG log (`universal_extraction: adapter=X field=weight_grams confidence=high`) gives future agents a grep target.

**(5) Three call-site insertions + ingest update (T04 + T03d).** Inserted `payload = adapter.apply_universal_extraction(html, payload)` at three production call sites — `runner.py` (line 589, after None-skip, before archive+ingest), `archive_rescrape.py` (line 152, after None-skip+failed branch, before existing ingest_payload try), and `api/endpoints/crawled_pages.py` (line 284, on the success path of the extension `/scrape` endpoint, using sanitized_html to keep the ReDoS guard). `ingest_payload` in `crawlers/base.py` now does a two-step resolve: `category_to_subslug(inferred_name, ...)` → `default_registry.resolve(bridged_subslug)`. WARN log includes both inferred DB category and bridged sub-slug so S04's admin endpoint can show per-sub-category failure rates.

**Contract change worth flagging (MEM024/MEM030):** before S02, no DB category resolved to a registry slug — the validation hook never fired. After S02, every non-None DB category resolves to at least 'universal', so payloads that fail UniversalSpec validation now drop to `specifications=None` and increment `ExtractionFailureRate` instead of silently passing through. Pass-through (no validation) only happens when `category_name is None` or `payload.specifications is None`. Existing test for "unregistered slug pass-through" was replaced by a wheels-validates-against-universal test in `test_ingest_spec_validation.py`.

**Test surface (T05).** Two new pytest files: `test_universal_extractor.py` (5 extractors × {high/medium/low/no-match/malformed}, weight unit normalization for kg/lb/oz/g, ReDoS-resistance budget at 100KB pathological input, real-archived-fixture smoke checks, plus the demo CLI subprocess test) and `test_universal_extraction_hook.py` (12 tests covering auto-extraction, adapter-wins merge, suppression, empty-input no-ops, debug log emission, and the `__init_subclass__` validation gate). T03 also extended `test_category_slug_bridge.py` with branch-by-branch coverage and added `TestIngestUsesBridgeToResolveSubslug` to `test_ingest_spec_validation.py` proving the bridge fires in production. Plus a runnable `app/crawlers/universal_extractor_demo.py` CLI module that walks the 5 tracked adapter fixtures and prints per-fixture extracted-fields summaries — pinned by the subprocess test to exit 0 with all 5 slugs in stdout.

**Empirical extraction signal observed on real fixtures:** amsperformance hits weight_grams=907.2g (high) + fitment_notes (medium); subispeed hits material=carbon fiber (low). Three of five tracked fixtures (briantooleyracing, cobbtuning, texasspeed) return None from `parse_product_page` on the archived snapshots — that's parser coverage, not extractor coverage, and is the gap S03 attacks via the 111-adapter compliance retrofit.

**No fixture refresh required.** The 5 characterization tests under `tests/crawlers/test_characterization_*.py` exercise `parse_product_page()` directly via the adapter registry and never touch `apply_universal_extraction` — `expected.json` snapshots are pinned to pre-merge parser output (unchanged) and all 5 still pass.

## Verification

**Slice-level verify (single pytest invocation, per MEM019):**

`pytest backend/tests/crawlers/test_universal_extractor.py backend/tests/crawlers/test_universal_extraction_hook.py backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=backend` → **86 passed in 10.97s**.

**Full crawler-suite regression sweep:**

`pytest backend/tests/crawlers/ -n auto --rootdir=backend --no-cov -q` → **1364 passed, 1 skipped (postgres-only) in 12.76s**. Zero regressions in adapter discovery, characterization snapshots, or the SpecRegistry contract suite.

**CLI demo (slice plan's primary demo gate):**

`python -m app.crawlers.universal_extractor_demo` from `backend/` → **exit 0**. Output includes all 5 adapter slugs in stdout:
- `amsperformance: weight_grams=907.2 (high), fitment_notes=AMS Performance R8/Huracan Billet Rear Sway Bar End Links - AMS Performance (medium)`
- `briantooleyracing: (parse_product_page returned None)`
- `cobbtuning: (parse_product_page returned None)`
- `subispeed: material=carbon fiber (low)`
- `texasspeed: (parse_product_page returned None)`

Real-extraction signal observed on 2 of 5 (amsperformance + subispeed); the 3 None-parse outcomes are parser-coverage gaps S03 will close, not extractor failures.

**Suppression contract (slice plan's second demo requirement):**

`tests/crawlers/test_universal_extraction_hook.py::TestApplyUniversalExtractionSuppression::test_suppressed_field_is_absent_from_specifications` → pass. Adapter declares `suppress_universal=['weight_grams']`; HTML containing 'Weight: 25 lb' produces a payload whose specifications dict does NOT contain weight_grams. Companion test `test_unknown_field_in_suppress_universal_raises_at_class_creation` confirms typos in suppress_universal fail at class-creation, not at extraction-time.

**ReDoS budget verified:**

`tests/crawlers/test_universal_extractor.py::TestExtractorsAreReDoSResistant` enforces a 1s wallclock budget per extractor and 5s for the aggregator on a 100KB pathological digit pile. All extractors pass under budget — fix from MEM029 (bounded numeric/whitespace runs) holds.

**Observability surface verified:**

`test_debug_log_emitted_per_extracted_field` proves the per-field DEBUG line (`universal_extraction: adapter=X field=Y confidence=Z`) emits at hook time. Ingest WARN log now carries both the inferred DB category and the bridged sub-slug — surface S04's extraction-health endpoint will consume.

## Requirements Advanced

- R002 — Universal-fields utilities (5 extractors + aggregator) and base-class auto-merge hook landed in production at 3 call sites; adapter authors no longer need to re-implement weight/material/finish/warranty/fitment extraction per retailer.
- R018 — Crawler test coverage extended with 86 new test cases across universal extractor units, base-class hook contracts (auto-extract, adapter-wins, suppression, empty-input safety, debug log, __init_subclass__ gate), category bridge branches, and ingest-validation paths via the bridge.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T03 landed test_category_slug_bridge.py and the bridge extension to test_ingest_spec_validation.py even though the slice plan attributes both to T05 — the T03 verify command requires both files to exist and pass, and the bridge change inherently breaks the old 'unregistered slug pass-through' assertion. T05 extended test_category_slug_bridge.py with deeper coverage and added the remaining test files. No fixture refresh was required at T04: characterization tests target parse_product_page() directly and bypass apply_universal_extraction; expected.json snapshots remained accurate against unchanged parser output. T01 added explicit numeric/whitespace bounds (\\d{1,8}, \\s{0,4}) to every regex during ReDoS-fixing — the plan called out the 50KB input cap and 'no nested quantifiers on user-controlled groups' but unbounded greedy quantifiers also need explicit bounds (captured in MEM029). Used DOM-aware BeautifulSoup decomposition of shipping-info blocks instead of the plan's regex-based skip pattern — more robust across adapter shapes."

## Known Limitations

"Three of five tracked adapter fixtures (briantooleyracing, cobbtuning, texasspeed) currently return None from parse_product_page on the archived snapshots — that's a parser-coverage gap S03 will close via the 111-adapter compliance retrofit, not an extractor-coverage gap. The universal extractor itself is exercised by amsperformance (weight high + fitment medium) and subispeed (material low) on real archived HTML. Suppression mechanism cannot opt in to extraction (only opt out) — the universal floor is mandatory unless explicitly suppressed; this is the intended design but worth flagging for adapter authors. After S02 the ingest pass-through contract changed: only None-category payloads or None-specifications payloads bypass validation — categorized payloads with malformed specs now drop to None + emit ExtractionFailureRate (this is the intended contract change that makes the hook fire across the catalog, captured in MEM024/MEM030)."

## Follow-ups

"S03 will retrofit category_targets declarations across all 111 adapters and inherit the S02 universal layer automatically — adapters needing per-field opt-out add suppress_universal at that point. S04 will surface per-sub-category failure rates from the WARN log enrichment landed in this slice (admin extraction-health endpoint reads inferred + bridged subslug). False-positive rate on weight/material extraction against real archive data will be measured in S04's compliance audit; if untenable, suppression conventions or confidence thresholds may evolve. The 3 None-parse fixture cases (briantooleyracing, cobbtuning, texasspeed) need parser-coverage attention in S03 so the demo surfaces real extraction signal on all 5 adapters, not 2."

## Files Created/Modified

- `backend/app/crawlers/parsing.py` — 5 pure-function universal extractors + aggregator + bounded ReDoS guards
- `backend/app/crawlers/specs/base.py` — 5 universal value+confidence field pairs declared on CategorySpec base
- `backend/app/crawlers/specs/universal.py` — NEW: UniversalSpec(CategorySpec) catch-all (no extra fields)
- `backend/app/crawlers/specs/__init__.py` — Register UniversalSpec under 'universal' slug; updated __all__
- `backend/app/crawlers/specs/category_bridge.py` — NEW: category_to_subslug() bridge with parent-aware keyword scoring + 'universal' fallback
- `backend/app/crawlers/adapters/base.py` — apply_universal_extraction hook + suppress_universal ClassVar + UNIVERSAL_FIELD_NAMES frozenset + __init_subclass__ validation gate
- `backend/app/crawlers/base.py` — ingest_payload uses category_to_subslug for two-step slug resolution; WARN log includes both inferred and bridged subslug
- `backend/app/crawlers/runner.py` — Wire apply_universal_extraction between parse_product_page and ingest (line 589)
- `backend/app/crawlers/archive_rescrape.py` — Wire apply_universal_extraction between parse_product_page and ingest (line 152)
- `backend/app/api/endpoints/crawled_pages.py` — Wire apply_universal_extraction in extension /scrape success path using sanitized_html (line 284)
- `backend/app/crawlers/universal_extractor_demo.py` — NEW: runnable CLI module that walks 5 tracked adapter fixtures and prints per-fixture summaries
- `backend/tests/crawlers/test_universal_extractor.py` — NEW: unit tests for 5 extractors + ReDoS budget + fixture smoke + demo subprocess test
- `backend/tests/crawlers/test_universal_extraction_hook.py` — NEW: 12 tests covering auto-extraction, adapter-wins merge, suppression, empty-input safety, debug log, __init_subclass__ gate
- `backend/tests/crawlers/test_category_slug_bridge.py` — NEW: branch-by-branch coverage of category_to_subslug + parametrized registry round-trip
- `backend/tests/crawlers/test_ingest_spec_validation.py` — Extended: TestIngestUsesBridgeToResolveSubslug + replaced 'unregistered slug pass-through' with wheels-validates-against-universal + UniversalSpec acceptance test
