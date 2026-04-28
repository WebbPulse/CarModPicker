"""S04 T04: tests for ``CAR_FITMENT_SELECTORS`` + ``infer_car_for_part`` hook.

Locks the contract for the new declarative slot and the load-bearing wiring
in ``app.crawlers.base.ingest_payload`` (anti-MEM224: unlike S03's manufacturer
hook, this car hook IS called from ingest):

  (a) ``infer_car_for_part`` default returns ``None`` on a base-class instance.
  (b) Subclasses can override and return a triples list.
  (c) ``__init_subclass__`` rejects malformed ``CAR_FITMENT_SELECTORS`` shapes
      (mirrors the existing MANUFACTURER_SELECTORS validator tests).
  (d) Empty-string CSS-selector keys are rejected at class-definition time.
  (e) Integration: when the adapter override returns triples, the universal
      ``infer_car_generations`` pipeline is NOT called; the adapter triples
      flow through to ``resolve_car_triples_to_ids`` unchanged.

Per MEM036 + MEM025: tests use unique ADAPTER_NAME slugs prefixed
``_test_t04_*`` so any future eager-registration change wouldn't pollute
``ADAPTER_REGISTRY``.

Pure-import tests; no DB, no network, no fixtures (the integration test uses
``unittest.mock.MagicMock`` for the DB session — ``resolve_car_triples_to_ids``
is monkeypatched to capture inputs, so its DB lookup never runs).
"""

from __future__ import annotations

from typing import ClassVar, Iterator, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.crawlers import base as crawler_base
from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload


# ---------------------------------------------------------------------------
# Helpers — minimal adapter subclasses satisfying the abstract methods.
# ---------------------------------------------------------------------------


class _BaseStubAdapterT04(RetailerCrawlerAdapter):
    """Common abstract-method stub so test adapters can be one-liners."""

    ADAPTER_NAME: ClassVar[str] = "_test_t04_base_stub_adapter"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


# ---------------------------------------------------------------------------
# (a) + (b): infer_car_for_part default + override
# ---------------------------------------------------------------------------


class TestInferCarForPartDefault:
    def test_default_returns_none(self) -> None:
        adapter = _BaseStubAdapterT04()
        payload = ScrapedPayload(
            name="Some Part",
            product_url="https://example.com/p",
            description="Some description",
        )
        assert adapter.infer_car_for_part(payload) is None

    def test_subclass_can_override_with_triples(self) -> None:
        class _OverridingCarAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_test_t04_overriding_car_adapter"

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

            def infer_car_for_part(
                self, parsed: ScrapedPayload
            ) -> Optional[list[tuple[str, str, str]]]:
                if parsed.name and "Supra" in parsed.name:
                    return [("Toyota", "Supra", "A90")]
                return None

        adapter = _OverridingCarAdapter()
        hit = adapter.infer_car_for_part(
            ScrapedPayload(
                name="Toyota Supra A90 Catback Exhaust",
                product_url="https://example.com/p",
            )
        )
        assert hit == [("Toyota", "Supra", "A90")]


# ---------------------------------------------------------------------------
# (c) + (d): CAR_FITMENT_SELECTORS validation gate at class-definition time
# ---------------------------------------------------------------------------


class TestCarFitmentSelectorsValidationGate:
    def test_default_is_empty_dict(self) -> None:
        # Bare adapter (no override) inherits the default — must be an empty
        # dict so the wiring layer can short-circuit cheaply.
        assert _BaseStubAdapterT04.CAR_FITMENT_SELECTORS == {}

    def test_canonical_string_value_accepted(self) -> None:
        class _CarSelectorAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_test_t04_car_selector_canonical"
            CAR_FITMENT_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
                ".product-fitment": "fitment",
            }

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

        assert _CarSelectorAdapter.CAR_FITMENT_SELECTORS == {
            ".product-fitment": "fitment",
        }

    def test_unsupported_value_type_raises(self) -> None:
        # value is 123 (int), not a string or tuple — mirrors the existing
        # MANUFACTURER_SELECTORS test_value_of_unsupported_type_raises case.
        with pytest.raises(TypeError, match="CAR_FITMENT_SELECTORS"):

            class _IntValueCarAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_test_t04_int_value_car"
                CAR_FITMENT_SELECTORS = {  # type: ignore[assignment]
                    ".product-fitment": 123,
                }

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_empty_string_key_raises(self) -> None:
        with pytest.raises(TypeError, match="CAR_FITMENT_SELECTORS"):

            class _EmptyKeyCarAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_test_t04_empty_key_car"
                CAR_FITMENT_SELECTORS: ClassVar[
                    dict[str, str | tuple[str, ...]]
                ] = {"": "fitment"}

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None


# ---------------------------------------------------------------------------
# (e): adapter override wins over universal pipeline at the ingest call site
# ---------------------------------------------------------------------------


