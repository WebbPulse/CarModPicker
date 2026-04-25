---
id: T01
parent: S02
milestone: M002
key_files:
  - backend/app/crawlers/parsing.py
key_decisions:
  - Bound every greedy numeric/whitespace run in the new regexes (\d{1,8}, \s{0,4}) instead of relying on the 50KB input cap alone — the cap protects scan length, but unbounded backtracking inside that window still pegs a CPU core on adversarial input.
  - Use BeautifulSoup .decompose() to strip shipping-info blocks before the body-text weight fallback, rather than a regex skip-pattern — DOM-aware removal is more reliable across the variety of shipping-table shapes adapters surface.
  - Split the finish lexicon into treatments (anodized/polished/...) and colors (black/red/...) with treatments always preferred, so a 'red anodized' page does not score a low-confidence color hit when a high-confidence treatment is available.
  - Use word-bounded chassis matcher (_CHASSIS_IN_TEXT_RE) for fitment_notes rather than reusing _CHASSIS_LIKE_PATTERN directly — the existing pattern is anchored ^...$ for first-token classification, but fitment scanning needs to find chassis mentions inside running prose.
duration: 
verification_result: mixed
completed_at: 2026-04-25T04:23:26.984Z
blocker_discovered: false
---

# T01: Add five pure-function universal-field extractors (weight, material, finish, warranty, fitment_notes) plus aggregator to crawlers/parsing.py

**Add five pure-function universal-field extractors (weight, material, finish, warranty, fitment_notes) plus aggregator to crawlers/parsing.py**

## What Happened

Implemented the universal-field extractor utilities in `backend/app/crawlers/parsing.py` per the T01 contract. Added a 50_000-char input cap (`_UNIVERSAL_INPUT_CAP`) before any scanning, then five pure-function extractors plus an aggregator:

- `extract_weight(html) -> (grams, conf) | None`: prefers JSON-LD Product `weight` (QuantitativeValue with unitCode/unitText, or "12 lb"-style strings) at high confidence; falls back to a labeled "Weight: 25 lb"-style spec row at medium (with shipping-info `<table>/<div>/<section>` blocks decomposed first via BeautifulSoup so a "Shipping Weight" row never beats the real spec); body-text catch-all at low. All values normalized to grams via a unit table covering g/kg/lb/oz plus UN/CEFACT codes (LBR, KGM, GRM, ONZ). Out-of-range values (<1g or >500_000g) reject to None.
- `extract_material`: enum lexicon with longer-prefixed entries first ("billet aluminum" before "aluminum"); canonicalizes "aluminium" → "aluminum" and "carbon-fiber" → "carbon fiber". JSON-LD `material` (string or `{name}` dict) → high; labeled "Material:" row → medium; body-text → low.
- `extract_finish`: split lexicon — "treatment" finishes (anodized, polished, powder coated, ...) score above color-only matches (black/red/blue/silver/gold). JSON-LD `color`/`additionalProperty` carries treatments at high, colors at low; labeled treatment is medium, free-text treatment or any color is low.
- `extract_warranty`: regex `(\d{1,4})[\s-]{0,4}(year|yr|month|day)\s*(limited\s+)?warranty` → days (year=365.25, month=30.44, day=1) so values are sortable. JSON-LD `warranty` field is high; body-text is medium.
- `extract_fitment_notes`: re-uses the existing `_looks_like_chassis_code` helper plus a new `_CHASSIS_IN_TEXT_RE` (word-bounded variant of `_CHASSIS_LIKE_PATTERN`) and a year-range regex; returns the first sentence containing both chassis + year as high, chassis-or-year alone as medium/low, capped at 300 chars.
- `extract_universal_fields(html)` aggregator: runs all five and returns a `Dict[str, Tuple[Any, str]]` keyed `weight_grams`/`material`/`finish`/`warranty_days`/`fitment_notes`. Empty/None input returns {}.

