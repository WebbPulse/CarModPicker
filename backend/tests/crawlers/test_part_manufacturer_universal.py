"""Unit tests for ``app.crawlers.parsing.part_manufacturer_universal``.

Pure-function tests with inline HTML strings as fixtures — no external files,
no DB, no network. Each test exercises one rung of the brand-precedence ladder
spec'd in S03 T02:

  1. JSON-LD ``Product.brand`` (str / dict.name / list[str | dict.name]) and
     ``Product.manufacturer`` same-block fallback.
  2. Microdata ``itemprop='brand'`` then ``itemprop='manufacturer'`` in all
     three element shapes (meta@content, nested itemprop=name, plain text).
  3. OpenGraph ``og:brand`` / ``product:brand`` / ``og:product:brand`` in
     order.
  4. ``part_manufacturer_from_title``.
  5. ``part_manufacturer_from_description``.
  6. ``part_manufacturer_fallback_from_title``.

Plus the defensive contract: oversized HTML short-circuits past steps 1–3,
corrupt JSON-LD/microdata degrade to None and never raise, and ``html=None``
falls straight through to the title/description ladder.

Mirror of the test shape from ``backend/tests/scripts/test_m004_ground_truth.py``
per the T02 plan.
"""

from __future__ import annotations

import logging

import pytest

from app.crawlers.parsing import (
    MANUFACTURER_HTML_SIZE_CAP_BYTES,
    part_manufacturer_universal,
)


# ---------------------------------------------------------------------------
# Layer 1: JSON-LD Product.brand
# ---------------------------------------------------------------------------


