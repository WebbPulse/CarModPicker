"""
Unit tests for the five pure-function universal-field extractors and the
``extract_universal_fields`` aggregator declared in ``app/crawlers/parsing.py``.

Each extractor is exercised across:

* a high-confidence happy path (JSON-LD or labelled spec row),
* a medium-confidence body-text path,
* a low-confidence path where applicable,
* "no signal in input" → ``None``,
* malformed input (empty string / ``None``) — must never raise.

Plus:

* unit normalization for ``extract_weight`` (kg / lb / oz → grams),
* a ReDoS-resistance assertion: every extractor returns under one wall-clock
  second on a 100 000-char repeating-digit pile (the regex shapes are bounded
  per ``MEM021`` — this test pins that we don't regress to unbounded
  quantifiers),
* a real-fixture smoke check against three tracked archived pages
  (amsperformance, subispeed, briantooleyracing) so we know the extractors
  fire on production HTML, not just hand-crafted snippets,
* a subprocess invocation of the ``universal_extractor_demo`` CLI module to
  prove the slice's demo runs cleanly under the same environment as the
  pytest verify line.

The subprocess test is bundled here (rather than a second file) so the
slice's verification command stays one ``pytest`` call — splitting it would
re-introduce the ``&&`` problem locked in by ``MEM019``.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.crawlers.parsing import (
    extract_finish,
    extract_fitment_notes,
    extract_manufacturer_part_number,
    extract_material,
    extract_universal_fields,
    extract_warranty,
    extract_weight,
)
from tests.crawlers.conftest import load_fixture_html

# Adversarial-input length for T03 ReDoS regression tests. Sized to comfortably
# exceed the 50KB universal-input cap so the cap path is exercised too.
_PATHOLOGICAL_LEN = 50_000

# ---------------------------------------------------------------------------
# extract_weight
# ---------------------------------------------------------------------------


class TestExtractWeight:
    def test_json_ld_quantitative_value_is_high_confidence(self) -> None:
        # Schema.org QuantitativeValue with unitText.
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "weight": {"value": "10", "unitText": "kg"}}
        </script>
        </head><body></body></html>
        """
        result = extract_weight(html)
        assert result is not None
        grams, conf = result
        assert conf == "high"
        # 10 kg → 10000 g exact.
        assert grams == pytest.approx(10_000.0)

    def test_json_ld_un_cefact_unit_code_normalizes(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "weight": {"value": "5", "unitCode": "LBR"}}
        </script>
        </head></html>
        """
        result = extract_weight(html)
        assert result is not None
        grams, conf = result
        assert conf == "high"
        # 5 lb → 2267.96185 g.
        assert grams == pytest.approx(5 * 453.59237)

    def test_labeled_body_row_is_medium_confidence(self) -> None:
        html = "<html><body><div>Weight: 25 lb</div></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, conf = result
        assert conf == "medium"
        assert grams == pytest.approx(25 * 453.59237)

    def test_unlabeled_body_text_is_low_confidence(self) -> None:
        html = "<html><body><p>Travels light at 16 oz.</p></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, conf = result
        # No "Weight:" label and no JSON-LD → low.
        assert conf == "low"
        assert grams == pytest.approx(16 * 28.3495231)

    @pytest.mark.parametrize(
        "value, unit, expected_grams",
        [
            (1, "kg", 1000.0),
            (1, "lb", 453.59237),
            (16, "oz", 16 * 28.3495231),
            (500, "g", 500.0),
            (2.5, "pounds", 2.5 * 453.59237),
        ],
    )
    def test_unit_normalization_to_grams(self, value: float, unit: str, expected_grams: float) -> None:
        html = f"<html><body><div>Weight: {value} {unit}</div></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, _ = result
        assert grams == pytest.approx(expected_grams)

    def test_shipping_weight_block_is_skipped_for_real_spec_row(self) -> None:
        # Shipping table claims 30 lb; real spec row is 12 lb. Stripping the
        # shipping block (DOM-aware) lets the spec row win.
        html = """
        <html><body>
          <table class="shipping-info"><tr><td>Shipping Weight: 30 lb</td></tr></table>
          <div>Weight: 12 lb</div>
        </body></html>
        """
        result = extract_weight(html)
        assert result is not None
        grams, _ = result
        assert grams == pytest.approx(12 * 453.59237)

    def test_no_signal_returns_none(self) -> None:
        html = "<html><body><p>No mass info here.</p></body></html>"
        assert extract_weight(html) is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_weight("") is None
        assert extract_weight("   ") is None
        assert extract_weight(None) is None  # type: ignore[arg-type]

    def test_out_of_range_weight_is_dropped(self) -> None:
        # 5 000 kg → 5_000_000 g is way past the 500_000 g sentinel and
        # should be rejected as scraper noise.
        html = "<html><body><div>Weight: 5000 kg</div></body></html>"
        assert extract_weight(html) is None

    # ---------- T03 Surface 1: composite "X lbs Y oz" shape ----------

    def test_composite_lbs_oz_sums_to_grams(self) -> None:
        # 2 lbs 8 oz → 2 * 453.59237 + 8 * 28.3495231 g.
        html = "<html><body><p>Net weight 2 lbs 8 oz.</p></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, conf = result
        expected = 2 * 453.59237 + 8 * 28.3495231
        assert grams == pytest.approx(expected)
        assert conf == "medium"

    def test_composite_with_label_resolves(self) -> None:
        # Labeled-row variant with the composite shape — the composite branch
        # runs ahead of the labeled-row branch so the whole composite resolves
        # rather than just the lbs leg.
        html = "<html><body><div>Weight: 1 lb 4 oz</div></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, _ = result
        expected = 1 * 453.59237 + 4 * 28.3495231
        assert grams == pytest.approx(expected)

    def test_composite_negative_lone_lbs_uses_single_value_path(self) -> None:
        # Negative path: a bare "5 lbs" with no oz leg must NOT be coerced as
        # a composite — falls through to the existing single-value resolver.
        html = "<html><body><div>Weight: 5 lbs</div></body></html>"
        result = extract_weight(html)
        assert result is not None
        grams, _ = result
        assert grams == pytest.approx(5 * 453.59237)


# ---------------------------------------------------------------------------
# extract_material
# ---------------------------------------------------------------------------


class TestExtractMaterial:
    def test_json_ld_material_string_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "material": "6061 Aluminum"}
        </script>
        </head></html>
        """
        result = extract_material(html)
        assert result == ("6061 aluminum", "high")

    def test_json_ld_material_dict_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "material": {"name": "Stainless Steel"}}
        </script>
        </head></html>
        """
        result = extract_material(html)
        assert result == ("stainless steel", "high")

    def test_labeled_body_row_is_medium_confidence(self) -> None:
        html = "<html><body><div>Material: Titanium</div></body></html>"
        assert extract_material(html) == ("titanium", "medium")

    def test_body_text_match_is_low_confidence(self) -> None:
        html = "<html><body><p>Forged from premium aluminum for the track.</p>" "</body></html>"
        assert extract_material(html) == ("aluminum", "low")

    def test_aluminium_spelling_canonicalizes_to_aluminum(self) -> None:
        html = "<html><body><p>Made from billet aluminium.</p></body></html>"
        # "billet aluminum" pattern doesn't match "billet aluminium" — falls
        # through to "aluminium" which canonicalizes to "aluminum".
        result = extract_material(html)
        assert result is not None
        assert result[0] == "aluminum"

    def test_specific_alloy_wins_over_generic(self) -> None:
        # "6061 aluminum" is more specific than plain "aluminum".
        html = "<html><body><p>Machined from 6061 aluminum bar stock.</p></body></html>"
        assert extract_material(html) == ("6061 aluminum", "low")

    def test_no_signal_returns_none(self) -> None:
        html = "<html><body><p>Lightweight construction.</p></body></html>"
        assert extract_material(html) is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_material("") is None
        assert extract_material(None) is None  # type: ignore[arg-type]

    # ---------- T03 Surface 1: lowercase normalization at JSON-LD ingest ----------

    def test_json_ld_string_title_case_canonicalizes(self) -> None:
        # JSON-LD string-form material must canonicalize from Title-Case to the
        # lexicon's lowercase form. ``re.IGNORECASE`` already covered this in
        # practice; the explicit lowercase guards against a future lexicon
        # entry that drops the IGNORECASE flag.
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "material": "Stainless Steel"}
        </script>
        </head></html>
        """
        assert extract_material(html) == ("stainless steel", "high")

    def test_json_ld_dict_mixed_case_canonicalizes(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X",
         "material": {"name": "TITANIUM"}}
        </script>
        </head></html>
        """
        assert extract_material(html) == ("titanium", "high")

    def test_json_ld_unknown_material_does_not_match(self) -> None:
        # Negative path: a JSON-LD ``material`` value not in the lexicon must
        # NOT produce a hit (no spurious low-conf canonicalization to ""). The
        # body-text path also has nothing to match here.
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "material": "Unobtainium"}
        </script>
        </head></html>
        """
        assert extract_material(html) is None

    def test_body_sweep_skips_chrome_neighborhood_and_returns_real_match(self) -> None:
        # The first lexicon hit is in nav chrome ("ARP stainless steel hidden hardware"
        # appears in a footer line); a real product description further down
        # mentions "carbon fiber". The chrome guard skips the chrome match and
        # returns the legit one.
        html = (
            "<html><body>"
            "<nav>Sign In My Cart Toggle Nav uses ARP stainless steel hidden hardware throughout. </nav>"
            "<main><p>This wheel is forged from carbon fiber for ultimate stiffness.</p></main>"
            "</body></html>"
        )
        assert extract_material(html) == ("carbon fiber", "low")

    def test_body_sweep_returns_none_when_only_chrome_match_exists(self) -> None:
        # Only the chrome region mentions a material — no clean signal. Returning
        # None is correct: a junk low-confidence hit on every page is worse than
        # an honest "we don't know".
        html = (
            "<html><body>"
            "<footer>Toggle Nav Sign In My Account Customer Service "
            "stainless steel hardware page. Wishlist Add to Cart.</footer>"
            "</body></html>"
        )
        assert extract_material(html) is None


