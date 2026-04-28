"""S03 T03: tests for ``MANUFACTURER_SELECTORS`` + ``infer_manufacturer_for_part``.

Locks the contract for the two declared override mechanisms on
``RetailerCrawlerAdapter`` plus their wiring into
``app.crawlers.parsing.part_manufacturer_universal``:

  (a) ``__init_subclass__`` validation accepts valid ``MANUFACTURER_SELECTORS``
      shapes — empty default, canonical-string mappings, tuple mappings.
  (b) ``__init_subclass__`` validation rejects malformed shapes — non-dict,
      non-string keys, empty keys, non-string/non-tuple values, empty-string
      values, empty tuples, tuples with non-string entries.
  (c) ``infer_manufacturer_for_part`` default returns ``None``.
  (d) ``part_manufacturer_universal`` consults
      ``adapter.MANUFACTURER_SELECTORS`` ahead of JSON-LD when both would
      resolve.
  (e) Reject-token coercion works — selector hits ``"BMW"`` (a shared
      ``_CAR_MAKES`` entry) coerce to the declared canonical, and
      tuple-supplied extra rejects supplement the shared set.
  (f) ``adapter is None`` exercises the T02 path identically — no regression.

Pure-import / inline-HTML tests; no DB, no network, no fixtures.
"""

from __future__ import annotations

import logging
from typing import ClassVar, Iterator, Optional

import pytest

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import part_manufacturer_universal


# ---------------------------------------------------------------------------
# Helpers — minimal adapter subclasses satisfying the abstract methods.
# ---------------------------------------------------------------------------


class _BaseStubAdapter(RetailerCrawlerAdapter):
    """Common abstract-method stub so test adapters can be one-liners."""

    ADAPTER_NAME: ClassVar[str] = "_base_stub_adapter_s03_t03"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


# ---------------------------------------------------------------------------
# (a) MANUFACTURER_SELECTORS default + valid shapes
# ---------------------------------------------------------------------------


class TestManufacturerSelectorsValidShapes:
    def test_default_is_empty_dict(self) -> None:
        # Bare adapter (no override) inherits the default — must be an empty
        # dict so ``part_manufacturer_universal`` short-circuits adapter
        # consultation cheaply.
        assert _BaseStubAdapter.MANUFACTURER_SELECTORS == {}

    def test_canonical_string_value_accepted(self) -> None:
        class _CanonicalAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_canonical_adapter_s03_t03"
            MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
                ".product-brand": "CSF",
            }

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

        assert _CanonicalAdapter.MANUFACTURER_SELECTORS == {".product-brand": "CSF"}

    def test_tuple_value_accepted(self) -> None:
        class _TupleAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_tuple_adapter_s03_t03"
            MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
                "meta[name=brand]": ("CSF", "wheels", "exhaust"),
            }

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

        assert _TupleAdapter.MANUFACTURER_SELECTORS == {
            "meta[name=brand]": ("CSF", "wheels", "exhaust"),
        }

    def test_single_entry_tuple_accepted(self) -> None:
        class _SingleEntryTupleAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_single_entry_tuple_s03_t03"
            MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
                ".brand": ("GrimmSpeed",),
            }

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

        assert _SingleEntryTupleAdapter.MANUFACTURER_SELECTORS == {
            ".brand": ("GrimmSpeed",),
        }


# ---------------------------------------------------------------------------
# (b) MANUFACTURER_SELECTORS validation gate at class-definition time
# ---------------------------------------------------------------------------


class TestManufacturerSelectorsValidationGate:
    def test_non_dict_value_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _NotADictAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_not_a_dict_s03_t03"
                MANUFACTURER_SELECTORS = ["not", "a", "dict"]  # type: ignore[assignment]

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_non_string_key_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _NonStringKeyAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_non_str_key_s03_t03"
                MANUFACTURER_SELECTORS = {  # type: ignore[assignment]
                    123: "CSF",
                }

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_empty_string_key_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _EmptyKeyAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_empty_key_s03_t03"
                MANUFACTURER_SELECTORS: ClassVar[
                    dict[str, str | tuple[str, ...]]
                ] = {"": "CSF"}

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_empty_string_value_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _EmptyValueAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_empty_value_s03_t03"
                MANUFACTURER_SELECTORS: ClassVar[
                    dict[str, str | tuple[str, ...]]
                ] = {".brand": ""}

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_empty_tuple_value_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _EmptyTupleAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_empty_tuple_s03_t03"
                MANUFACTURER_SELECTORS: ClassVar[
                    dict[str, str | tuple[str, ...]]
                ] = {".brand": ()}

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_tuple_with_non_string_entry_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _TupleNonStrAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_tuple_non_str_s03_t03"
                MANUFACTURER_SELECTORS = {  # type: ignore[assignment]
                    ".brand": ("CSF", 123),
                }

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_tuple_with_empty_string_entry_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _TupleEmptyStrAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_tuple_empty_str_s03_t03"
                MANUFACTURER_SELECTORS: ClassVar[
                    dict[str, str | tuple[str, ...]]
                ] = {".brand": ("CSF", "")}

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None

    def test_value_of_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError, match="MANUFACTURER_SELECTORS"):

            class _IntValueAdapter(RetailerCrawlerAdapter):  # noqa: N801
                ADAPTER_NAME: ClassVar[str] = "_int_value_s03_t03"
                MANUFACTURER_SELECTORS = {  # type: ignore[assignment]
                    ".brand": 123,
                }

                def discover_product_urls(self) -> Iterator[str]:
                    return iter([])

                def parse_product_page(
                    self, html: str, url: str
                ) -> Optional[ScrapedPayload]:
                    return None