class TestJsonLdBrand:
    def test_brand_as_bare_string(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        assert (
            part_manufacturer_universal("E46 M3 Coilovers", None, html) == "Bilstein"
        )

    def test_brand_as_dict_name(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "brand": {"@type": "Brand", "name": "AC Schnitzer"}}
        </script>
        """
        assert (
            part_manufacturer_universal("E46 Wheels", None, html) == "AC Schnitzer"
        )

    def test_brand_as_list_of_strings(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": ["Bilstein", "OtherBrand"]}
        </script>
        """
        assert (
            part_manufacturer_universal("Coilovers", None, html) == "Bilstein"
        )

    def test_brand_as_list_of_dicts(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "brand": [{"@type": "Brand", "name": "Rogue Engineering"}]}
        </script>
        """
        assert (
            part_manufacturer_universal("Diff Bushings", None, html)
            == "Rogue Engineering"
        )

    def test_manufacturer_fallback_inside_jsonld(self) -> None:
        # No ``brand`` key, but ``manufacturer`` is present — should win over
        # microdata/OG which would otherwise fire downstream.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "manufacturer": {"@type": "Organization", "name": "VF-Engineering"}}
        </script>
        <meta property="og:brand" content="ShouldNotWin" />
        """
        assert (
            part_manufacturer_universal("VF Oil Cooler", None, html)
            == "VF-Engineering"
        )

    def test_empty_brand_falls_through(self) -> None:
        # Empty brand string + microdata fallback should land on the microdata
        # value, not the empty JSON-LD brand.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "   "}
        </script>
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">Rogue Engineering</span>
        </div>
        """
        assert (
            part_manufacturer_universal("Diff Bushings", None, html)
            == "Rogue Engineering"
        )


# ---------------------------------------------------------------------------
# Layer 2: Microdata itemprop=brand / itemprop=manufacturer
# ---------------------------------------------------------------------------


class TestMicrodata:
    def test_brand_plain_text(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">AC Schnitzer</span>
        </div>
        """
        assert (
            part_manufacturer_universal("E46 Wheels", None, html) == "AC Schnitzer"
        )

    def test_brand_meta_content(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <meta itemprop="brand" content="Bilstein" />
        </div>
        """
        assert part_manufacturer_universal("Coilovers", None, html) == "Bilstein"

    def test_brand_nested_name_itemprop(self) -> None:
        # Schema.org Brand: <span itemprop=brand><span itemprop=name>X</span></span>
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand" itemscope itemtype="https://schema.org/Brand">
            <span itemprop="name">VF-Engineering</span>
          </span>
        </div>
        """
        assert (
            part_manufacturer_universal("VF650 Supercharger", None, html)
            == "VF-Engineering"
        )

    def test_manufacturer_fallback_when_brand_missing(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <meta itemprop="manufacturer" content="Rogue Engineering" />
        </div>
        """
        assert (
            part_manufacturer_universal("Bushings", None, html)
            == "Rogue Engineering"
        )

    def test_empty_brand_falls_through_to_og(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand"></span>
        </div>
        <meta property="og:brand" content="Bilstein" />
        """
        assert part_manufacturer_universal("Coilovers", None, html) == "Bilstein"


# ---------------------------------------------------------------------------
# Layer 3: OpenGraph / product:* meta tags
# ---------------------------------------------------------------------------


class TestOpenGraph:
    def test_og_brand(self) -> None:
        html = '<head><meta property="og:brand" content="Bilstein" /></head>'
        assert part_manufacturer_universal("Coilovers", None, html) == "Bilstein"

    def test_product_brand(self) -> None:
        html = '<meta property="product:brand" content="Studio RSR" />'
        assert (
            part_manufacturer_universal("Roll Bar", None, html) == "Studio RSR"
        )

    def test_og_product_brand(self) -> None:
        html = '<meta property="og:product:brand" content="CSF" />'
        assert (
            part_manufacturer_universal("Radiator", None, html) == "CSF"
        )

    def test_og_brand_wins_over_product_brand(self) -> None:
        # _MANUFACTURER_OG_PROPS order: og:brand → product:brand → og:product:brand.
        html = """
        <meta property="og:brand" content="WinningBrand" />
        <meta property="product:brand" content="LosingBrand" />
        """
        assert (
            part_manufacturer_universal("Coilovers", None, html) == "WinningBrand"
        )

    def test_empty_og_content_falls_through(self) -> None:
        # Empty content should not be picked up — falls to title heuristic.
        html = '<meta property="og:brand" content="" />'
        # "AC Schnitzer Wheel" matches the two-word title heuristic.
        assert (
            part_manufacturer_universal(
                "AC Schnitzer Wheel For E46 M3", None, html
            )
            == "AC Schnitzer"
        )


# ---------------------------------------------------------------------------
# Layer 4: title heuristic
# ---------------------------------------------------------------------------


class TestTitleFallback:
    def test_two_word_brand(self) -> None:
        # No HTML signals — should land on part_manufacturer_from_title.
        assert (
            part_manufacturer_universal(
                "AC Schnitzer Type IV For E46 M3", None, None
            )
            == "AC Schnitzer"
        )

    def test_by_brand_pattern(self) -> None:
        assert (
            part_manufacturer_universal(
                "E46 M3 Coilovers by Bilstein", None, None
            )
            == "Bilstein"
        )

    def test_first_token_brand(self) -> None:
        # First non-chassis, non-part-code, non-generic token wins.
        assert (
            part_manufacturer_universal(
                "Bilstein B16 Damptronic Coilovers", None, None
            )
            == "Bilstein"
        )


# ---------------------------------------------------------------------------
# Layer 5: description heuristic
# ---------------------------------------------------------------------------


class TestDescriptionFallback:
    def test_studio_rsr_in_description(self) -> None:
        # Title is all generic words (intake, system, kit) so the title
        # heuristic returns None and we fall through to the description.
        out = part_manufacturer_universal(
            "Intake System Kit",
            "The Studio RSR roll bar bolts in to the OEM mount points.",
            None,
        )
        assert out == "Studio RSR"

    def test_csf_in_description(self) -> None:
        # All-generic title (radiator, kit) so we fall through.
        out = part_manufacturer_universal(
            "Radiator Kit",
            "CSF Radiators direct-fit replacement for the OEM unit.",
            None,
        )
        assert out == "CSF"


# ---------------------------------------------------------------------------
# Layer 6: fallback regex on title
# ---------------------------------------------------------------------------


class TestFallbackFromTitle:
    def test_vf_part_code_implies_vf_engineering(self) -> None:
        # part_manufacturer_from_title rejects "VF650" as a part-code token,
        # description is None, but the fallback regex picks VF up via "VF\d".
        # However, the title heuristic also handles "E9x M3 VF650 Supercharger"
        # via the VF-prefix-of-digits regex inside the FALLBACK helper, NOT
        # the from_title helper. We verify the universal function reaches the
        # fallback rung.
        out = part_manufacturer_universal(
            "E9x M3 VF650 Supercharger", None, None
        )
        assert out == "VF-Engineering"


# ---------------------------------------------------------------------------
# Defensive contract: never raises, oversized short-circuits, corrupt degrades
# ---------------------------------------------------------------------------


class TestOversizedHtml:
    def test_oversized_short_circuits_past_html_layers(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Embed a real JSON-LD brand at the start of an oversized payload.
        # If the cap weren't enforced, JSON-LD would win and return "ShouldNotWin".
        # Cap enforcement forces a fall-through to title heuristic instead.
        oversized_pad = "x" * (MANUFACTURER_HTML_SIZE_CAP_BYTES + 1)
        html = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "n", "brand": "ShouldNotWin"}'
            "</script>" + oversized_pad
        )
        with caplog.at_level(logging.DEBUG):
            out = part_manufacturer_universal(
                "Bilstein B16 Damptronic Coilovers", None, html
            )
        # Title heuristic ladder is what should have fired.
        assert out == "Bilstein"

    def test_just_under_cap_still_parses_jsonld(self) -> None:
        # Sanity check: a payload one byte under the cap should still parse.
        small_payload = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "n", "brand": "Bilstein"}'
            "</script>"
        )
        pad_size = MANUFACTURER_HTML_SIZE_CAP_BYTES - len(small_payload) - 50
        if pad_size > 0:
            small_payload = (
                small_payload + "<body>" + (" " * pad_size) + "</body>"
            )
        out = part_manufacturer_universal("X", None, small_payload)
        assert out == "Bilstein"


