"""Tests for extract_year_ranges, the single canonical year range parser.

Covers each accepted spelling, century inference, plausibility filtering and empty input.
"""

import datetime as _dt

import pytest

from app.core.car_inference import extract_year_ranges

CURRENT_YEAR = _dt.datetime.now(_dt.timezone.utc).year


class TestYYYYDashYYYY:
    """Ranges written with two four digit years."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("2015-2018", [(2015, 2018)]),
            ("(2015-2018)", [(2015, 2018)]),
            ("Steeda Mustang (2015-2023) Cold Air Kit", [(2015, 2023)]),
            ("ASCII hyphen 2015-2023", [(2015, 2023)]),
            ("en dash 2015–2023", [(2015, 2023)]),
            ("em dash 2015—2023", [(2015, 2023)]),
            ("with spaces 2015 - 2023", [(2015, 2023)]),
            ("with 'to' 2015 to 2023", [(2015, 2023)]),
        ],
    )
    def test_full_4digit_ranges(self, text: str, expected: list[tuple[int, int]]) -> None:
        """Each separator and surrounding text yields the same range."""
        assert extract_year_ranges(text) == expected

    def test_half_my_on_either_side(self) -> None:
        """A half model year on the start truncates to the whole year."""
        assert extract_year_ranges("BorgWarner 1998.5-2002 Cummins") == [(1998, 2002)]


class TestYYYYDashYY:
    """Ranges written with a four digit start and a two digit tail."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("2015-23", [(2015, 2023)]),
            ("(2015-23)", [(2015, 2023)]),
            ("DSS 2005-08 Carbon Driveshaft", [(2005, 2008)]),
            ("Vintage 1995-04 Mopar bracket", [(1995, 2004)]),
        ],
    )
    def test_4digit_start_2digit_tail(self, text: str, expected: list[tuple[int, int]]) -> None:
        """The two digit tail is expanded against the four digit start."""
        assert extract_year_ranges(text) == expected


class TestYYDashYY:
    """Ranges written with two two digit years."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("92-95 Civic", [(1992, 1995)]),
            ("Hasport 90-91 EF Civic mount kit", [(1990, 1991)]),
            ("08-14 challenger SRT", [(2008, 2014)]),
        ],
    )
    def test_2digit_pair_century_inferred(self, text: str, expected: list[tuple[int, int]]) -> None:
        """The century is inferred from the two digit pair."""
        assert extract_year_ranges(text) == expected

    def test_does_not_match_decimal_numbers(self) -> None:
        """Decimal measurements are not read as year ranges."""
        assert extract_year_ranges("Hose ID 1.5-2.0 inch") == []
        assert extract_year_ranges("displacement 5.7-6.4 L") == []


class TestYYYYPlus:
    """Open ended ranges written as a year and a plus."""

    @pytest.mark.parametrize(
        "text",
        [
            "2015+",
            "(2015+)",
            "Subaru WRX 2015+ Strut Bar",
            "MY2015+ trim only",
            "MY2010.5+ Mishimoto kit",
        ],
    )
    def test_open_ended_returns_current_year_plus_one(self, text: str) -> None:
        """An open ended range runs to next year."""
        ranges = extract_year_ranges(text)
        assert len(ranges) == 1
        start = 2010 if "2010" in text else 2015
        assert ranges[0] == (start, CURRENT_YEAR + 1)


class TestSingleYear:
    """Single years, with and without a model year prefix."""

    def test_single_year_returns_y_y(self) -> None:
        """A single year becomes a range covering that year only."""
        assert extract_year_ranges("2015") == [(2015, 2015)]
        assert extract_year_ranges("(2015)") == [(2015, 2015)]

    def test_my_prefix_recognized(self) -> None:
        """A model year prefix is recognised."""
        assert extract_year_ranges("MY2010") == [(2010, 2010)]
        assert extract_year_ranges("MY 2010") == [(2010, 2010)]

    def test_part_of_4digit_year_inside_range_not_double_counted(self) -> None:
        """A year already inside a range is not also emitted on its own."""
        assert extract_year_ranges("(2015-2018)") == [(2015, 2018)]


class TestPlausibilityFilter:
    """Ranges outside the plausible window or inverted are dropped."""

    def test_pre_1960_year_is_dropped(self) -> None:
        """A year before the window is dropped."""
        assert extract_year_ranges("1955-1960") == []
        assert extract_year_ranges("1960") == [(1960, 1960)]

    def test_far_future_year_is_dropped(self) -> None:
        """A year too far in the future is dropped."""
        far_future = CURRENT_YEAR + 5
        assert extract_year_ranges(str(far_future)) == []

    def test_inverted_range_is_dropped(self) -> None:
        """A range whose end precedes its start is dropped."""
        assert extract_year_ranges("2018-2015") == []


class TestMultipleRanges:
    """Text carrying more than one range."""

    def test_returns_all_ranges_in_order(self) -> None:
        """Every range is returned in the order it appears."""
        ranges = extract_year_ranges("92-95 Civic EG / 96-00 Civic EK")
        assert ranges == [(1992, 1995), (1996, 2000)]


class TestEmptyInput:
    """Input with no parseable year."""

    def test_none_returns_empty(self) -> None:
        """None yields no ranges."""
        assert extract_year_ranges(None) == []

    def test_empty_string_returns_empty(self) -> None:
        """An empty string yields no ranges."""
        assert extract_year_ranges("") == []

    def test_no_year_returns_empty(self) -> None:
        """Text with no year yields no ranges."""
        assert extract_year_ranges("Stainless steel boost pipe") == []
