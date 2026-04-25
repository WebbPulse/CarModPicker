---
estimated_steps: 10
estimated_files: 1
skills_used: []
---

# T01: Implement five universal-field extractors in crawlers/parsing.py

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

## Inputs

- ``backend/app/crawlers/parsing.py` — module being extended; reuse existing `_CHASSIS_LIKE_PATTERN` and follow the same regex style`
- ``backend/app/crawlers/specs/base.py` — confirms confidence Literal type matches (no edit)`

## Expected Output

- ``backend/app/crawlers/parsing.py` — five new extract_* functions plus extract_universal_fields aggregator added below the existing parsing helpers`

## Verification

pytest backend/tests/crawlers/test_universal_extractor.py -n auto --rootdir=backend

## Observability Impact

Each extract_* function returns (value, confidence) or None — silent failure mode is intentional. T03 wires the DEBUG log line that records which extractor populated which field per page; this task only needs to make the values available.
