---
estimated_steps: 4
estimated_files: 2
skills_used:
  - test
---

# T02: Add category_targets ClassVar on adapter base and specifications field on ScrapedPayload

Extend the two foundation types so adapters can declare which category schemas they target and so ScrapedPayload can carry a structured spec block end-to-end. In `app/crawlers/adapters/base.py`, add `category_targets: ClassVar[list[str]] = []` to `RetailerCrawlerAdapter` (default empty list — adapters opt in by overriding). Validate the values at import time inside `__init_subclass__`: each entry must be a non-empty string and must resolve via `default_registry.resolve()` (lazy import inside the hook to avoid circular imports). If a slug is unknown, raise TypeError with the adapter qualname and the bad slug — this enforces the contract loudly during the S03 retrofit. In `app/crawlers/base.py`, extend `ScrapedPayload` with `specifications: Optional[Dict[str, Any]] = None` (matches `Part.specifications` JSON shape and `PartCreate.specifications`). Do NOT change any existing adapter — every concrete adapter's `category_targets` defaults to `[]` and continues to work. Do NOT auto-run universal extraction yet (that's S02). This task is purely the rails. Update the existing `tests/crawlers/test_adapter_discovery.py` ONLY if it asserts on the exact attribute set of the base class — otherwise leave it alone.

## Inputs

- ``backend/app/crawlers/adapters/base.py` — existing RetailerCrawlerAdapter with __init_subclass__ enforcement pattern (ADAPTER_NAME validation)`
- ``backend/app/crawlers/base.py` — existing ScrapedPayload @dataclass`
- ``backend/app/crawlers/specs/registry.py` — default_registry.resolve() (from T01) used to validate category_targets entries`

## Expected Output

- ``backend/app/crawlers/adapters/base.py` — adds `category_targets: ClassVar[list[str]] = []` plus per-entry validation inside `__init_subclass__``
- ``backend/app/crawlers/base.py` — adds `specifications: Optional[Dict[str, Any]] = None` to `ScrapedPayload``

## Verification

cd backend && pytest tests/crawlers/test_adapter_discovery.py -n auto && python -c "from app.crawlers.adapters.base import RetailerCrawlerAdapter; from app.crawlers.base import ScrapedPayload; assert RetailerCrawlerAdapter.category_targets == []; p = ScrapedPayload(name='x', product_url='https://example.com/p', specifications={'spring_rate_front': 600}); assert p.specifications == {'spring_rate_front': 600}; print('ok')"

## Steps

1. In `backend/app/crawlers/adapters/base.py`, add `category_targets: ClassVar[list[str]] = []` alongside the existing `ADAPTER_NAME` ClassVar.
2. Inside the existing `__init_subclass__`, after the existing `ADAPTER_NAME` validation, iterate `cls.category_targets`: each entry must be a non-empty string, and `default_registry.resolve(entry)` must return a model. On miss, raise `TypeError(f"{cls.__module__}.{cls.__qualname__} declares unknown category_targets entry {entry!r}; not registered in default_registry")`. Lazy-import `default_registry` inside the function body (`from app.crawlers.specs import default_registry`) to avoid circular imports — `specs/` does not import `adapters/`, so this is one-directional.
3. In `backend/app/crawlers/base.py`, extend `ScrapedPayload` with `specifications: Optional[Dict[str, Any]] = None`. Add `Dict` and `Any` to the typing imports if not present.
4. Run the verify commands. Confirm all 113 adapters still import via `pytest tests/crawlers/test_adapter_discovery.py -n auto`.

## Must-Haves

- [ ] `RetailerCrawlerAdapter.category_targets == []` at the base-class level.
- [ ] Defining a subclass with `category_targets = ['nonsense_slug']` raises `TypeError` at class-definition time.
- [ ] Defining a subclass with `category_targets = ['coilover']` (a registered slug) does NOT raise.
- [ ] `ScrapedPayload(name='x', product_url='y', specifications={'k': 1}).specifications == {'k': 1}`.
- [ ] `pytest tests/crawlers/test_adapter_discovery.py -n auto` is still green — no existing adapter regresses.

## Observability Impact

Failure mode added: import-time TypeError when an adapter declares an unknown category slug. This is intentional — silent typos in S03 retrofit would defeat the contract. The error message includes the adapter qualname and the bad slug so the source is immediate.