Caught a ReDoS during smoke testing: the original `[\d]+(?:\.[\d]+)?\s*(lbs?|...)` form pegged a CPU core for minutes on `"1" * 50_000` because the unbounded greedy `\d+` backtracked one char at a time looking for a unit token. Fixed by bounding the digit/whitespace runs explicitly (`\d{1,8}(?:\.\d{1,4})?`, `\s{0,4}`) and adding `(?<!\d)` to anchor the leading boundary cleanly. Same fix applied to the warranty regex (`\d{1,4}`) and chassis pattern (`{1,4}`). Captured MEM021 so future extractor work avoids the same trap.

Smoke test exercises every confidence tier including a JSON-LD weight (QuantitativeValue with unitCode "KGM"), a shipping-block strip-and-prefer test, out-of-range rejection (0.0001g and 9999kg), aluminium→aluminum canonicalization, treatment-beats-color finish, 30-day warranty, chassis+year fitment, and a 100KB pathological-input ReDoS check (completed in 73ms across all five). Aggregator returns the expected keys when fed combined HTML.

No call sites changed — purely additive utilities per the task contract. The CategorySpec base does not yet declare these fields (T02's job), so the values are not yet wired through the validation hook (T03's job) or the runner/archive_rescrape/crawled_pages call sites (T04's job).

## Verification

Three layers of verification:

1. Smoke test (`backend/_smoke_universal.py`, deleted post-run) covered each extractor's high/medium/low confidence path, empty/None safety, unit normalization (kg/lb→g), out-of-range rejection, canonicalization (aluminium→aluminum), shipping-block strip, JSON-LD weight high path with QuantitativeValue+unitCode, JSON-LD warranty high path, fitment chassis+year=high, fitment chassis-only=medium, and the aggregator returning all five keys. All assertions passed.

2. ReDoS guard probe (`backend/_perf_check.py`, deleted post-run) ran every extractor against three 100KB pathological inputs (digit-only, alpha-only, weight-labeled with massive padding). Every extractor completed in <13ms — no super-linear behavior. The 50KB input cap plus bounded numeric runs (\d{1,8}, \d{1,4}) and bounded whitespace (\s{0,4}) keep the engine linear-time on adversarial input.

3. Full crawler test suite ran clean: `pytest tests/crawlers/ -n auto --rootdir=.` → 1284 passed, 1 skipped in 10.53s. No regression in existing characterization tests, adapter tests, ingest validation tests, or the SpecRegistry contract tests.

The T01 verify command (`pytest backend/tests/crawlers/test_universal_extractor.py -n auto`) returns "no tests ran" because T05 hasn't created that test file yet — expected per the slice plan: T01 ships the utilities, T05 ships the unit tests that exercise them.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest backend/tests/crawlers/ -n auto --rootdir=backend` | 0 | ✅ pass | 10530ms |
| 2 | `python backend/_smoke_universal.py (universal extractor smoke + 100KB ReDoS guard)` | 0 | ✅ pass | 200ms |
| 3 | `python backend/_perf_check.py (per-extractor 100KB pathological-input probe)` | 0 | ✅ pass | 200ms |
| 4 | `pytest backend/tests/crawlers/test_universal_extractor.py -n auto --rootdir=backend` | 5 | ⚪ no tests ran (test file is T05's deliverable) | 7820ms |

## Deviations

Plan said the labeled-weight regex should match `outside <table class=\"shipping*\"|.shipping-info` — implemented as a BeautifulSoup-based decomposition of any `<table>/<div>/<section>` whose class or id contains 'shipping' before the body-text fallback runs. DOM-aware strip is more robust across adapter shapes than a single regex assertion. Behavior matches the plan's intent (shipping rows must not beat real spec rows). Also added explicit numeric/whitespace bounds (\\d{1,8}, \\s{0,4}) to every regex during ReDoS-fixing — the plan called out the 50KB input cap and 'no nested quantifiers on user-controlled groups' but unbounded greedy quantifiers also need to be bounded; documented in MEM021.

## Known Issues

None for this task. Downstream tasks have remaining work as designed: T02 declares the universal fields on CategorySpec, T03 wires the apply_universal_extraction hook, T04 inserts at the three call sites, T05 ships the unit tests that exercise these extractors against tracked fixture HTML.

## Files Created/Modified

- `backend/app/crawlers/parsing.py`