# ---------------------------------------------------------------------------
# (c) infer_manufacturer_for_part default
# ---------------------------------------------------------------------------


class TestInferManufacturerDefault:
    def test_default_returns_none(self) -> None:
        adapter = _BaseStubAdapter()
        payload = ScrapedPayload(
            name="Some Part",
            product_url="https://example.com/p",
            description="Some description",
        )
        assert adapter.infer_manufacturer_for_part(payload) is None

    def test_subclass_can_override(self) -> None:
        class _OverridingAdapter(RetailerCrawlerAdapter):
            ADAPTER_NAME: ClassVar[str] = "_overriding_s03_t03"

            def discover_product_urls(self) -> Iterator[str]:
                return iter([])

            def parse_product_page(
                self, html: str, url: str
            ) -> Optional[ScrapedPayload]:
                return None

            def infer_manufacturer_for_part(
                self, parsed: ScrapedPayload
            ) -> Optional[str]:
                if parsed.name and "VF" in parsed.name:
                    return "VF-Engineering"
                return None

        adapter = _OverridingAdapter()
        hit = adapter.infer_manufacturer_for_part(
            ScrapedPayload(
                name="VF650 Supercharger",
                product_url="https://example.com/p",
            )
        )
        assert hit == "VF-Engineering"


# ---------------------------------------------------------------------------
# (d) Adapter selectors run AHEAD of JSON-LD when both would resolve
# ---------------------------------------------------------------------------


