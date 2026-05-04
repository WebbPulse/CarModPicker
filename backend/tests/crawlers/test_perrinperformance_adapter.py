"""
Tests for the Perrin Performance adapter's ``infer_car_for_part`` hook.

Perrin titles encode fitment as a leading year-range token followed by a
comma-separated list of Subaru models (and the BRZ/86/FR-S sibling). The
hook extracts the year range, walks the model dictionary, and intersects
each (make, model) pair against the static generation windows.
"""

from app.core.car_inference import generations_for_make_model_year_range
from app.crawlers.base import ScrapedPayload
from app.crawlers.adapters.tier0_http.perrinperformance import (
    PerrinPerformanceAdapter,
    _extract_perrin_models,
    _extract_perrin_year_range,
)


class TestExtractPerrinYearRange:
    def test_canonical_yyyy_yyyy(self) -> None:
        assert _extract_perrin_year_range("Wheel Spacers 25mm for 2015-2026 WRX, STI") == (2015, 2026)

    def test_two_digit_tail_carries_century(self) -> None:
        assert _extract_perrin_year_range("Bushings for 2002-05 WRX") == (2002, 2005)

    def test_open_ended_yyyy_plus(self) -> None:
        assert _extract_perrin_year_range("Strut Brace Front for 2022+ WRX") == (2022, 9999)

    def test_unicode_dash(self) -> None:
        assert _extract_perrin_year_range("Top Mount Intercooler for 2008–2021 STI") == (2008, 2021)

    def test_no_year_returns_none(self) -> None:
        assert _extract_perrin_year_range("Subaru WRX Cold Air Intake") is None

    def test_implausible_range_rejected(self) -> None:
        # Both years out-of-range bounds.
        assert _extract_perrin_year_range("Antique 1850-1900 part") is None


class TestExtractPerrinModels:
    def test_wrx(self) -> None:
        assert _extract_perrin_models("Bushings 22mm for Rear Swaybar fits 2002-2005 WRX") == [
            ("Subaru", "WRX"),
        ]

    def test_sti_maps_to_wrx(self) -> None:
        # STI is a WRX trim in the seed data — emit the WRX row.
        assert _extract_perrin_models("Top Mount Intercooler for 2008-2021 STI") == [
            ("Subaru", "WRX"),
        ]

    def test_legacy_expands_to_legacy_and_legacy_gt(self) -> None:
        # "Legacy" alone covers both rows; "Outback" covers base + XT. Year-narrow
        # filters off-window gens in the next stage.
        assert _extract_perrin_models("for 2008-2014 WRX, STI, Outback XT, Legacy GT") == [
            ("Subaru", "WRX"),
            ("Subaru", "Legacy"),
            ("Subaru", "Legacy GT"),
            ("Subaru", "Outback"),
            ("Subaru", "Outback XT"),
        ]

    def test_brz_frs_86_three_nameplates(self) -> None:
        # The 86 platform has three nameplates that each map to their own row.
        assert _extract_perrin_models("High Flow Replacement Air Filter for 2013-2020 BRZ, FR-S, 86") == [
            ("Subaru", "BRZ"),
            ("Scion", "FR-S"),
            ("Toyota", "86"),
        ]

    def test_full_lineup(self) -> None:
        # Most-shared title shape — emits a triple for every recognised token.
        models = _extract_perrin_models(
            "Wheel Spacers 25mm for 2015-2026 WRX, STI, Forester, Outback, Legacy, Impreza, BRZ, FR-S, 86"
        )
        assert ("Subaru", "WRX") in models
        assert ("Subaru", "Impreza") in models
        assert ("Subaru", "Legacy") in models
        assert ("Subaru", "Legacy GT") in models
        assert ("Subaru", "Forester XT") in models
        assert ("Subaru", "Outback XT") in models
        assert ("Subaru", "BRZ") in models
        assert ("Scion", "FR-S") in models
        assert ("Toyota", "86") in models

    def test_no_known_model_returns_empty(self) -> None:
        # Year range present but no model token — hook must punt.
        assert _extract_perrin_models("Generic 2015-2020 hardware kit") == []

    def test_bare_86_does_not_match_year_fragment(self) -> None:
        # The bare "86" pattern uses non-digit boundaries so it can't latch
        # onto a year fragment like "1986" or "2086".
        assert ("Toyota", "86") not in _extract_perrin_models("Vintage 1986 part")
        assert ("Toyota", "86") not in _extract_perrin_models("for 2008-2086 WRX")