# ---------------------------------------------------------------------------
# extract_finish
# ---------------------------------------------------------------------------


class TestExtractFinish:
    def test_json_ld_color_treatment_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "color": "Anodized"}
        </script>
        </head></html>
        """
        assert extract_finish(html) == ("anodized", "high")

    def test_json_ld_color_only_is_low_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "color": "Red"}
        </script>
        </head></html>
        """
        assert extract_finish(html) == ("red", "low")

    def test_labeled_treatment_is_medium_confidence(self) -> None:
        html = "<html><body><div>Finish: Powder Coated</div></body></html>"
        assert extract_finish(html) == ("powder coated", "medium")

    def test_treatment_in_body_text_is_low_confidence(self) -> None:
        html = "<html><body><p>Hand-polished surface.</p></body></html>"
        assert extract_finish(html) == ("polished", "low")

    def test_no_signal_returns_none(self) -> None:
        html = "<html><body><p>High quality construction.</p></body></html>"
        assert extract_finish(html) is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_finish("") is None
        assert extract_finish(None) is None  # type: ignore[arg-type]

    # ---------- T03 Surface 1: Coating/Surface label widening ----------

    def test_coating_label_resolves_treatment(self) -> None:
        # ``Coating: anodized black`` → finish='anodized', medium confidence.
        html = "<html><body><div>Coating: anodized black</div></body></html>"
        assert extract_finish(html) == ("anodized", "medium")

    def test_surface_label_resolves_treatment(self) -> None:
        html = "<html><body><div>Surface: Powder Coated</div></body></html>"
        assert extract_finish(html) == ("powder coated", "medium")

    def test_finish_label_still_resolves_after_widening(self) -> None:
        # Regression guard: original ``Finish:`` prefix must still match.
        html = "<html><body><div>Finish: Polished</div></body></html>"
        assert extract_finish(html) == ("polished", "medium")

    def test_coating_label_negative_unrelated_word(self) -> None:
        # Negative path: ``Coatings sold separately`` (no colon, no label
        # shape) must not produce a labeled-row treatment hit. There's no
        # treatment word in the prose, so the body-text path also returns None.
        html = "<html><body><p>Coatings sold separately.</p></body></html>"
        assert extract_finish(html) is None

    def test_body_sweep_skips_chrome_neighborhood(self) -> None:
        # Chrome region's "Black" link doesn't beat a real "polished" body line.
        html = (
            "<html><body>"
            "<nav>Skip to Content Sign In My Cart Wishlist Black Friday Sale.</nav>"
            "<main><p>Polished aluminum face for show-quality finish.</p></main>"
            "</body></html>"
        )
        assert extract_finish(html) == ("polished", "low")

    def test_body_sweep_returns_none_when_only_chrome_match_exists(self) -> None:
        html = (
            "<html><body>"
            "<footer>Toggle Nav My Account Customer Service: silver tier "
            "membership. Wishlist Add to Cart View Cart.</footer>"
            "</body></html>"
        )
        assert extract_finish(html) is None