class _CsfClassSelectorAdapter(RetailerCrawlerAdapter):
    """Selector hits the visible product page brand class with canonical CSF."""

    ADAPTER_NAME: ClassVar[str] = "_csf_class_selector_s03_t03"
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        ".product-brand": "CSF",
    }

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class _MetaBrandAdapter(RetailerCrawlerAdapter):
    """Selector hits a meta tag with content extraction."""

    ADAPTER_NAME: ClassVar[str] = "_meta_brand_adapter_s03_t03"
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        "meta[name=brand]": "GrimmSpeed",
    }

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class TestAdapterSelectorsRunAheadOfJsonLd:
    def test_selector_wins_over_jsonld(self) -> None:
        # JSON-LD says "WrongBrand" — adapter's class selector picks the
        # canonical "CSF" from the visible product brand div, which is what
        # the retailer-specific override is for.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "WrongBrand"}
        </script>
        <div class="product-brand">CSF Radiators</div>
        """
        adapter = _CsfClassSelectorAdapter()
        # Resolved string is "CSF Radiators" — not in shared rejects, not a
        # car make. Pass-through: no coercion needed.
        out = part_manufacturer_universal(
            "BMW E46 Oil Cooler", None, html, adapter=adapter
        )
        assert out == "CSF Radiators"

    def test_meta_selector_extracts_content_attr(self) -> None:
        html = """
        <head>
          <meta name="brand" content="GrimmSpeed" />
        </head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Subaru"}
        </script>
        """
        adapter = _MetaBrandAdapter()
        out = part_manufacturer_universal(
            "WRX STI Short Shifter", None, html, adapter=adapter
        )
        assert out == "GrimmSpeed"

    def test_selector_emits_adapter_selectors_log_source(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        html = '<div class="product-brand">CSF Radiators</div>'
        adapter = _CsfClassSelectorAdapter()
        with caplog.at_level(logging.DEBUG, logger="app.crawlers.parsing"):
            out = part_manufacturer_universal(
                "BMW E46 Oil Cooler", None, html, adapter=adapter
            )
        assert out == "CSF Radiators"
        resolved = [
            r
            for r in caplog.records
            if r.message == "manufacturer_universal_resolved"
        ]
        assert resolved
        assert getattr(resolved[0], "source", None) == "adapter_selectors"
        assert getattr(resolved[0], "value", None) == "CSF Radiators"

    def test_missing_selector_falls_through_to_jsonld(self) -> None:
        # The adapter declares a selector, but the HTML doesn't contain it.
        # JSON-LD must fire because the adapter layer yielded nothing.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        adapter = _CsfClassSelectorAdapter()
        out = part_manufacturer_universal(
            "Coilovers", None, html, adapter=adapter
        )
        assert out == "Bilstein"


# ---------------------------------------------------------------------------
# (e) Reject-token coercion: shared _CAR_MAKES + tuple-supplied extras.
# ---------------------------------------------------------------------------


class _CsfCanonicalAdapter(RetailerCrawlerAdapter):
    """Title sometimes leads with the target vehicle ('BMW') — coerce to canonical."""

    ADAPTER_NAME: ClassVar[str] = "_csf_canonical_s03_t03"
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        ".product-brand": "CSF",
    }

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class _CsfTupleRejectsAdapter(RetailerCrawlerAdapter):
    """Tuple form supplements the shared reject set with retailer-specific extras."""

    ADAPTER_NAME: ClassVar[str] = "_csf_tuple_rejects_s03_t03"
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        ".product-brand": ("CSF", "Wheels", "Exhaust"),
    }

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class TestSelectorRejectCoercion:
    def test_shared_car_make_coerces_to_canonical(self) -> None:
        # ".product-brand" hits "BMW" — a shared _CAR_MAKES entry. The
        # universal pipeline must coerce to the declared canonical "CSF"
        # rather than passing "BMW" through as the manufacturer.
        html = '<div class="product-brand">BMW</div>'
        adapter = _CsfCanonicalAdapter()
        out = part_manufacturer_universal(
            "BMW E46 Oil Cooler", None, html, adapter=adapter
        )
        assert out == "CSF"

    def test_shared_reject_token_coerces_to_canonical(self) -> None:
        # "Race" is in the shared _BRAND_REJECT_TOKENS set.
        html = '<div class="product-brand">Race</div>'
        adapter = _CsfCanonicalAdapter()
        out = part_manufacturer_universal(
            "BMW E46 Oil Cooler", None, html, adapter=adapter
        )
        assert out == "CSF"

    def test_tuple_extra_reject_supplements_shared_set(self) -> None:
        # "Wheels" isn't in the shared set, but the tuple supplies it as a
        # retailer-specific reject. Must coerce to canonical "CSF".
        html = '<div class="product-brand">Wheels</div>'
        adapter = _CsfTupleRejectsAdapter()
        out = part_manufacturer_universal(
            "BMW E46 Wheels Set", None, html, adapter=adapter
        )
        assert out == "CSF"

    def test_non_reject_value_passes_through(self) -> None:
        # A value that isn't in the reject set passes through unchanged —
        # the canonical mapping does NOT replace non-rejected values.
        html = '<div class="product-brand">Studio RSR</div>'
        adapter = _CsfCanonicalAdapter()
        out = part_manufacturer_universal(
            "Some Part", None, html, adapter=adapter
        )
        assert out == "Studio RSR"

    def test_reject_match_is_case_insensitive(self) -> None:
        # "bmw" lowercase should match the shared _CAR_MAKES set the same
        # way "BMW" does.
        html = '<div class="product-brand">bmw</div>'
        adapter = _CsfCanonicalAdapter()
        out = part_manufacturer_universal(
            "BMW E46 Oil Cooler", None, html, adapter=adapter
        )
        assert out == "CSF"


# ---------------------------------------------------------------------------
# (f) adapter=None regression — universal pipeline behaves identically to T02.
# ---------------------------------------------------------------------------


class TestAdapterNoneRegression:
    def test_jsonld_brand_still_wins_when_adapter_none(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        # No adapter — the new T03 code path must short-circuit cleanly and
        # leave the JSON-LD layer to win exactly as in T02.
        assert part_manufacturer_universal("Coilovers", None, html) == "Bilstein"

    def test_microdata_still_wins_when_adapter_none(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">AC Schnitzer</span>
        </div>
        """
        assert (
            part_manufacturer_universal("E46 Wheels", None, html) == "AC Schnitzer"
        )

    def test_title_fallback_still_fires_when_adapter_none(self) -> None:
        # No HTML, no description — title heuristic must still fire.
        assert (
            part_manufacturer_universal("Bilstein B16 Coilovers", None, None)
            == "Bilstein"
        )

    def test_adapter_with_empty_selectors_behaves_like_none(self) -> None:
        # Adapter is non-None but declares no MANUFACTURER_SELECTORS — must
        # produce the same result as adapter=None for the same HTML.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        adapter = _BaseStubAdapter()
        with_adapter = part_manufacturer_universal(
            "Coilovers", None, html, adapter=adapter
        )
        without_adapter = part_manufacturer_universal("Coilovers", None, html)
        assert with_adapter == without_adapter == "Bilstein"


# ---------------------------------------------------------------------------
# Defensive: malformed selectors / parser failures degrade silently.
# ---------------------------------------------------------------------------


class _MalformedSelectorAdapter(RetailerCrawlerAdapter):
    """Selector string that BeautifulSoup will refuse to parse."""

    ADAPTER_NAME: ClassVar[str] = "_malformed_selector_s03_t03"
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        # "::invalid::" is not a valid CSS pseudo-element; soupsieve raises.
        "::invalid::": "CSF",
    }

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class TestSelectorDefensiveContract:
    def test_malformed_selector_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # When the only declared selector is invalid, the adapter layer
        # contributes nothing and the function falls through to JSON-LD.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        adapter = _MalformedSelectorAdapter()
        with caplog.at_level(logging.DEBUG, logger="app.crawlers.parsing"):
            out = part_manufacturer_universal(
                "Coilovers", None, html, adapter=adapter
            )
        # Fall-through to JSON-LD must succeed even when the selector blows up.
        assert out == "Bilstein"