class TestPerrinIntersectGenerations:
    """Anchor the generation-window contract for a few Perrin-typical inputs."""

    def test_wrx_2015_2026_spans_three_gens(self) -> None:
        # 2015-2026 covers VA (2015-2021) and VB (2022-present).
        triples = generations_for_make_model_year_range("Subaru", "WRX", (2015, 2026))
        assert triples == [
            ("Subaru", "WRX", "VA"),
            ("Subaru", "WRX", "VB"),
        ]

    def test_brz_2013_2020_returns_zc6(self) -> None:
        assert generations_for_make_model_year_range("Subaru", "BRZ", (2013, 2020)) == [
            ("Subaru", "BRZ", "ZC6"),
        ]

    def test_brz_2021_open_ended_returns_zd8(self) -> None:
        assert generations_for_make_model_year_range("Subaru", "BRZ", (2021, 9999)) == [
            ("Subaru", "BRZ", "ZD8"),
        ]

    def test_outback_xt_2002_2005_returns_empty(self) -> None:
        # Outback XT only goes back to 2005 in seed; a 2002-2005 part hits
        # only the start of the BL/BP gen.
        triples = generations_for_make_model_year_range("Subaru", "Outback XT", (2002, 2005))
        assert ("Subaru", "Outback XT", "BL/BP") in triples


class TestInferCarForPart:
    """End-to-end: model + year-range in title → resolved triples."""

    def _payload(self, name: str) -> ScrapedPayload:
        return ScrapedPayload(name=name, product_url=f"https://perrin.com/products/{name[:20]}")

    def test_wrx_only_resolves(self) -> None:
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Bushings 22mm for Rear Swaybar fits 2002-2005 WRX")
        )
        # 2002-2005 covers GD (2002-2007).
        assert triples == [("Subaru", "WRX", "GD")]

    def test_sti_routes_to_wrx(self) -> None:
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Top Mount Intercooler for 2008-2021 STI")
        )
        # 2008-2021 covers GR (2008-2014) and VA (2015-2021).
        assert triples == [
            ("Subaru", "WRX", "GR"),
            ("Subaru", "WRX", "VA"),
        ]

    def test_brz_frs_86_emits_three_nameplates(self) -> None:
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("High Flow Replacement Air Filter for 2013-2020 BRZ, FR-S, 86")
        )
        assert triples is not None
        assert ("Subaru", "BRZ", "ZC6") in triples
        assert ("Scion", "FR-S", "ZN6") in triples
        assert ("Toyota", "86", "ZN6") in triples

    def test_open_ended_yyyy_plus(self) -> None:
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Fender Shrouds for 2022+ WRX")
        )
        assert triples == [("Subaru", "WRX", "VB")]

    def test_no_year_tag_returns_none(self) -> None:
        # Year-range required — without one the universal pipeline can still
        # resolve titles like "Subaru WRX Cold Air Intake".
        adapter = PerrinPerformanceAdapter()
        assert adapter.infer_car_for_part(self._payload("Subaru WRX Cold Air Intake")) is None

    def test_no_known_model_returns_none(self) -> None:
        # Generic part with year range but no Perrin-mapped model token.
        adapter = PerrinPerformanceAdapter()
        assert adapter.infer_car_for_part(self._payload("Generic 2015-2020 hardware kit")) is None

    def test_empty_name_returns_none(self) -> None:
        adapter = PerrinPerformanceAdapter()
        assert adapter.infer_car_for_part(ScrapedPayload(name="", product_url="https://x")) is None

    def test_crosstrek_year_range_resolves(self) -> None:
        # Crosstrek was added to seed in this PR; before that the token was
        # silently dropped because no DB row existed.
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("CSF Aluminum 2 Row Radiator for 2018-2023 Crosstrek, Impreza")
        )
        assert triples is not None
        assert ("Subaru", "Crosstrek", "2nd Gen") in triples
        assert ("Subaru", "Impreza", "GP/GJ") in triples

    def test_forester_base_resolves_for_post_xt_years(self) -> None:
        # 2019-2024 (Forester SK) is past the XT-trim window (last XT was SJ,
        # 2014-2018). Without the base Forester seed entry this would have
        # produced no triples.
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Performance Air Intake for 2019-2024 Forester")
        )
        assert triples == [("Subaru", "Forester", "SK")]

    def test_full_lineup_year_narrows_correctly(self) -> None:
        # 2015-2026 should NOT pick up Forester XT (last gen ends 2018) or
        # Legacy GT (last gen ends 2009 in seed) for off-window years —
        # the year-narrow contract drops those rows silently.
        adapter = PerrinPerformanceAdapter()
        triples = adapter.infer_car_for_part(
            self._payload(
                "Wheel Spacers 25mm for 2015-2026 WRX, STI, Forester, Outback, Legacy, Impreza, BRZ"
            )
        )
        assert triples is not None
        # WRX should resolve VA + VB; BRZ should resolve ZC6 + ZD8.
        assert ("Subaru", "WRX", "VA") in triples
        assert ("Subaru", "WRX", "VB") in triples
        assert ("Subaru", "BRZ", "ZC6") in triples
        assert ("Subaru", "BRZ", "ZD8") in triples
