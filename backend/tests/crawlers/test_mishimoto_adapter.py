"""
Tests for the Mishimoto adapter's ``infer_car_for_part`` hook.

Mishimoto titles encode fitment as a ", fits <Make> <Model> [<engine/trim>]
<year-range>" suffix. The hook extracts the suffix, identifies the make,
matches a make-scoped model pattern, and intersects the year range against
the static generation windows.
"""

from app.crawlers.base import ScrapedPayload
from app.crawlers.adapters.tier0_http.mishimoto import (
    MishimotoAdapter,
    _extract_mishimoto_make,
    _extract_mishimoto_model,
    _extract_mishimoto_year_range,
)


class TestExtractMishimotoYearRange:
    def test_canonical_yyyy_yyyy(self) -> None:
        assert _extract_mishimoto_year_range("Ford Mustang 5.0L 2011-2014") == (2011, 2014)

    def test_two_digit_tail_carries_century(self) -> None:
        assert _extract_mishimoto_year_range("Chevrolet/GMC 6.6L Duramax 2011-16") == (2011, 2016)

    def test_open_ended_yyyy_plus(self) -> None:
        assert _extract_mishimoto_year_range("Ford 6.7L Powerstroke 2017+") == (2017, 9999)

    def test_yyyy_dot_5_mid_my(self) -> None:
        # Mishimoto uses "2007.5" for mid-MY Cummins introductions; we coerce to 2007.
        assert _extract_mishimoto_year_range("Dodge 6.7L Cummins 2007.5-2009") == (2007, 2009)
        assert _extract_mishimoto_year_range("Chevrolet/GMC 6.6L Duramax 2004.5-10") == (2004, 2010)

    def test_no_year_returns_none(self) -> None:
        assert _extract_mishimoto_year_range("Front-Sump Oil Cooler Adapter, fits LS1/LS2") is None


class TestExtractMishimotoMake:
    def test_canonical_makes(self) -> None:
        assert _extract_mishimoto_make("Ford Mustang 2011-2014") == "Ford"
        assert _extract_mishimoto_make("Mazda Miata 1990-1991") == "Mazda"
        assert _extract_mishimoto_make("Toyota Supra 1986-1992") == "Toyota"

    def test_chevy_alias(self) -> None:
        # "Chevy" is a colloquial form of Chevrolet.
        assert _extract_mishimoto_make("Chevy Monte Carlo 305/350/400ci 1970-1977") == "Chevrolet"

    def test_chevrolet_gmc_split(self) -> None:
        # "Chevrolet/GMC 6.6L Duramax" — split on "/" so the first sub-token resolves.
        assert _extract_mishimoto_make("Chevrolet/GMC 6.6L Duramax 2011-2016") == "Chevrolet"

    def test_unknown_make_returns_none(self) -> None:
        assert _extract_mishimoto_make("Bugatti Veyron 2005-2015") is None

    def test_empty_returns_none(self) -> None:
        assert _extract_mishimoto_make("") is None
        assert _extract_mishimoto_make("   ") is None


class TestExtractMishimotoModel:
    def test_ford_mustang_subtrims_collapse(self) -> None:
        # "Mustang EcoBoost" / "Mustang 5.0L" / "Mustang" all map to the parent row.
        assert _extract_mishimoto_model("Ford Mustang EcoBoost 2015-2023", "Ford") == "Mustang"
        assert _extract_mishimoto_model("Ford Mustang 5.0L 2011-2014", "Ford") == "Mustang"
        assert _extract_mishimoto_model("Ford Mustang 351ci 1967-1969", "Ford") == "Mustang"

    def test_focus_subtrims_resolve_to_their_own_rows(self) -> None:
        # Focus RS / Focus ST / base Focus each have their own seed row.
        assert _extract_mishimoto_model("Ford Focus RS 2016-2018", "Ford") == "Focus RS"
        assert _extract_mishimoto_model("Ford Focus ST 2013-2018", "Ford") == "Focus ST"
        assert _extract_mishimoto_model("Ford Focus 2016-2018", "Ford") == "Focus"

    def test_f250_routes_to_super_duty(self) -> None:
        # Ford F-250/F-350 collapse into the F-Series Super Duty row.
        assert (
            _extract_mishimoto_model("Ford F-250 6.7L Powerstroke 2011-2016", "Ford")
            == "F-Series Super Duty"
        )

    def test_mazda_miata(self) -> None:
        assert _extract_mishimoto_model("Mazda Miata 1990-1991", "Mazda") == "Miata"

    def test_jeep_wrangler(self) -> None:
        # Jeep was empty in seed before this PR; Wrangler now exists.
        assert _extract_mishimoto_model("Jeep Wrangler JL 2.0L 2018-2023", "Jeep") == "Wrangler"

    def test_engine_platform_title_does_not_match_a_model(self) -> None:
        # "Dodge 5.9L Cummins" has no Dodge model token — the hook should
        # punt rather than guess. Verifies the engine-platform fallthrough.
        assert _extract_mishimoto_model("Dodge 5.9L Cummins 1994-2002", "Dodge") is None
        assert _extract_mishimoto_model("Ford 6.7L Powerstroke 2011-2016", "Ford") is None

    def test_unknown_make_returns_none(self) -> None:
        # Even with a valid model token, an unsupported make (e.g. Smart) returns None.
        assert _extract_mishimoto_model("Wrangler 2018-2023", "Smart") is None


