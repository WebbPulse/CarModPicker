"""Tests for extract_fitment_candidates, the shared make, model and year extractor."""

import datetime as _dt

from app.core.car_inference import (
    FitmentCandidate,
    extract_fitment_candidates,
)

CURRENT_YEAR = _dt.datetime.now(_dt.timezone.utc).year


class TestMakeModelMatching:
    """Matching a make and model out of a title."""

    def test_full_make_model_phrase(self) -> None:
        """A full make and model phrase is matched."""
        candidates = extract_fitment_candidates("Steeda Ford Mustang Strut Tower Brace")
        assert any(c.make == "Ford" and c.model == "Mustang" for c in candidates)

    def test_bare_model_requires_trusted_makes(self) -> None:
        """A bare model is not matched without a trusted make to attribute it to."""
        candidates = extract_fitment_candidates("Mustang Cold Air Kit")
        assert not any(c.model == "Mustang" for c in candidates)

    def test_bare_model_with_trusted_makes_matches(self) -> None:
        """A bare model matches once the make is trusted."""
        candidates = extract_fitment_candidates("Mustang Cold Air Kit", trusted_makes={"Ford"})
        assert any(c.make == "Ford" and c.model == "Mustang" for c in candidates)

    def test_trusted_makes_constrains_full_phrase_match_too(self) -> None:
        """Trusted makes also constrain a full phrase match."""
        candidates = extract_fitment_candidates("Toyota Supra Carbon Fiber Lip", trusted_makes={"Ford"})
        assert not any(c.make == "Toyota" for c in candidates)


class TestYearPairing:
    """Pairing an extracted year range to the nearest make and model."""

    def test_year_range_paired_with_adjacent_make_model(self) -> None:
        """An adjacent year range is paired with the make and model."""
        candidates = extract_fitment_candidates("Steeda Ford Mustang (2015-2023) Cold Air Intake")
        ford_match = next((c for c in candidates if c.model == "Mustang"), None)
        assert ford_match is not None
        assert ford_match.year_range == (2015, 2023)

    def test_year_range_pairs_to_closest_make_model(self) -> None:
        """A year range pairs with the closest make and model, not the first."""
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
        """A title with no year yields a candidate with no year range."""
        candidates = extract_fitment_candidates("Mustang Strut Brace", trusted_makes={"Ford"})
        m = next((c for c in candidates if c.model == "Mustang"), None)
        assert m is not None
        assert m.year_range is None

    def test_far_year_not_paired(self) -> None:
        """A year range too far from the model is not paired with it."""
        title = "Mustang " + ("filler " * 10) + "(2015-2023)"
        candidates = extract_fitment_candidates(title, trusted_makes={"Ford"})
        m = next((c for c in candidates if c.model == "Mustang"), None)
        assert m is not None
        assert m.year_range is None


class TestRealWorldTitles:
    """Cross-check against known-good titles from each migrated adapter's corpus."""

    def test_steeda_parens_year_form(self) -> None:
        """A parenthesised year form from a real title is extracted."""
        candidates = extract_fitment_candidates("Steeda Mustang (2015-2023) Cold Air Kit", trusted_makes={"Ford"})
        m = next(c for c in candidates if c.model == "Mustang")
        assert m.make == "Ford"
        assert m.year_range == (2015, 2023)

    def test_driveshaftshop_leading_year_form(self) -> None:
        """A leading year form from a real title is extracted."""
        candidates = extract_fitment_candidates("2005-08 Mustang GT 1-Piece Carbon Driveshaft", trusted_makes={"Ford"})
        m = next(c for c in candidates if c.model == "Mustang")
        assert m.year_range == (2005, 2008)

    def test_perrin_subaru_form(self) -> None:
        """A Subaru title form is extracted."""
        candidates = extract_fitment_candidates("Perrin 2015-2018 Subaru WRX/STI Strut Bar")
        m = next(c for c in candidates if c.make == "Subaru" and c.model == "WRX")
        assert m.year_range == (2015, 2018)

    def test_open_ended_year(self) -> None:
        """An open ended year form is extracted."""
        candidates = extract_fitment_candidates("2015+ Subaru WRX Front Strut Bar")
        m = next(c for c in candidates if c.model == "WRX")
        assert m.year_range == (2015, CURRENT_YEAR + 1)


class TestDeduplication:
    """Repeated candidates collapse to one."""

    def test_duplicate_make_model_year_collapsed(self) -> None:
        """The same make, model and year range appears once."""
        candidates = extract_fitment_candidates("Subaru WRX strut brace, fits all WRX 2015-2018 trims")
        wrx = [c for c in candidates if c.model == "WRX"]
        keys = [(c.make, c.model, c.year_range) for c in wrx]
        assert len(keys) == len(set(keys))


class TestEmptyInput:
    """Input with nothing to extract."""

    def test_none_returns_empty(self) -> None:
        """None yields no candidates."""
        assert extract_fitment_candidates(None) == []

    def test_empty_string_returns_empty(self) -> None:
        """An empty string yields no candidates."""
        assert extract_fitment_candidates("") == []

    def test_no_make_or_model_returns_empty(self) -> None:
        """Text naming no make or model yields no candidates."""
        assert extract_fitment_candidates("Stainless Steel Boost Pipe") == []


class TestFitmentCandidateDataclass:
    """The candidate value type itself."""

    def test_equality_and_hashing(self) -> None:
        """Candidates compare and hash by value, which is what deduplication relies on."""
        a = FitmentCandidate("Ford", "Mustang", (2015, 2023))
        b = FitmentCandidate("Ford", "Mustang", (2015, 2023))
        c = FitmentCandidate("Ford", "Mustang", None)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)
