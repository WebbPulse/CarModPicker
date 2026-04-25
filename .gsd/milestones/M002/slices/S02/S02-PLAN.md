# S02: Universal-field extractor + base-class auto-run

**Goal:** Build the universal-field extractor — shared utilities in crawlers/parsing.py for weight, material, finish, warranty, and fitment_notes — wire it as a base-class auto-run hook on RetailerCrawlerAdapter that the runner / archive_rescrape / extension-scrape call sites invoke after parse_product_page returns, bridge the infer_category() (DB-name) → SpecRegistry (sub-slug) gap so the S01 validation hook actually fires in production, and let adapters opt out of specific universal fields via a suppress_universal ClassVar.
**Demo:** Run a CLI one-liner against 5 archived HTML samples drawn from 5 different adapters: each result's specifications dict is populated with universal fields at appropriate confidence levels. Verify suppression: an adapter declares suppress_universal=['weight'] and that field is not auto-extracted for that adapter.

## Must-Haves

- Five universal extractors (`extract_weight`, `extract_material`, `extract_finish`, `extract_warranty`, `extract_fitment_notes`) live in `app/crawlers/parsing.py`, each returning `(value, confidence)` or `None`, with confidence ∈ {'high','medium','low'} per the S01-locked CategorySpec convention.
- CategorySpec base declares the 5 universal value fields plus their `_confidence` companions, so universal-extracted output passes Pydantic `extra='forbid'` validation alongside category-specific fields. A `UniversalSpec(CategorySpec)` catch-all is registered under the `'universal'` slug for categories without a category-specific schema.
- A category-name → sub-category-slug bridge (`category_to_subslug`) resolves DB category names like `'suspension'`/`'brakes'`/`'engine'` to registry slugs `'coilover'`/`'brake'`/`'turbo'` (or `'universal'`) using keyword scoring over the part name+description; `ingest_payload` uses this bridge so the S01 validation hook actually fires in production. The bridge falls back to None when category_name is None — preserves S01 pass-through.
- `RetailerCrawlerAdapter.apply_universal_extraction(html, payload)` post-hook on the base class merges the 5 universal fields into `payload.specifications`, respecting the adapter's `suppress_universal: ClassVar[list[str]]` override (validated against the 5 known field names at __init_subclass__ time).
- The 3 call sites that currently invoke `parse_product_page` followed by `ingest_payload` (`runner.py`, `archive_rescrape.py`, `api/endpoints/crawled_pages.py`) call `adapter.apply_universal_extraction(html, payload)` between the two — single insertion point per file.
- `pytest backend/tests/crawlers/ -n auto --rootdir=backend` passes — covers the new extractor units, the suppression mechanism, the slug bridge, the base-class hook, the bridge-resolves-to-CoiloverSpec ingest test, and a CLI-demo subprocess test that runs `python -m app.crawlers.universal_extractor_demo` and asserts exit 0.
- ## Threat Surface
- **Abuse**: None — extractor reads adapter-supplied HTML server-side; no new user input boundary. Existing crawler input sanitization in `crawlers/sanitize.py` still applies for the extension-scrape route.
- **Data exposure**: None — universal fields are public product metadata (weight, material, finish, warranty, fitment notes). No PII.
- **Input trust**: Universal extractors run regex over arbitrary retailer HTML; pathological input could trigger ReDoS. Mitigation: every regex must be linear-time (no nested quantifiers on user-controlled text) and input scanning is capped at the first 50_000 chars of `html` before scanning. Document this constraint in the extractor module docstring.
- ## Requirement Impact
- **Requirements touched**: R002 (universal-fields utilities + post-hook merge), R018 (crawler test coverage extends to universal extractor + bridge).
- **Re-verify**: Existing crawler test suite (`pytest backend/tests/crawlers/`) — must remain green. The 5 characterization-test snapshots (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed) may need refresh if the universal extractor populates `specifications` from their archived HTML; expected.json files are a known fixture refresh point.
- **Decisions revisited**: D002 (universal-fields strategy) — this slice is the first concrete implementation; if the false-positive rate on weight/material extraction proves untenable on real archive data during T05, suppression conventions or confidence thresholds may need to evolve in S03.

## Proof Level

- This slice proves: contract + integration — this slice proves the universal extractor + auto-run hook + slug bridge end-to-end against real archived HTML through the runner-style call site (not the live crawler — no network). Real runtime required: yes (sqlite test DB + tracked HTML fixtures). Human/UAT required: no.

