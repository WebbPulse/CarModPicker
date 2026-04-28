"""
Base-class hook tests for ``RetailerCrawlerAdapter.apply_universal_extraction``.

The hook is the call site that runs the five universal extractors over raw
HTML and merges the results into a payload's ``specifications`` dict. Three
contracts must hold (see ``MEM023`` and the S02 plan):

* **Auto-extraction** — fields the extractor finds land in
  ``payload.specifications`` along with their ``*_confidence`` companions.
* **Adapter wins** — when an adapter already filled a key in
  ``payload.specifications``, the hook leaves it untouched. This lets a
  hand-rolled, retailer-specific extraction beat the universal heuristic.
* **Per-field opt-out** — adapters can list field names in
  ``suppress_universal: ClassVar[list[str]]`` to skip them entirely; typos
  fail loudly at class-definition time so a silent miss can't ship.

Empty-HTML / no-extracted-fields paths must be no-ops, and ``__init_subclass__``
validation of ``suppress_universal`` against ``UNIVERSAL_FIELD_NAMES`` must
raise ``TypeError`` for unknown entries.

These adapters never touch the network — discover_product_urls is implemented
as ``return iter([])`` purely so the abstract methods are satisfied.
"""

from __future__ import annotations

import logging
from typing import ClassVar, Iterator, Optional

import pytest

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload

# ---------------------------------------------------------------------------
# Test adapter helpers
# ---------------------------------------------------------------------------


def _make_payload(
    name: str = "Test Part",
    specifications: Optional[dict] = None,
) -> ScrapedPayload:
    return ScrapedPayload(
        name=name,
        product_url="https://example.com/p",
        specifications=specifications,
    )


class _DefaultHookAdapter(RetailerCrawlerAdapter):
    """Adapter that runs all five universal extractors with no suppression."""

    ADAPTER_NAME: ClassVar[str] = "_default_hook_adapter_t05"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return _make_payload()


class _SuppressWeightAdapter(RetailerCrawlerAdapter):
    """Adapter that opts out of the weight_grams universal extractor."""

    ADAPTER_NAME: ClassVar[str] = "_suppress_weight_adapter_t05"
    suppress_universal: ClassVar[list[str]] = ["weight_grams"]

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return _make_payload()


class _AdapterWinsAdapter(RetailerCrawlerAdapter):
    """
    Adapter that pre-populates ``weight_grams`` to verify the merge contract:
    the hook must leave adapter-set values alone.
    """

    ADAPTER_NAME: ClassVar[str] = "_adapter_wins_adapter_t05"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return _make_payload()


class _SuppressMpnAdapter(RetailerCrawlerAdapter):
    """Adapter that opts out of the manufacturer_part_number universal extractor (M004/S06 T03)."""

    ADAPTER_NAME: ClassVar[str] = "_suppress_mpn_adapter_t03"
    suppress_universal: ClassVar[list[str]] = ["manufacturer_part_number"]

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return _make_payload()


# ---------------------------------------------------------------------------
# (a) Default auto-extraction
# ---------------------------------------------------------------------------


