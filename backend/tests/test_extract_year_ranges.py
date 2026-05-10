"""Tests for extract_year_ranges (issue #5).

Single canonical year-range parser, replacing the 5 near-duplicate
_extract_*_year_range helpers that lived in Steeda, Hasport, Perrin,
Mishimoto, and Driveshaftshop adapters.
"""

import datetime as _dt

import pytest

from app.core.car_inference import extract_year_ranges


CURRENT_YEAR = _dt.datetime.now(_dt.timezone.utc).year


class TestYYYYDashYYYY:
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
        assert extract_year_ranges(text) == expected

    def test_half_my_on_either_side(self) -> None:
        # MY1998.5-2002 → (1998, 2002); MY 2010.5+ would be tested in YYYY_PLUS.
        assert extract_year_ranges("BorgWarner 1998.5-2002 Cummins") == [(1998, 2002)]


class TestYYYYDashYY:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("2015-23", [(2015, 2023)]),
            ("(2015-23)", [(2015, 2023)]),
            ("DSS 2005-08 Carbon Driveshaft", [(2005, 2008)]),
            # Crossing decade boundary: '95-04 should be (1995, 2004).
            ("Vintage 1995-04 Mopar bracket", [(1995, 2004)]),
        ],
    )
    def test_4digit_start_2digit_tail(self, text: str, expected: list[tuple[int, int]]) -> None:
        assert extract_year_ranges(text) == expected


class TestYYDashYY:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("92-95 Civic", [(1992, 1995)]),
            ("Hasport 90-91 EF Civic mount kit", [(1990, 1991)]),
            ("08-14 challenger SRT", [(2008, 2014)]),
        ],
    )
    def test_2digit_pair_century_inferred(self, text: str, expected: list[tuple[int, int]]) -> None:
        assert extract_year_ranges(text) == expected

    def test_does_not_match_decimal_numbers(self) -> None:
        # "1.5-2.0" or "5.7-6.4" must not be interpreted as years.
        assert extract_year_ranges("Hose ID 1.5-2.0 inch") == []
        assert extract_year_ranges("displacement 5.7-6.4 L") == []


class TestYYYYPlus:
    @pytest.mark.parametrize(
        "text",
        [
            "2015+",
            "(2015+)",
            "Subaru WRX 2015+ Strut Bar",
            "MY2015+ trim only",
            # .5 MY ahead of +
            "MY2010.5+ Mishimoto kit",
        ],
    )
    def test_open_ended_returns_current_year_plus_one(self, text: str) -> None:
        ranges = extract_year_ranges(text)
        assert len(ranges) == 1
        # The year extracted from the text (2015 or 2010 depending on input).
        start = 2010 if "2010" in text else 2015
        assert ranges[0] == (start, CURRENT_YEAR + 1)


class TestSingleYear:
    def test_single_year_returns_y_y(self) -> None:
        assert extract_year_ranges("2015") == [(2015, 2015)]
        assert extract_year_ranges("(2015)") == [(2015, 2015)]

    def test_my_prefix_recognized(self) -> None:
        assert extract_year_ranges("MY2010") == [(2010, 2010)]
        assert extract_year_ranges("MY 2010") == [(2010, 2010)]

    def test_part_of_4digit_year_inside_range_not_double_counted(self) -> None:
        # The YYYY-YYYY match should consume both endpoint years; we should
        # not also see (2015, 2015) and (2018, 2018) as single-year hits.
        assert extract_year_ranges("(2015-2018)") == [(2015, 2018)]


class TestPlausibilityFilter:
    def test_pre_1960_year_is_dropped(self) -> None:
        assert extract_year_ranges("1955-1960") == []
        # 1960 alone is the floor and is allowed.
        assert extract_year_ranges("1960") == [(1960, 1960)]

    def test_far_future_year_is_dropped(self) -> None:
        # Beyond current_year + 1.
        far_future = CURRENT_YEAR + 5
        assert extract_year_ranges(str(far_future)) == []

    def test_inverted_range_is_dropped(self) -> None:
        # 2018-2015 is implausible.
        assert extract_year_ranges("2018-2015") == []


class TestMultipleRanges:
    def test_returns_all_ranges_in_order(self) -> None:
        # Hasport titles can list multiple chassis-and-year segments.
        ranges = extract_year_ranges(
            "92-95 Civic EG / 96-00 Civic EK"
        )
        assert ranges == [(1992, 1995), (1996, 2000)]


class TestEmptyInput:
    def test_none_returns_empty(self) -> None:
        assert extract_year_ranges(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert extract_year_ranges("") == []

    def test_no_year_returns_empty(self) -> None:
        assert extract_year_ranges("Stainless steel boost pipe") == []
