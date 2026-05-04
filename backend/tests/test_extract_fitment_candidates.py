"""Tests for extract_fitment_candidates (issue #2).

Shared (make, model, year_range) extractor that adapter hooks call instead
of maintaining per-adapter regex dictionaries.
"""

import datetime as _dt

from app.core.car_inference import (
    FitmentCandidate,
    extract_fitment_candidates,
)


CURRENT_YEAR = _dt.datetime.now(_dt.timezone.utc).year


class TestMakeModelMatching:
    def test_full_make_model_phrase(self) -> None:
        candidates = extract_fitment_candidates("Steeda Ford Mustang Strut Tower Brace")
        assert any(c.make == "Ford" and c.model == "Mustang" for c in candidates)

    def test_bare_model_requires_trusted_makes(self) -> None:
        # Without trusted_makes, "Mustang Cold Air Kit" must NOT match.
        candidates = extract_fitment_candidates("Mustang Cold Air Kit")
        assert not any(c.model == "Mustang" for c in candidates)

    def test_bare_model_with_trusted_makes_matches(self) -> None:
        candidates = extract_fitment_candidates(
            "Mustang Cold Air Kit", trusted_makes={"Ford"}
        )
        assert any(c.make == "Ford" and c.model == "Mustang" for c in candidates)

    def test_trusted_makes_constrains_full_phrase_match_too(self) -> None:
        # "Toyota Supra" full phrase must NOT match if Toyota isn't trusted.
        candidates = extract_fitment_candidates(
            "Toyota Supra Carbon Fiber Lip", trusted_makes={"Ford"}
        )
        assert not any(c.make == "Toyota" for c in candidates)


class TestYearPairing:
    def test_year_range_paired_with_adjacent_make_model(self) -> None:
        candidates = extract_fitment_candidates(
            "Steeda Ford Mustang (2015-2023) Cold Air Intake"
        )
        ford_match = next((c for c in candidates if c.model == "Mustang"), None)
        assert ford_match is not None
        assert ford_match.year_range == (2015, 2023)

    def test_year_range_pairs_to_closest_make_model(self) -> None:
        # Two ranges in a multi-fitment title; each should pair with its model.
        candidates = extract_fitment_candidates(
            "2009-2014 Dodge Charger SRT8 / 2015-2023 Dodge Challenger Driveshaft",
            trusted_makes={"Dodge"},
        )
        charger = next((c for c in candidates if c.model == "Charger"), None)
        challenger = next((c for c in candidates if c.model == "Challenger"), None)
        assert charger is not None
        assert challenger is not None
        assert charger.year_range == (2009, 2014)
        assert challenger.year_range == (2015, 2023)

    def test_no_year_in_title_yields_none_year_range(self) -> None:
        candidates = extract_fitment_candidates(
            "Mustang Strut Brace", trusted_makes={"Ford"}
        )
        m = next((c for c in candidates if c.model == "Mustang"), None)
        assert m is not None
        assert m.year_range is None

    def test_far_year_not_paired(self) -> None:
        # Year is more than 50 chars away from the model — no pairing.
        title = "Mustang " + ("filler " * 10) + "(2015-2023)"
        candidates = extract_fitment_candidates(title, trusted_makes={"Ford"})
        m = next((c for c in candidates if c.model == "Mustang"), None)
        assert m is not None
        assert m.year_range is None


class TestRealWorldTitles:
    """Cross-check against known-good titles from each migrated adapter's corpus."""

    def test_steeda_parens_year_form(self) -> None:
        candidates = extract_fitment_candidates(
            "Steeda Mustang (2015-2023) Cold Air Kit", trusted_makes={"Ford"}
        )
        m = next(c for c in candidates if c.model == "Mustang")
        assert m.make == "Ford"
        assert m.year_range == (2015, 2023)

    def test_driveshaftshop_leading_year_form(self) -> None:
        candidates = extract_fitment_candidates(
            "2005-08 Mustang GT 1-Piece Carbon Driveshaft", trusted_makes={"Ford"}
        )
        m = next(c for c in candidates if c.model == "Mustang")
        assert m.year_range == (2005, 2008)

    def test_perrin_subaru_form(self) -> None:
        candidates = extract_fitment_candidates(
            "Perrin 2015-2018 Subaru WRX/STI Strut Bar"
        )
        m = next(c for c in candidates if c.make == "Subaru" and c.model == "WRX")
        assert m.year_range == (2015, 2018)

    def test_open_ended_year(self) -> None:
        candidates = extract_fitment_candidates(
            "2015+ Subaru WRX Front Strut Bar"
        )
        m = next(c for c in candidates if c.model == "WRX")
        assert m.year_range == (2015, CURRENT_YEAR + 1)


class TestDeduplication:
    def test_duplicate_make_model_year_collapsed(self) -> None:
        # Two mentions of the same fitment (different fragments of the title).
        candidates = extract_fitment_candidates(
            "Subaru WRX strut brace, fits all WRX 2015-2018 trims"
        )
        wrx = [c for c in candidates if c.model == "WRX"]
        # First mention pairs with no year (none nearby), second with (2015, 2018).
        # We deduplicate on (make, model, year_range) so both can coexist if year differs.
        # Key contract: same (make, model, year_range) tuple appears at most once.
        keys = [(c.make, c.model, c.year_range) for c in wrx]
        assert len(keys) == len(set(keys))


class TestEmptyInput:
    def test_none_returns_empty(self) -> None:
        assert extract_fitment_candidates(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert extract_fitment_candidates("") == []

    def test_no_make_or_model_returns_empty(self) -> None:
        assert extract_fitment_candidates("Stainless Steel Boost Pipe") == []


class TestFitmentCandidateDataclass:
    def test_equality_and_hashing(self) -> None:
        a = FitmentCandidate("Ford", "Mustang", (2015, 2023))
        b = FitmentCandidate("Ford", "Mustang", (2015, 2023))
        c = FitmentCandidate("Ford", "Mustang", None)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)