class TestApplyUniversalExtractionAutoExtracts:
    def test_labeled_weight_lands_in_specifications(self) -> None:
        adapter = _DefaultHookAdapter()
        # 25 lb → 25 * 453.59237 ≈ 11339.81 g.
        html = "<html><body><div>Weight: 25 lb</div></body></html>"
        payload = _make_payload()

        result = adapter.apply_universal_extraction(html, payload)

        assert result is payload, (
            "Hook must always return the same payload instance — call sites "
            "rely on reflexive `payload = adapter.apply_universal_extraction(...)`."
        )
        assert result.specifications is not None
        assert "weight_grams" in result.specifications
        assert result.specifications["weight_grams"] == pytest.approx(25 * 453.59237)
        assert result.specifications["weight_grams_confidence"] == "medium"

    def test_debug_log_emitted_per_extracted_field(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Locks in the slice plan's observability contract: a DEBUG line per
        successfully merged universal field, including the adapter name and
        confidence. S04 needs this trace to grep archive reruns and tune
        confidence thresholds in S03.
        """
        adapter = _DefaultHookAdapter()
        html = "<html><body><div>Weight: 25 lb</div><div>Material: Aluminum</div></body></html>"
        payload = _make_payload()

        with caplog.at_level(logging.DEBUG, logger="app.crawlers.adapters.base"):
            adapter.apply_universal_extraction(html, payload)

        debug_messages = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.DEBUG and "universal_extraction" in r.getMessage()
        ]
        assert any(
            "weight_grams" in m and adapter.ADAPTER_NAME in m for m in debug_messages
        ), f"Expected DEBUG with adapter+weight_grams, got: {debug_messages!r}"


# ---------------------------------------------------------------------------
# (b) Per-field suppression
# ---------------------------------------------------------------------------


class TestApplyUniversalExtractionSuppression:
    def test_suppressed_field_is_absent_from_specifications(self) -> None:
        adapter = _SuppressWeightAdapter()
        html = "<html><body><div>Weight: 25 lb</div><div>Material: Aluminum</div></body></html>"
        payload = _make_payload()

        result = adapter.apply_universal_extraction(html, payload)

        # Non-suppressed fields still merge.
        assert result.specifications is not None
        assert result.specifications.get("material") == "aluminum"
        # Weight is suppressed entirely — neither value nor confidence companion.
        assert "weight_grams" not in result.specifications
        assert "weight_grams_confidence" not in result.specifications

    def test_suppress_mpn_drops_manufacturer_part_number(self) -> None:
        # M004/S06 T03: suppress_universal=['manufacturer_part_number'] must
        # drop the field even when the body cleanly carries an MPN row.
        adapter = _SuppressMpnAdapter()
        html = "<html><body><div>MPN: KW-12345</div><div>Material: Aluminum</div></body></html>"
        payload = _make_payload()

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications is not None
        # Non-suppressed fields still merge.
        assert result.specifications.get("material") == "aluminum"
        # MPN is suppressed entirely — neither value nor confidence companion.
        assert "manufacturer_part_number" not in result.specifications
        assert "manufacturer_part_number_confidence" not in result.specifications


# ---------------------------------------------------------------------------
# (c) Adapter-wins merge
# ---------------------------------------------------------------------------


class TestApplyUniversalExtractionAdapterWins:
    def test_adapter_set_value_is_preserved(self) -> None:
        """
        The hook is an adapter-wins merge: when an adapter already wrote a
        value for a universal key, the universal extractor's value must NOT
        overwrite it. This is the contract that lets a retailer-specific
        extraction beat the heuristic for fields the adapter cares about.
        """
        adapter = _AdapterWinsAdapter()
        # Adapter pre-set weight_grams = 999.0 with high confidence.
        adapter_specs = {
            "weight_grams": 999.0,
            "weight_grams_confidence": "high",
        }
        # HTML disagrees: contains "Weight: 25 lb" → ~11339.81 g.
        html = "<html><body><div>Weight: 25 lb</div></body></html>"
        payload = _make_payload(specifications=adapter_specs)

        result = adapter.apply_universal_extraction(html, payload)

        # Adapter's value survives.
        assert result.specifications is not None
        assert result.specifications["weight_grams"] == 999.0
        assert result.specifications["weight_grams_confidence"] == "high"

    def test_unset_universal_fields_still_fill_in(self) -> None:
        """
        Adapter wins only on keys it actually set. Other universal fields
        the adapter didn't touch must still come through.
        """
        adapter = _AdapterWinsAdapter()
        adapter_specs = {"weight_grams": 999.0}  # only weight is adapter-set
        html = "<html><body><div>Weight: 25 lb</div><div>Material: Aluminum</div>" "</body></html>"
        payload = _make_payload(specifications=adapter_specs)

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications is not None
        # Adapter-set field preserved.
        assert result.specifications["weight_grams"] == 999.0
        # Unset universal field merged.
        assert result.specifications["material"] == "aluminum"
        assert result.specifications["material_confidence"] == "medium"

    def test_manufacturer_part_number_fills_when_adapter_did_not_set_it(self) -> None:
        """
        M004/S06 T03: the hook must auto-fill ``manufacturer_part_number`` from
        a labeled body row when the adapter pre-populated other keys but left
        MPN unset, AND must preserve the adapter-set value if it did.
        """
        adapter = _AdapterWinsAdapter()
        adapter_specs = {"weight_grams": 999.0}  # MPN intentionally unset
        html = "<html><body><div>MPN: kw-12345-xyz</div></body></html>"
        payload = _make_payload(specifications=adapter_specs)

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications is not None
        # Adapter-set field preserved.
        assert result.specifications["weight_grams"] == 999.0
        # MPN filled by extractor at medium confidence (labeled body row).
        # Validator canonicalizes to upper-case + whitespace-collapsed.
        assert result.specifications["manufacturer_part_number"] == "KW-12345-XYZ"
        assert result.specifications["manufacturer_part_number_confidence"] == "medium"

    def test_adapter_set_manufacturer_part_number_is_preserved(self) -> None:
        """
        Mirror of the weight_grams adapter-wins case for the new universal
        field: when the adapter pre-set the MPN, the universal extractor must
        not overwrite it.
        """
        adapter = _AdapterWinsAdapter()
        adapter_specs = {
            "manufacturer_part_number": "ADAPTER-WIN-1",
            "manufacturer_part_number_confidence": "high",
        }
        html = "<html><body><div>MPN: should-not-overwrite-1</div></body></html>"
        payload = _make_payload(specifications=adapter_specs)

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications is not None
        assert result.specifications["manufacturer_part_number"] == "ADAPTER-WIN-1"
        assert result.specifications["manufacturer_part_number_confidence"] == "high"


# ---------------------------------------------------------------------------
# (d) Empty-HTML / no-extraction safety
# ---------------------------------------------------------------------------


class TestApplyUniversalExtractionEmptyInputs:
    def test_empty_html_leaves_payload_unchanged(self) -> None:
        adapter = _DefaultHookAdapter()
        payload = _make_payload(specifications={"weight_grams": 500.0})

        result = adapter.apply_universal_extraction("", payload)

        assert result is payload
        assert result.specifications == {"weight_grams": 500.0}

    def test_html_without_universal_signals_leaves_payload_unchanged(self) -> None:
        adapter = _DefaultHookAdapter()
        payload = _make_payload(specifications={"existing_key": "x"})
        html = "<html><body><p>Pure marketing copy with no signals.</p></body></html>"

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications == {"existing_key": "x"}

    def test_payload_none_is_a_noop(self) -> None:
        adapter = _DefaultHookAdapter()
        # Hook docstring promises this short-circuits.
        result = adapter.apply_universal_extraction("<html><body><div>Weight: 25 lb</div></body></html>", None)
        assert result is None

    def test_null_specifications_become_dict_when_extraction_fires(self) -> None:
        adapter = _DefaultHookAdapter()
        payload = _make_payload(specifications=None)
        html = "<html><body><div>Weight: 25 lb</div></body></html>"

        result = adapter.apply_universal_extraction(html, payload)

        assert result.specifications is not None
        assert "weight_grams" in result.specifications


# ---------------------------------------------------------------------------
# (e) suppress_universal validation gate at class-definition time
# ---------------------------------------------------------------------------


class TestSuppressUniversalValidationGate:
    def test_unknown_field_in_suppress_universal_raises_at_class_creation(
        self,
    ) -> None:
        with pytest.raises(TypeError, match="suppress_universal"):

            class _BadAdapter(RetailerCrawlerAdapter):  # noqa: N801 — local fixture
                ADAPTER_NAME: ClassVar[str] = "_bad_adapter_t05"
                suppress_universal: ClassVar[list[str]] = ["not_a_real_field"]

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
                    return None

    def test_suppress_universal_rejects_non_string_entry(self) -> None:
        with pytest.raises(TypeError):

            class _BadTypesAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_bad_types_adapter_t05"
                suppress_universal: ClassVar[list] = [123]  # type: ignore[list-item]

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
                    return None

    def test_suppress_universal_rejects_non_list_value(self) -> None:
        with pytest.raises(TypeError, match="suppress_universal"):

            class _BadShapeAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_bad_shape_adapter_t05"
                # Wrong type — not list/tuple. Use Any so type-checkers don't reject
                # the deliberately invalid annotation.
                suppress_universal = "weight_grams"  # type: ignore[assignment]

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
                    return None