## Integration Closure

Upstream surfaces consumed: `app.crawlers.specs.default_registry` + `CategorySpec` subclasses (S01), `app.crawlers.adapters.base.RetailerCrawlerAdapter` (S01-extended with `category_targets`), `app.crawlers.base.ScrapedPayload.specifications` field (S01), `app.crawlers.base.ingest_payload` validation hook (S01), `app.core.category_inference.infer_category` (existing — provides DB category names that the bridge maps to sub-slugs).

New wiring introduced in this slice: 5 extractor functions in `parsing.py`; universal value+confidence fields on the CategorySpec base; UniversalSpec catch-all in a new `app/crawlers/specs/universal.py` module; `category_to_subslug` bridge in a new `app/crawlers/specs/category_bridge.py` module; `apply_universal_extraction` method on the adapter base; `suppress_universal` ClassVar on the adapter base; one call-site insertion in each of `runner.py`, `archive_rescrape.py`, `api/endpoints/crawled_pages.py`; CLI demo module under `app/crawlers/universal_extractor_demo.py`.

What remains before the milestone is truly usable end-to-end: S03 must propagate `category_targets` declarations to all 111 adapters; S04 must surface universal-field coverage in the admin extraction-health endpoint; S04's compliance audit will count adapters whose archived HTML produces ≥1 universal field as 'covered' (vs binary 'compliant').

## Verification

- Runtime signals: existing S01 WARN log + ExtractionFailureRate EMF metric remain the failure surface; the bridge-resolved sub-slug appears in the WARN log alongside the raw inferred name when validation fails, so S04's admin extraction-health endpoint sees per-sub-category granularity. New DEBUG log line per universal field successfully extracted (`universal_extraction: adapter=X field=weight_grams confidence=high`) so future agents can grep an archive rerun for which extractor populated what.
- Inspection surfaces: `Part.specifications IS NOT NULL` rate per category in the DB rises as the bridge starts firing; CLI demo script prints per-fixture extracted-fields summary to stdout; existing `tests/crawlers/fixtures/<adapter>/expected.json` snapshots show the new specifications dict shape after T04's refresh.
- Failure visibility: per-extractor failures are silent (return None); aggregate observability is the existing ExtractionFailureRate metric. Input-size cap (50KB) is the ReDoS guard — no separate timing budget needed if the regex shapes stay linear-time.
- Redaction constraints: none — all output is public product metadata.

## Tasks

- [x] **T01: Implement five universal-field extractors in crawlers/parsing.py** `est:2h`
  Add five pure-function extractors to `backend/app/crawlers/parsing.py` — `extract_weight(html: str) -> tuple[float, Literal['high','medium','low']] | None`, `extract_material`, `extract_finish`, `extract_warranty`, `extract_fitment_notes`. Each returns `(value, confidence)` or `None`. They must be deterministic, side-effect-free, and import-safe (no DB, no network, no I/O). The S01 CategorySpec convention is `Optional[Literal['high','medium','low']]` for confidence — match it exactly.

Extraction strategy per field (high → low confidence priority order):
- `extract_weight`: (high) JSON-LD Product `weight` property with a unit (`{value, unitCode}` or `'12 lb'` strings); (medium) labeled DOM/spec-table row matching `/weight\s*[:=]?\s*([\d.]+)\s*(lb|kg|oz|g)\b/i` *outside* `<table class="shipping*"|.shipping-info` blocks; (low) first body-text match. Always normalize to grams (return float grams). Reject values < 1 g or > 500_000 g (500 kg) as obvious junk (returns None).
- `extract_material`: enum-style match against {'aluminum','aluminium','steel','stainless steel','titanium','carbon fiber','carbon-fiber','plastic','rubber','silicone','brass','copper','iron','cast iron','forged steel','billet aluminum','6061 aluminum','7075 aluminum'} — case-insensitive, whole-word. Returns the matched canonical form (e.g. 'aluminum' for both 'aluminum' and 'aluminium', 'carbon fiber' for both spellings). High confidence on JSON-LD `material`; medium on labeled spec-row; low on title or first description sentence.
- `extract_finish`: enum match against {'anodized','polished','brushed','painted','powder coated','powder-coated','raw','clear-coat','satin','matte','gloss','chrome','black','red','blue','silver','gold'}. Same confidence tiering. Color-only matches return low confidence (so a red-anodized part scores higher than a 'red' free-text mention).
- `extract_warranty`: regex `/(\d+)[-\s]*(year|yr|month|day)\s*(limited\s+)?warranty/i`; convert to a float number-of-days (year = 365.25, month = 30.44, day = 1) so values are comparable and sortable. Returns None when no match. High confidence on JSON-LD `warranty`; medium on body-text match.
- `extract_fitment_notes`: capture the first paragraph or list block that mentions a chassis code (E46/E9x/F80/G82/etc — reuse the existing `_CHASSIS_LIKE_PATTERN` from parsing.py) and a year range (`2008-2013`, `'08-'13`). Returns the captured string, capped at 300 chars. High confidence when both chassis + year matched in same sentence; medium when only one; low when only loose chassis mention.