# ---------------------------------------------------------------------------
# extract_warranty
# ---------------------------------------------------------------------------


class TestExtractWarranty:
    def test_json_ld_warranty_string_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "warranty": "2 year limited warranty"}
        </script>
        </head></html>
        """
        result = extract_warranty(html)
        assert result is not None
        days, conf = result
        assert conf == "high"
        assert days == pytest.approx(2 * 365.25)

    def test_body_text_warranty_is_medium_confidence(self) -> None:
        html = "<html><body><p>Backed by a 30-day warranty.</p></body></html>"
        result = extract_warranty(html)
        assert result is not None
        days, conf = result
        assert conf == "medium"
        assert days == pytest.approx(30.0)

    def test_months_unit_normalizes(self) -> None:
        html = "<html><body><p>6 months warranty included.</p></body></html>"
        result = extract_warranty(html)
        assert result is not None
        days, _ = result
        assert days == pytest.approx(6 * 30.44)

    def test_no_signal_returns_none(self) -> None:
        assert extract_warranty("<html><body>No coverage info.</body></html>") is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_warranty("") is None
        assert extract_warranty(None) is None  # type: ignore[arg-type]

    # ---------- T03 Surface 1: lifetime literal warranty ----------

    @pytest.mark.parametrize("coverage_token", ["warranty", "guarantee", "coverage"])
    def test_lifetime_literal_in_body_is_medium_confidence(self, coverage_token: str) -> None:
        # ``lifetime warranty/guarantee/coverage`` maps to the 100-year
        # sentinel (36500 days). Body-text path is medium-confidence.
        html = f"<html><body><p>Backed by a lifetime {coverage_token}.</p></body></html>"
        result = extract_warranty(html)
        assert result is not None, f"Expected lifetime+{coverage_token} to resolve"
        days, conf = result
        assert days == pytest.approx(36500.0)
        assert conf == "medium"

    def test_lifetime_in_json_ld_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "warranty": "Lifetime warranty"}
        </script>
        </head></html>
        """
        result = extract_warranty(html)
        assert result is not None
        days, conf = result
        assert days == pytest.approx(36500.0)
        assert conf == "high"

    def test_bare_lifetime_without_coverage_token_does_not_match(self) -> None:
        # Negative path: ``lifetime`` adjacent to non-coverage prose must NOT
        # produce a warranty hit. Guards against e.g. ``lifetime achievement``.
        html = "<html><body><p>Celebrating a lifetime achievement in motorsport.</p></body></html>"
        assert extract_warranty(html) is None