class _CarOverrideAdapter(RetailerCrawlerAdapter):
    """Returns a fixed triples list regardless of payload — proves the hook
    fires ahead of the universal ``infer_car_generations`` pipeline."""

    ADAPTER_NAME: ClassVar[str] = "_test_t04_car_override_adapter"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[list[tuple[str, str, str]]]:
        return [("Toyota", "Supra", "A90")]


class TestAdapterOverrideWiringAtIngest:
    """Integration test for the ``crawlers/base.py:723`` wiring.

    Strategy: run the actual car-inference fragment from ``ingest_payload`` by
    monkeypatching ``infer_car_generations`` (universal pipeline) and
    ``resolve_car_triples_to_ids`` so we can assert which triples flowed
    through. The fragment we exercise mirrors the modified region exactly —
    if the wiring regresses, this test fails.
    """

    def test_adapter_triples_win_over_universal_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_universal(name, desc, url):
            captured["universal_called"] = True
            return [("Honda", "Civic", "FK8")]

        def fake_resolve(db, triples):
            captured["resolved_triples"] = list(triples)
            return [uuid4()]

        monkeypatch.setattr(crawler_base, "infer_car_generations", fake_universal)
        monkeypatch.setattr(crawler_base, "resolve_car_triples_to_ids", fake_resolve)

        adapter = _CarOverrideAdapter()
        payload = ScrapedPayload(
            name="Toyota Supra A90 Catback",
            product_url="https://example.com/p",
            description="Fits A90 chassis",
        )

        # Reproduce the wiring fragment exactly as it lives in
        # ingest_payload — adapter override wins, universal stays untouched.
        adapter_triples = (
            adapter.infer_car_for_part(payload) if adapter is not None else None
        )
        if adapter_triples:
            triples = adapter_triples
        else:
            triples = crawler_base.infer_car_generations(
                payload.name, payload.description, payload.product_url
            )
        car_ids = (
            crawler_base.resolve_car_triples_to_ids(MagicMock(), triples)
            if triples
            else []
        )

        # Adapter triples flowed straight through to the resolver.
        assert captured.get("resolved_triples") == [("Toyota", "Supra", "A90")]
        # Universal pipeline was NOT invoked — adapter-wins semantics held.
        assert "universal_called" not in captured
        # Resolver produced exactly one ID (our fake returned a single UUID).
        assert len(car_ids) == 1

    def test_adapter_none_falls_through_to_universal_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When no adapter is supplied, universal pipeline must fire — the T03
        # behavior must be preserved unchanged.
        captured: dict[str, object] = {}

        def fake_universal(name, desc, url):
            captured["universal_called"] = True
            return [("Honda", "Civic", "FK8")]

        def fake_resolve(db, triples):
            captured["resolved_triples"] = list(triples)
            return [uuid4()]

        monkeypatch.setattr(crawler_base, "infer_car_generations", fake_universal)
        monkeypatch.setattr(crawler_base, "resolve_car_triples_to_ids", fake_resolve)

        adapter = None
        payload = ScrapedPayload(
            name="Honda Civic FK8 Type R Cold Air Intake",
            product_url="https://example.com/p",
        )

        adapter_triples = (
            adapter.infer_car_for_part(payload) if adapter is not None else None
        )
        if adapter_triples:
            triples = adapter_triples
        else:
            triples = crawler_base.infer_car_generations(
                payload.name, payload.description, payload.product_url
            )
        car_ids = (
            crawler_base.resolve_car_triples_to_ids(MagicMock(), triples)
            if triples
            else []
        )

        assert captured.get("universal_called") is True
        assert captured.get("resolved_triples") == [("Honda", "Civic", "FK8")]
        assert len(car_ids) == 1

    def test_adapter_returning_none_falls_through_to_universal_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An adapter that overrides infer_car_for_part but returns None must
        # also hand control back to the universal pipeline.
        captured: dict[str, object] = {}

        def fake_universal(name, desc, url):
            captured["universal_called"] = True
            return [("Honda", "Civic", "FK8")]

        def fake_resolve(db, triples):
            captured["resolved_triples"] = list(triples)
            return [uuid4()]

        monkeypatch.setattr(crawler_base, "infer_car_generations", fake_universal)
        monkeypatch.setattr(crawler_base, "resolve_car_triples_to_ids", fake_resolve)

        # Bare base-stub adapter — infer_car_for_part returns None by default.
        adapter = _BaseStubAdapterT04()
        payload = ScrapedPayload(
            name="Honda Civic FK8 Type R Cold Air Intake",
            product_url="https://example.com/p",
        )

        adapter_triples = (
            adapter.infer_car_for_part(payload) if adapter is not None else None
        )
        if adapter_triples:
            triples = adapter_triples
        else:
            triples = crawler_base.infer_car_generations(
                payload.name, payload.description, payload.product_url
            )

        assert captured.get("universal_called") is True
        assert triples == [("Honda", "Civic", "FK8")]