ReDoS / cost guard: every regex must be linear-time on user-controlled text. Cap input scanning at the first 50_000 chars of `html` (well above any real product page). Document this in the module-level docstring you add at the top of the new section. No nested quantifiers on user-controlled groups.

Add a sixth helper `extract_universal_fields(html: str | None) -> dict[str, tuple[Any, str]]` that runs all five and returns the non-None results keyed by field name. Returns an empty dict when nothing extracted or when html is None/empty. This is the call-site for T03's hook.

Do NOT modify any adapter, ingest path, or spec module in this task — purely additive utilities in parsing.py.
  - Files: `backend/app/crawlers/parsing.py`
  - Verify: pytest backend/tests/crawlers/test_universal_extractor.py -n auto --rootdir=backend

- [x] **T02: Add universal fields to CategorySpec base + UniversalSpec catch-all** `est:1h`
  Make universal-extracted fields validate cleanly against the existing CategorySpec schemas. The existing `CategorySpec(BaseModel)` in `backend/app/crawlers/specs/base.py` uses `ConfigDict(extra='forbid')`, so universal fields must be declared on the schema or validation will reject them.

Approach: define the five universal value-fields plus their paired `_confidence` companions on the `CategorySpec` base itself, so every concrete spec inherits them automatically. Field shapes (matching T01's return contract):
- `weight_grams: Optional[float] = None` + `weight_grams_confidence: Optional[Literal['high','medium','low']] = None`
- `material: Optional[str] = None` + `material_confidence: Optional[Literal['high','medium','low']] = None`
- `finish: Optional[str] = None` + `finish_confidence: Optional[Literal['high','medium','low']] = None`
- `warranty_days: Optional[float] = None` + `warranty_days_confidence: Optional[Literal['high','medium','low']] = None`
- `fitment_notes: Optional[str] = None` + `fitment_notes_confidence: Optional[Literal['high','medium','low']] = None`

Update the module docstring of `base.py` to document that the 5 universal fields are inherited and that subclasses only need to add category-specific fields. CoiloverSpec / BrakeSpec / TurboSpec concrete specs need NO field changes — they automatically gain the universal fields via inheritance.

Also add a `UniversalSpec(CategorySpec)` concrete subclass in a new file `backend/app/crawlers/specs/universal.py` — declares no extra fields beyond the inherited universal set. Register it in `app/crawlers/specs/__init__.py`: `default_registry.register('universal', UniversalSpec)`. The T03 bridge will resolve unmapped categories to 'universal' so an unknown category with universal fields can still ingest a validated specs block instead of silently dropping.

Update `__init__.py`'s `__all__` list to include `UniversalSpec` and import it.

Update `backend/tests/crawlers/test_spec_registry_contract.py` *only* if any existing test pins the field set on CategorySpec via reflection or schema introspection; if it does, extend the assertions to include the new universal fields. Do not break the 16 existing contract tests.
  - Files: `backend/app/crawlers/specs/base.py`, `backend/app/crawlers/specs/universal.py`, `backend/app/crawlers/specs/__init__.py`, `backend/tests/crawlers/test_spec_registry_contract.py`
  - Verify: pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=backend

- [ ] **T03: Add category-name → sub-slug bridge + base-class apply_universal_extraction hook + suppress_universal ClassVar + ingest update** `est:2h`
  Three connected pieces that together form the auto-run mechanism. Build them in this order so each piece can be unit-tested as you go.

**(a) Sub-slug bridge (`backend/app/crawlers/specs/category_bridge.py`).**
Create a new module exposing `category_to_subslug(category_name: str | None, *, name: str | None = None, description: str | None = None) -> str | None` that maps a DB category name to a SpecRegistry sub-slug using keyword scoring over the part name + description. Mirror the structure of `app/core/category_inference.py` — small per-slug keyword dict, word-boundary matches, best-score-wins. Initial mapping (3 sub-slugs to land + 'universal' fallback):
- `'suspension'` + ('coilover'|'coilovers'|'coil over'|'coil-over' in name/desc) → `'coilover'`
- `'brakes'` (always — single brake sub-slug for now) → `'brake'`
- `'engine'` + ('turbo'|'turbocharger' in name/desc) → `'turbo'`
- Everything else (or 'suspension'/'engine' without the disambiguating keyword): return `'universal'` so the UniversalSpec fallback fires.
- When `category_name is None`: return None (caller should skip validation entirely — preserves S01 pass-through).

Returning `'universal'` when category_name is set but has no sub-slug is the change that makes the S01 hook actually fire across the catalog. Today it never fires because no DB category name resolves to a registry slug; after this, every category with universal-field content gets validated against UniversalSpec.

**(b) Base-class `apply_universal_extraction` method (`backend/app/crawlers/adapters/base.py`).**
Add `def apply_universal_extraction(self, html: str, payload: ScrapedPayload) -> ScrapedPayload` to `RetailerCrawlerAdapter`. Implementation:
1. If payload is None, return payload unchanged.
2. Lazy import: `from app.crawlers.parsing import extract_universal_fields` inside the method to keep the import cycle broken (parsing.py already imports ScrapedPayload from base.py).
3. Call `extract_universal_fields(html)`.
4. Filter out any field listed in `self.suppress_universal` (new ClassVar — see (c)).
5. Build a flat dict `{'<field>': value, '<field>_confidence': conf}` for each surviving extracted field.
6. Merge into `payload.specifications` — preserve any adapter-set keys (adapter wins). Create a new dict if specifications is None. Only assign back to payload if the merged dict is non-empty.
7. Emit `logger.debug('universal_extraction: adapter=%s field=%s confidence=%s', self.ADAPTER_NAME, field, confidence)` for each extracted field.
8. Return the (possibly mutated) payload.

**(c) `suppress_universal: ClassVar[list[str]] = []` on `RetailerCrawlerAdapter`.**
Default empty (every adapter gets all 5 universal fields). Adapters override to opt out. Validate at import time inside the existing `__init_subclass__` hook (alongside `category_targets` validation): each entry must be one of the 5 known field names {'weight_grams','material','finish','warranty_days','fitment_notes'}. Raise TypeError on unknown name with the adapter qualname so typos fail loudly.

**(d) Update `ingest_payload` slug resolution in `backend/app/crawlers/base.py`.**
In the existing validation hook, replace the bare `default_registry.resolve(inferred_name)` with a two-step: first call `category_to_subslug(inferred_name, name=payload.name, description=payload.description)`, then resolve that. If the bridge returns None, keep the existing pass-through (no change). Update the WARN log to include both `inferred_name` AND the bridged sub-slug, so S04's admin endpoint can show per-sub-category failure rates. Use a lazy import for `category_to_subslug` inside the validation hook to avoid pulling specs/category_bridge into the import graph at module load.

No call-site changes in this task — that's T04. This task only adds the bridge + hook + ClassVar + ingest slug resolution.
  - Files: `backend/app/crawlers/specs/category_bridge.py`, `backend/app/crawlers/adapters/base.py`, `backend/app/crawlers/base.py`
  - Verify: pytest backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py backend/tests/crawlers/test_adapter_discovery.py -n auto --rootdir=backend

- [ ] **T04: Wire apply_universal_extraction into runner / archive_rescrape / crawled_pages call sites + refresh fixture snapshots** `est:1h`
  Insert the universal-extraction hook between `parse_product_page` and `ingest_payload` at the three call sites. Single-line insertion per file plus a sanity check that the existing flow is unchanged for None-payload returns.

**Call site 1: `backend/app/crawlers/runner.py` (around line 574).**
Current shape:
```python
payload = adapter.parse_product_page(html, url)
if payload is None:
    skipped_not_product += 1
    ...
    continue
# ... archive HTML ...
part = ingest_payload(db, payload, ...)
```
New shape:
```python
payload = adapter.parse_product_page(html, url)
if payload is None:
    skipped_not_product += 1
    ...
    continue
payload = adapter.apply_universal_extraction(html, payload)
# ... archive HTML ...
part = ingest_payload(db, payload, ...)
```
The hook is called *after* the None check (no point extracting against junk pages) and *before* archive + ingest (so the merged specifications land in the same DB write).

**Call site 2: `backend/app/crawlers/archive_rescrape.py` (around line 143).**
Current shape:
```python
payload = adapter.parse_product_page(html, page.url)
if payload is None:
    page.parse_status = 'failed'
    ...
```
Insert `payload = adapter.apply_universal_extraction(html, payload)` after the None check, before the existing `try: ingest_payload(...)`.

**Call site 3: `backend/app/api/endpoints/crawled_pages.py` (around line 267).**
This is the extension `/scrape` endpoint where the Chrome extension uploads HTML. Locate the existing `payload = adapter.parse_product_page(sanitized_html, url)` line; insert the hook on the next line after the None-skip branch. Same shape as the other two sites.

Then refresh the 5 stale characterization-test snapshots if T03's bridge change causes any of them to populate `specifications` with universal fields where today they're `null`. Files to check: `backend/tests/crawlers/fixtures/{amsperformance,briantooleyracing,cobbtuning,subispeed,texasspeed}/expected.json`. Run `pytest backend/tests/crawlers/test_characterization_*.py -n auto --rootdir=backend` to surface any drift; refresh the JSON if needed by setting the actual extracted dict (or keep `null` if extraction returns nothing). Do NOT introduce new fixtures; just refresh existing ones if the merged universal-field output requires it.

No new files. Three call-site edits + up to five fixture-snapshot refreshes.
  - Files: `backend/app/crawlers/runner.py`, `backend/app/crawlers/archive_rescrape.py`, `backend/app/api/endpoints/crawled_pages.py`, `backend/tests/crawlers/fixtures/amsperformance/expected.json`, `backend/tests/crawlers/fixtures/briantooleyracing/expected.json`, `backend/tests/crawlers/fixtures/cobbtuning/expected.json`, `backend/tests/crawlers/fixtures/subispeed/expected.json`, `backend/tests/crawlers/fixtures/texasspeed/expected.json`
  - Verify: pytest backend/tests/crawlers/ -n auto --rootdir=backend

- [ ] **T05: Tests for universal extractor, suppression, slug bridge, and base-class hook + CLI demo script + demo subprocess test** `est:2h30m`
  Write the verification suite that proves S02's slice goal and produces the demo script. Four new test files plus one runnable CLI module, plus an extension to the existing ingest-validation test file.

**(1) `backend/tests/crawlers/test_universal_extractor.py`** — unit tests for the 5 extractors from T01. For each extractor, cover: high-confidence happy path (JSON-LD or labeled spec row), medium-confidence path (body text), low-confidence path where applicable, no-match returns None, malformed input returns None (empty string, None — should never raise), and unit normalization (kg→g, lb→g, oz→g for weight). Most extractor tests just call the functions directly with raw HTML strings. Add one ReDoS-resistance test: build a 100KB pathological string (long repeating digits, e.g. `'1' * 100_000`) and assert each extractor returns within 1 second wallclock. Use existing tracked fixture HTML from `tests/crawlers/fixtures/<adapter>/product.html` for at least 3 of the 5 extractors so tests prove the extractor works on real archived pages, not just hand-crafted strings.

**(2) `backend/tests/crawlers/test_universal_extraction_hook.py`** — base-class hook tests. (a) Construct a minimal test adapter that subclasses RetailerCrawlerAdapter, declares `category_targets=['coilover']`, and returns a fixed ScrapedPayload from parse_product_page. Call `adapter.apply_universal_extraction(html, payload)` with HTML that contains a labeled 'Weight: 25 lb' row; assert the returned payload's specifications dict has `weight_grams` set to ~11340 (25 lb in grams) and `weight_grams_confidence` set. (b) Suppression test: declare a second test adapter with `suppress_universal=['weight_grams']`; assert weight_grams is absent from specifications even though the HTML contains it. (c) Adapter-wins merge: declare an adapter that returns a payload with `specifications={'weight_grams': 999.0, 'weight_grams_confidence': 'high'}` and call the hook on HTML that contains different weight text — assert the adapter's value is preserved (hook merges only fields the adapter didn't set). (d) Empty-HTML safety: hook returns the payload unchanged when extract_universal_fields returns {}. (e) Validation gate at __init_subclass__: declaring an adapter with `suppress_universal=['not_a_real_field']` raises TypeError at class-definition time.

**(3) `backend/tests/crawlers/test_category_slug_bridge.py`** — `category_to_subslug` unit tests. Cover the mapping branches: `('suspension', name='ST X35 Coilovers')` → 'coilover'; `('brakes', name='Big Brake Kit')` → 'brake'; `('engine', name='K04 Turbo')` → 'turbo'; `('engine', name='Cold Air Intake')` → 'universal' (engine without turbo keyword); `('exhaust', name='Catback')` → 'universal' (no sub-slug for exhaust yet); `(None, ...)` → None. Confirm that the resolved slug, fed into `default_registry.resolve()`, returns a CategorySpec subclass for every non-None case.

**(4) Extend `backend/tests/crawlers/test_ingest_spec_validation.py`** — add a new test `test_ingest_uses_bridge_to_resolve_subslug` that calls ingest_payload with a coilover-keyword payload and asserts the validated specifications were validated against CoiloverSpec (not UniversalSpec) — proves the bridge fired in production. Keep all 7 existing tests passing; the registry save/restore fixture from S01 can stay unchanged for those tests.

**(5) `backend/app/crawlers/universal_extractor_demo.py`** — runnable CLI module. Top-level `if __name__ == '__main__':` block that, for each of the 5 tracked adapter fixtures (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed): loads `tests/crawlers/fixtures/<adapter>/product.html`, instantiates the adapter (look up via `ADAPTER_REGISTRY` in `app/crawlers/adapters/__init__.py`), calls `adapter.parse_product_page(html, fixture_url)`, calls `adapter.apply_universal_extraction(html, payload)`, and prints a one-line summary: `<adapter_slug>: <field1>=<value> (<conf>), <field2>=<value> (<conf>), ...` (or `(no universal fields extracted)` when empty). `sys.exit(0)` on full success, `sys.exit(1)` on any exception. Path lookups use `pathlib.Path(__file__).resolve().parents[2] / 'tests' / 'crawlers' / 'fixtures'` — all under git-tracked paths.

**(6) Add `test_universal_extractor_demo_cli` test inside `test_universal_extractor.py`** — invokes the demo script via `subprocess.run(['python', '-m', 'app.crawlers.universal_extractor_demo'], cwd=str(Path(__file__).parents[2]), capture_output=True, check=False)` and asserts `result.returncode == 0` plus that stdout contains all 5 adapter slugs. Wrapping the CLI demo in a pytest test means the slice's verify command stays a single pytest invocation — no `&&` chaining (per MEM019: the gate splits on `&&`, breaking multi-command verifies).

All new test files run under the existing pytest -n auto convention.
  - Files: `backend/tests/crawlers/test_universal_extractor.py`, `backend/tests/crawlers/test_universal_extraction_hook.py`, `backend/tests/crawlers/test_category_slug_bridge.py`, `backend/tests/crawlers/test_ingest_spec_validation.py`, `backend/app/crawlers/universal_extractor_demo.py`
  - Verify: pytest backend/tests/crawlers/test_universal_extractor.py backend/tests/crawlers/test_universal_extraction_hook.py backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto -v --rootdir=backend

## Files Likely Touched

- backend/app/crawlers/parsing.py
- backend/app/crawlers/specs/base.py
- backend/app/crawlers/specs/universal.py
- backend/app/crawlers/specs/__init__.py
- backend/tests/crawlers/test_spec_registry_contract.py
- backend/app/crawlers/specs/category_bridge.py
- backend/app/crawlers/adapters/base.py
- backend/app/crawlers/base.py
- backend/app/crawlers/runner.py
- backend/app/crawlers/archive_rescrape.py
- backend/app/api/endpoints/crawled_pages.py
- backend/tests/crawlers/fixtures/amsperformance/expected.json
- backend/tests/crawlers/fixtures/briantooleyracing/expected.json
- backend/tests/crawlers/fixtures/cobbtuning/expected.json
- backend/tests/crawlers/fixtures/subispeed/expected.json
- backend/tests/crawlers/fixtures/texasspeed/expected.json
- backend/tests/crawlers/test_universal_extractor.py
- backend/tests/crawlers/test_universal_extraction_hook.py
- backend/tests/crawlers/test_category_slug_bridge.py
- backend/tests/crawlers/test_ingest_spec_validation.py
- backend/app/crawlers/universal_extractor_demo.py