# ---------------------------------------------------------------------------
# extract_fitment_notes
# ---------------------------------------------------------------------------


class TestExtractFitmentNotes:
    def test_chassis_plus_year_in_same_sentence_is_high_confidence(self) -> None:
        html = "<html><body><p>Direct fit for E46 M3, 2001-2006 production years.</p>" "</body></html>"
        result = extract_fitment_notes(html)
        assert result is not None
        text, conf = result
        assert conf == "high"
        assert "E46" in text

    def test_chassis_only_is_medium_confidence(self) -> None:
        html = "<html><body><p>Designed for the F80 platform.</p></body></html>"
        result = extract_fitment_notes(html)
        assert result is not None
        text, conf = result
        assert conf == "medium"
        assert "F80" in text

    def test_no_signal_returns_none(self) -> None:
        html = "<html><body><p>Universal fitment kit.</p></body></html>"
        assert extract_fitment_notes(html) is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_fitment_notes("") is None
        assert extract_fitment_notes(None) is None  # type: ignore[arg-type]

    # ---------- T03 Surface 1: chassis regex widening (1-3 leading alphas) ----------

    @pytest.mark.parametrize("chassis", ["FK8", "MK7", "DC5"])
    def test_widened_chassis_codes_resolve(self, chassis: str) -> None:
        # Honda (FK8/DC5) and VW/Audi (MK7) chassis codes were previously
        # rejected by the 1-alpha-only chassis pattern. Widening to 1-3 alphas
        # lets them through. Preserve the standalone-chassis behavior — these
        # tokens should produce at least a low-confidence fitment hit.
        html = f"<html><body><p>Designed for the {chassis} platform.</p></body></html>"
        result = extract_fitment_notes(html)
        assert result is not None, f"Expected widened chassis {chassis!r} to resolve"
        text, _conf = result
        assert chassis in text

    def test_widened_chassis_with_year_range_is_high_confidence(self) -> None:
        # Composite signal (chassis + year-range in same sentence) preserves
        # the high-confidence path on widened tokens.
        html = "<html><body><p>Direct fit for FK8 Civic Type R, 2017-2021.</p></body></html>"
        result = extract_fitment_notes(html)
        assert result is not None
        text, conf = result
        assert conf == "high"
        assert "FK8" in text

    @pytest.mark.parametrize("legacy", ["E46", "G80"])
    def test_existing_narrow_chassis_codes_still_resolve(self, legacy: str) -> None:
        # Regression guard: widening MUST NOT drop the legacy 1-alpha shapes.
        html = f"<html><body><p>Built for the {legacy} chassis.</p></body></html>"
        result = extract_fitment_notes(html)
        assert result is not None, f"Legacy chassis {legacy!r} must still resolve"
        text, _conf = result
        assert legacy in text

    def test_widened_chassis_negative_pure_alpha_does_not_match(self) -> None:
        # Negative path: a 3-alpha token with no digits (looks vaguely chassis-shaped)
        # must not produce a fitment-notes hit on its own.
        html = "<html><body><p>The ABC product line is now in stock.</p></body></html>"
        assert extract_fitment_notes(html) is None

    # ---------- Chrome neighborhood rejection (cross-cutting noise filter) ----------

    def test_chrome_sentence_with_chassis_is_rejected(self) -> None:
        # Real shape captured from production data: site nav text with a chassis
        # token in the breadcrumb / category list. Must not be persisted as
        # fitment_notes — return None and let the consumer omit the field.
        html = (
            "<html><body><p>Skip to Content Sign In Create an Account "
            "Toggle Nav My Cart Search Search Advanced Search Search Menu "
            "Shop By Vehicle Software ZTF Wheels 034 Gear Garage Sale "
            "RacingLine Service All-Wheel Alignments E36 E46 G20 platform "
            "Kits Brakes Pads Rotors.</p></body></html>"
        )
        assert extract_fitment_notes(html) is None

    def test_chrome_sentence_does_not_shadow_a_clean_one(self) -> None:
        # When the page chrome AND a real product sentence both mention chassis
        # codes, the chrome filter skips the chrome and the legitimate sentence
        # still wins.
        html = (
            "<html><body>"
            "<p>Skip to Content Sign In My Cart Toggle Nav Shop By Vehicle E36.</p>"
            "<p>Direct fit for E46 M3, 2001-2006 production years.</p>"
            "</body></html>"
        )
        result = extract_fitment_notes(html)
        assert result is not None
        text, conf = result
        assert "E46" in text
        assert "Sign In" not in text
        assert conf == "high"

    def test_chrome_only_window_in_last_ditch_sweep_is_rejected(self) -> None:
        # All chassis hits sit inside one chrome-saturated run with no period
        # to split on. The first-pass sentence loop rejects the chrome sentence;
        # the last-ditch sweep then evaluates the wider chrome window and also
        # rejects, returning None instead of nav-only "fitment".
        html = (
            "<html><body><div>"
            "Open Main Menu Sign In Wishlist Customer Service Cart 0 "
            "Add to Cart View Cart Checkout free shipping on orders "
            "categories include E46 in the menu listings"
            "</div></body></html>"
        )
        assert extract_fitment_notes(html) is None