class TestCorruptInputs:
    def test_corrupt_jsonld_falls_through(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        html = """
        <script type="application/ld+json">{not valid json,,,}</script>
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">Rogue Engineering</span>
        </div>
        """
        with caplog.at_level(logging.DEBUG):
            out = part_manufacturer_universal("Bushings", None, html)
        # Microdata wins because JSON-LD parser silently bailed.
        assert out == "Rogue Engineering"

    def test_corrupt_microdata_falls_through_to_og(self) -> None:
        # Repeated unterminated <div itemprop=brand> open tags shouldn't crash.
        broken_microdata = '<div itemprop="brand">' * 50
        html = (
            broken_microdata
            + '<meta property="og:brand" content="Bilstein" />'
        )
        out = part_manufacturer_universal("Coilovers", None, html)
        # Microdata-shaped soup parses these as deeply nested empty divs;
        # value is empty, function falls through to OG.
        assert out == "Bilstein"

    @pytest.mark.parametrize(
        "broken",
        [
            "<<<>>>",
            '<script type="application/ld+json">null</script>',
            '<script type="application/ld+json">[]</script>',
            '<script type="application/ld+json">{"@type": "Product", "brand": null}</script>',
            '<script type="application/ld+json">{',  # truncated
        ],
    )
    def test_defensive_never_raises(
        self, broken: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            # Title is intentionally minimal so the fall-through ladder runs
            # all the way to the bottom without spuriously matching.
            result = part_manufacturer_universal("a", None, broken)
        # Just asserting we got here without an exception.
        assert result is None or isinstance(result, str)


class TestNoneHtml:
    def test_none_html_with_valid_title(self) -> None:
        # html=None must short-circuit to title/description/fallback.
        assert (
            part_manufacturer_universal(
                "Bilstein B16 Coilovers", None, None
            )
            == "Bilstein"
        )

    def test_none_html_with_none_description(self) -> None:
        # No HTML, no description, all-generic title (oil/cooler/kit) →
        # title/description/fallback all return None.
        assert part_manufacturer_universal("Oil Cooler Kit", None, None) is None

    def test_whitespace_html_treated_as_none(self) -> None:
        # Whitespace-only html should behave like None.
        assert (
            part_manufacturer_universal(
                "Bilstein B16 Coilovers", None, "   \n\t  "
            )
            == "Bilstein"
        )


# ---------------------------------------------------------------------------
# Logging contract: every successful resolution emits one debug line.
# ---------------------------------------------------------------------------


class TestLogging:
    def test_resolution_emits_structured_debug_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        with caplog.at_level(logging.DEBUG, logger="app.crawlers.parsing"):
            out = part_manufacturer_universal("Coilovers", None, html)
        assert out == "Bilstein"
        resolved = [
            r for r in caplog.records if r.message == "manufacturer_universal_resolved"
        ]
        assert resolved, (
            "expected a manufacturer_universal_resolved record, "
            f"got: {[r.message for r in caplog.records]}"
        )
        rec = resolved[0]
        assert getattr(rec, "source", None) == "jsonld_brand"
        assert getattr(rec, "value", None) == "Bilstein"
        assert getattr(rec, "adapter", None) == "none"

    def test_no_resolution_still_logs_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="app.crawlers.parsing"):
            out = part_manufacturer_universal("Oil Cooler Kit", None, None)
        assert out is None
        resolved = [
            r for r in caplog.records if r.message == "manufacturer_universal_resolved"
        ]
        assert resolved, "expected a terminal manufacturer_universal_resolved=none log"
        rec = resolved[-1]
        assert getattr(rec, "source", None) == "none"
        assert getattr(rec, "value", None) is None


# ---------------------------------------------------------------------------
# Adapter param is accepted but UNUSED in T02.
# ---------------------------------------------------------------------------


class TestAdapterParamUnused:
    def test_adapter_arg_is_accepted_and_does_not_change_output(self) -> None:
        # T03 wires adapters in; T02 just keeps the param in the signature.
        class _StubAdapter:
            name = "stub_adapter"

        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        with_adapter = part_manufacturer_universal(
            "X", None, html, adapter=_StubAdapter()  # type: ignore[arg-type]
        )
        without_adapter = part_manufacturer_universal("X", None, html)
        assert with_adapter == without_adapter == "Bilstein"

    def test_adapter_name_propagated_to_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _StubAdapter:
            name = "stub_adapter"

        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        with caplog.at_level(logging.DEBUG, logger="app.crawlers.parsing"):
            part_manufacturer_universal(
                "X", None, html, adapter=_StubAdapter()  # type: ignore[arg-type]
            )
        resolved = [
            r for r in caplog.records if r.message == "manufacturer_universal_resolved"
        ]
        assert resolved
        assert getattr(resolved[0], "adapter", None) == "stub_adapter"