class TestInferCarForPart:
    """End-to-end: complete Mishimoto title → resolved triples."""

    def _payload(self, name: str) -> ScrapedPayload:
        return ScrapedPayload(name=name, product_url=f"https://www.mishimoto.com/{name[:20]}")

    def test_ford_mustang_5_0l(self) -> None:
        adapter = MishimotoAdapter()
        triples = adapter.infer_car_for_part(
            self._payload(
                "Oil Cooler Kit, Black, Thermostatic, fits Ford Mustang 5.0L 2011-2014"
            )
        )
        assert triples == [("Ford", "Mustang", "5th Gen")]

    def test_jeep_wrangler_jl(self) -> None:
        adapter = MishimotoAdapter()
        triples = adapter.infer_car_for_part(
            self._payload(
                "Performance Intercooler Pipe, fits Jeep Wrangler JL 2.0L 2018-2023"
            )
        )
        # 2018 is the JK→JL transition year (JK ends 2018, JL starts 2018), so
        # year-narrow correctly matches both. The JL trim qualifier in the
        # title doesn't narrow further today; that would require platform-code
        # extraction which is out of scope for this hook.
        assert triples is not None
        names = {gen for _, _, gen in triples}
        assert "JL" in names
        assert "JK" in names

    def test_chevy_camaro_ss(self) -> None:
        adapter = MishimotoAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Oil Cooler Kit, Silver, fits Chevrolet Camaro SS 2016-2024")
        )
        # 2016-2024 covers the 6th gen Camaro (2016-2024).
        assert triples is not None
        assert ("Chevrolet", "Camaro", "6th Gen") in triples

    def test_mazda_miata_classic(self) -> None:
        adapter = MishimotoAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Silicone Heater Hose Set, Black, fits Mazda Miata 1994-2005")
        )
        assert triples is not None
        # 1994-2005 covers NA (1990-1997) and NB (1998-2005).
        names = {gen for _, _, gen in triples}
        assert "NA" in names
        assert "NB" in names

    def test_engine_platform_title_returns_none(self) -> None:
        # Engine-platform titles have no vehicle model — the hook must punt
        # so the part falls through to the universal pipeline rather than
        # mis-attributing to a wrong Dodge model.
        adapter = MishimotoAdapter()
        assert (
            adapter.infer_car_for_part(
                self._payload(
                    "Intercooler, Black, fits Dodge 5.9L/6.7 Cummins 2003-2009"
                )
            )
            is None
        )
        assert (
            adapter.infer_car_for_part(
                self._payload("Replacement Oil Cooler, fits Ford 6.4L Powerstroke 2008-2010")
            )
            is None
        )

    def test_no_fits_suffix_returns_none(self) -> None:
        # Titles without "fits ..." can't be parsed by this hook.
        adapter = MishimotoAdapter()
        assert (
            adapter.infer_car_for_part(self._payload("Mishimoto Aluminum Catch Can"))
            is None
        )

    def test_unknown_make_returns_none(self) -> None:
        # Bugatti has no support in the make alias dict.
        adapter = MishimotoAdapter()
        assert (
            adapter.infer_car_for_part(
                self._payload("Performance Intake, fits Bugatti Chiron 2016-2024")
            )
            is None
        )

    def test_no_year_range_returns_none(self) -> None:
        # Bare engine code like "fits LS1/LS2" — no year, no model.
        adapter = MishimotoAdapter()
        assert (
            adapter.infer_car_for_part(
                self._payload("Front-Sump Oil Cooler Adapter, fits LS1/LS2")
            )
            is None
        )

    def test_empty_name_returns_none(self) -> None:
        adapter = MishimotoAdapter()
        assert adapter.infer_car_for_part(ScrapedPayload(name="", product_url="https://x")) is None

    def test_dodge_challenger_classic(self) -> None:
        adapter = MishimotoAdapter()
        triples = adapter.infer_car_for_part(
            self._payload(
                "Performance Aluminum Radiator, fits Dodge Challenger Big Block 1970-1974"
            )
        )
        assert triples is not None
        # 1970-1974 covers the 1st-gen Challenger.
        names = {gen for _, _, gen in triples}
        assert "1st Gen" in names