# ---------------------------------------------------------------------------
# extract_manufacturer_part_number (M004/S06 T03)
# ---------------------------------------------------------------------------


class TestExtractManufacturerPartNumber:
    def test_json_ld_mpn_is_high_confidence(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Coilover Set",
         "mpn": "abc-123/x"}
        </script>
        </head><body></body></html>
        """
        result = extract_manufacturer_part_number(html)
        assert result is not None
        mpn, conf = result
        assert conf == "high"
        assert mpn == "ABC-123/X"

    def test_labeled_body_row_is_medium_confidence(self) -> None:
        html = "<html><body><div>MPN: KW-12345-XYZ</div></body></html>"
        result = extract_manufacturer_part_number(html)
        assert result is not None
        mpn, conf = result
        assert conf == "medium"
        assert mpn == "KW-12345-XYZ"

    def test_manufacturer_part_number_label_resolves(self) -> None:
        html = "<html><body><p>Manufacturer Part Number: brz-stx-7</p></body></html>"
        result = extract_manufacturer_part_number(html)
        assert result is not None
        mpn, conf = result
        assert conf == "medium"
        assert mpn == "BRZ-STX-7"

    def test_no_signal_returns_none(self) -> None:
        html = "<html><body><p>Universal fitment kit, ships in 24h.</p></body></html>"
        assert extract_manufacturer_part_number(html) is None

    def test_empty_and_none_inputs_return_none_without_raising(self) -> None:
        assert extract_manufacturer_part_number("") is None
        assert extract_manufacturer_part_number(None) is None

    def test_pathological_alpha_digit_payload_completes_quickly(self) -> None:
        # MEM029/MEM245: bounded {1,63} quantifier on the MPN token body must
        # keep worst-case linear on a 50K-char alpha+digit pile.
        adversarial = ("A1B2C3D4" * (_PATHOLOGICAL_LEN // 8))[:_PATHOLOGICAL_LEN]
        start = time.perf_counter()
        extract_manufacturer_part_number(adversarial)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, (
            f"extract_manufacturer_part_number took {elapsed:.3f}s on adversarial "
            "input — bounded MPN regex has regressed (see MEM029/MEM245)."
        )


# ---------------------------------------------------------------------------
# extract_universal_fields aggregator
# ---------------------------------------------------------------------------


class TestExtractUniversalFields:
    def test_aggregator_returns_only_non_none_hits(self) -> None:
        # Weight + material present; no warranty / finish / fitment text.
        html = """
        <html><body>
          <div>Weight: 5 lb</div>
          <div>Material: Aluminum</div>
        </body></html>
        """
        out = extract_universal_fields(html)
        assert set(out.keys()) == {"weight_grams", "material"}
        # Tuple shape: (value, confidence).
        assert isinstance(out["weight_grams"], tuple)
        assert isinstance(out["material"], tuple)

    def test_empty_input_returns_empty_dict(self) -> None:
        assert extract_universal_fields("") == {}
        assert extract_universal_fields("   ") == {}
        assert extract_universal_fields(None) == {}

    def test_no_signal_input_returns_empty_dict(self) -> None:
        assert extract_universal_fields("<html><body></body></html>") == {}


# ---------------------------------------------------------------------------
# ReDoS / cost guard (MEM021)
# ---------------------------------------------------------------------------


class TestExtractorsAreReDoSResistant:
    """
    Adversarial-input timing pin. The extractors are routinely fed
    user-controlled HTML; unbounded greedy quantifiers next to optional unit
    tokens previously pegged a CPU core for minutes on a digit-only payload
    (MEM021). Each extractor must complete under a generous one-second
    wall-clock budget on a 100 000-char repeating-digit pile.
    """

    @pytest.mark.parametrize(
        "extractor",
        [
            extract_weight,
            extract_material,
            extract_finish,
            extract_warranty,
            extract_fitment_notes,
            extract_manufacturer_part_number,
        ],
    )
    def test_pathological_digit_pile_completes_quickly(self, extractor) -> None:  # type: ignore[no-untyped-def]
        adversarial = "1" * 100_000
        start = time.perf_counter()
        # Extractors must not raise on adversarial input — they should return
        # cleanly within budget. Result value is unimportant; what matters is
        # that the regex engine doesn't backtrack catastrophically.
        extractor(adversarial)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, (
            f"{extractor.__name__} took {elapsed:.3f}s on adversarial input — "
            "regex backtracking has regressed (see MEM021)."
        )

    def test_aggregator_completes_quickly_on_adversarial_input(self) -> None:
        adversarial = "1" * 100_000
        start = time.perf_counter()
        extract_universal_fields(adversarial)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, (
            f"extract_universal_fields took {elapsed:.3f}s on adversarial "
            "input — at least one extractor has regressed past the per-call "
            "1s budget. Investigate before relaxing this gate."
        )

    # ---------- T03 Surface 1: ReDoS regression for the new regex shapes ----------

    @pytest.mark.parametrize(
        "extractor, payload",
        [
            # Composite "X lbs Y oz" — alternating digit / ' lbs ' / digit / ' oz '
            # tokens stress the bounded numeric/whitespace runs.
            (extract_weight, ("1 lbs 1 oz " * 5_000)[:_PATHOLOGICAL_LEN]),
            # Lifetime literal — repeating ``lifetime`` token without coverage
            # cue. Alpha-only payload also tests _CHASSIS_IN_TEXT_RE behavior.
            (extract_warranty, ("lifetime " * 8_000)[:_PATHOLOGICAL_LEN]),
            # Finish coating/surface prefix — repeating label cue.
            (extract_finish, ("Coating: " * 8_000)[:_PATHOLOGICAL_LEN]),
            # Widened chassis ranges over uppercase alphas + digits.
            (extract_fitment_notes, ("FK8 " * 16_000)[:_PATHOLOGICAL_LEN]),
        ],
    )
    def test_new_regex_shapes_redos_resistant(self, extractor, payload: str) -> None:  # type: ignore[no-untyped-def]
        # Each new T03 regex (composite weight, lifetime warranty, coating
        # finish prefix, widened chassis) must complete under 1s on a
        # 50K-char adversarial payload. MEM029: bounded numeric and whitespace
        # runs preserved on every modified pattern.
        start = time.perf_counter()
        extractor(payload)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, (
            f"{extractor.__name__} took {elapsed:.3f}s on T03 adversarial "
            "input — new regex has regressed (see MEM021/MEM029)."
        )


# ---------------------------------------------------------------------------
# Real-fixture smoke checks
# ---------------------------------------------------------------------------


class TestExtractorsOnTrackedFixtures:
    """
    Three tracked product-page fixtures exercise the extractors against real
    archived HTML, not hand-crafted snippets. The assertions here are
    deliberately minimal — we don't want to pin extractor confidence levels
    that S03 will tune; we just need to know an extractor *fires* on real
    pages so a future regex rewrite cannot silently zero out coverage.
    """

    def test_amsperformance_fixture_yields_weight_with_high_confidence(self) -> None:
        html = load_fixture_html("amsperformance")
        out = extract_universal_fields(html)
        assert "weight_grams" in out, f"AMSPerformance fixture should yield a weight from JSON-LD; got {out!r}"
        _, confidence = out["weight_grams"]
        assert confidence == "high", f"AMSPerformance JSON-LD weight should be high-confidence; got {confidence!r}"

    def test_subispeed_fixture_yields_material(self) -> None:
        html = load_fixture_html("subispeed")
        out = extract_universal_fields(html)
        assert "material" in out, f"SubiSpeed fixture should yield a material; got {out!r}"

    def test_briantooleyracing_fixture_yields_fitment_notes(self) -> None:
        html = load_fixture_html("briantooleyracing")
        out = extract_universal_fields(html)
        assert "fitment_notes" in out, f"BrianTooleyRacing fixture should yield fitment notes; got {out!r}"


# ---------------------------------------------------------------------------
# CLI demo subprocess test (single pytest verify line per MEM019)
# ---------------------------------------------------------------------------


def test_universal_extractor_demo_cli() -> None:
    """
    Invoke ``python -m app.crawlers.universal_extractor_demo`` and assert it
    exits cleanly and prints all five tracked adapter slugs. Bundling the
    demo run as a pytest test (instead of a second verify command) keeps the
    slice's verify line single — splitting on ``&&`` would re-trigger
    ``MEM019``.
    """
    backend_dir = Path(__file__).resolve().parents[2]
    assert (backend_dir / "app" / "crawlers" / "universal_extractor_demo.py").is_file(), (
        f"Demo module missing under {backend_dir}; expected at " "app/crawlers/universal_extractor_demo.py"
    )

    result = subprocess.run(
        [sys.executable, "-m", "app.crawlers.universal_extractor_demo"],
        cwd=str(backend_dir),
        capture_output=True,
        check=False,
        timeout=120,
        env={**__import__("os").environ, "TESTING": "true"},
    )

    assert result.returncode == 0, (
        f"Demo CLI exited {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout.decode(errors='replace')}\n"
        f"--- stderr ---\n{result.stderr.decode(errors='replace')}"
    )
    stdout = result.stdout.decode(errors="replace")
    for adapter_slug in (
        "amsperformance",
        "briantooleyracing",
        "cobbtuning",
        "subispeed",
        "texasspeed",
    ):
        assert adapter_slug in stdout, f"Expected adapter slug {adapter_slug!r} in demo stdout; got:\n{stdout}"
