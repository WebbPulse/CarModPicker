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
    extract_material,
    extract_universal_fields,
    extract_warranty,
    extract_weight,
)
from tests.crawlers.conftest import load_fixture_html


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
    def test_unit_normalization_to_grams(
        self, value: float, unit: str, expected_grams: float
    ) -> None:
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
        html = (
            "<html><body><p>Forged from premium aluminum for the track.</p>"
            "</body></html>"
        )
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


# ---------------------------------------------------------------------------
# extract_fitment_notes
# ---------------------------------------------------------------------------


class TestExtractFitmentNotes:
    def test_chassis_plus_year_in_same_sentence_is_high_confidence(self) -> None:
        html = (
            "<html><body><p>Direct fit for E46 M3, 2001-2006 production years.</p>"
            "</body></html>"
        )
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
        assert "weight_grams" in out, (
            f"AMSPerformance fixture should yield a weight from JSON-LD; got {out!r}"
        )
        _, confidence = out["weight_grams"]
        assert confidence == "high", (
            f"AMSPerformance JSON-LD weight should be high-confidence; got {confidence!r}"
        )

    def test_subispeed_fixture_yields_material(self) -> None:
        html = load_fixture_html("subispeed")
        out = extract_universal_fields(html)
        assert "material" in out, (
            f"SubiSpeed fixture should yield a material; got {out!r}"
        )

    def test_briantooleyracing_fixture_yields_fitment_notes(self) -> None:
        html = load_fixture_html("briantooleyracing")
        out = extract_universal_fields(html)
        assert "fitment_notes" in out, (
            f"BrianTooleyRacing fixture should yield fitment notes; got {out!r}"
        )


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
        f"Demo module missing under {backend_dir}; expected at "
        "app/crawlers/universal_extractor_demo.py"
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
        assert adapter_slug in stdout, (
            f"Expected adapter slug {adapter_slug!r} in demo stdout; got:\n{stdout}"
        )
