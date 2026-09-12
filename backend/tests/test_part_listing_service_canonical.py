"""Tests for canonical manufacturer names and the canonical key lookup.

The lookup is what keeps a collapsed duplicate from being recreated by an adapter.
"""

from __future__ import annotations

from typing import Any

from app.api.services.part_listing_service import (
    get_or_create_part_manufacturer_by_name,
    manufacturer_name_canonical,
)
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from tests.conftest import save_catalog


class TestManufacturerNameCanonical:
    """The canonical key collapses casing, whitespace, punctuation, and a
    fixed set of trailing brand-suffix tokens (Performance, Tuning, Inc, etc.).
    """

    def test_empty_string_returns_empty(self) -> None:
        """An empty name canonicalises to empty."""
        assert manufacturer_name_canonical("") == ""
        assert manufacturer_name_canonical("   ") == ""

    def test_brand_subdivision_collapses_to_parent(self) -> None:
        """A brand subdivision canonicalises to its parent brand."""
        assert manufacturer_name_canonical("APR Performance") == "apr"
        assert manufacturer_name_canonical("APR") == "apr"
        assert manufacturer_name_canonical("AEM Electronics") == "aem"
        assert manufacturer_name_canonical("AEM Induction") == "aem"
        assert manufacturer_name_canonical("AEM") == "aem"
        assert manufacturer_name_canonical("PRL Motorsports") == "prl"
        assert manufacturer_name_canonical("PRL") == "prl"
        assert manufacturer_name_canonical("Hawk Performance") == "hawk"
        assert manufacturer_name_canonical("Burger Motorsports") == "burger"
        assert manufacturer_name_canonical("Burger Motorsport") == "burger"

    def test_corporate_suffix_strips(self) -> None:
        """Corporate suffixes are stripped from the canonical form."""
        assert manufacturer_name_canonical("Katech Engineering") == "katech"
        assert manufacturer_name_canonical("Katech Inc.") == "katech"
        assert manufacturer_name_canonical("Katech Inc") == "katech"
        assert manufacturer_name_canonical("Katech") == "katech"
        assert manufacturer_name_canonical("CSF Inc.") == "csf"
        assert manufacturer_name_canonical("CSF") == "csf"

    def test_iterative_trailing_token_strip(self) -> None:
        """Trailing tokens are stripped repeatedly until the brand remains."""
        assert manufacturer_name_canonical("Titan 7 LLC") == "titan7"
        assert manufacturer_name_canonical("Titan 7") == "titan7"
        assert manufacturer_name_canonical("Titan7") == "titan7"

    def test_punctuation_and_whitespace_collapse(self) -> None:
        """Punctuation and whitespace collapse in the canonical form."""
        assert manufacturer_name_canonical("A'PEX-i") == "apexi"
        assert manufacturer_name_canonical("APEXi") == "apexi"
        assert manufacturer_name_canonical("Apex-i") == "apexi"
        assert manufacturer_name_canonical("K&N") == "kn"
        assert manufacturer_name_canonical("KN") == "kn"
        assert manufacturer_name_canonical("Borg Warner") == "borgwarner"
        assert manufacturer_name_canonical("BorgWarner") == "borgwarner"
        assert manufacturer_name_canonical("Stop Tech") == "stoptech"
        assert manufacturer_name_canonical("StopTech") == "stoptech"
        assert manufacturer_name_canonical("Power Stop") == "powerstop"
        assert manufacturer_name_canonical("PowerStop") == "powerstop"

    def test_oem_naming_intentionally_distinct(self) -> None:
        """OEM names stay distinct rather than collapsing together."""
        assert manufacturer_name_canonical("BMW OEM") == "bmwoem"
        assert manufacturer_name_canonical("Genuine BMW") == "genuinebmw"
        assert manufacturer_name_canonical("Genuine BMW Motorsport") == "genuinebmw"


class TestCuratedPMResolution:
    """``get_or_create_part_manufacturer_by_name`` must route variant inputs
    to an existing canonical row instead of inserting a duplicate."""

    def _make_curated(self, db_session: Any, name: str) -> DBPartManufacturer:
        """Create an active curated manufacturer row with the given name."""
        pm = DBPartManufacturer(
            name=name,
            is_active=True,
        )
        pm = save_catalog(pm)
        return pm

    def test_exact_case_insensitive_match_wins(self, db_session: Any) -> None:
        """An exact case insensitive match resolves to the existing row."""
        canonical = self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name("apr")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_subdivision_resolves_to_parent_brand(self, db_session: Any) -> None:
        """A subdivision name resolves to the parent brand's row."""
        canonical = self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name("APR Performance")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_corporate_suffix_resolves_to_parent_brand(self, db_session: Any) -> None:
        """A name with a corporate suffix resolves to the parent brand's row."""
        canonical = self._make_curated(db_session, "Katech")
        resolved = get_or_create_part_manufacturer_by_name("Katech Engineering")
        assert resolved is not None
        assert resolved.id == canonical.id
        also = get_or_create_part_manufacturer_by_name("Katech Inc.")
        assert also is not None
        assert also.id == canonical.id

    def test_punctuation_variant_resolves(self, db_session: Any) -> None:
        """A punctuation variant resolves to the existing row."""
        canonical = self._make_curated(db_session, "Borg Warner")
        resolved = get_or_create_part_manufacturer_by_name("BorgWarner")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_unrelated_brand_creates_new_row(self, db_session: Any) -> None:
        """An unrelated brand creates a new row rather than resolving."""
        self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name("AEM")
        assert resolved is not None
        assert resolved.name == "AEM"

    def test_empty_input_returns_none(self, db_session: Any) -> None:
        """Empty input resolves to nothing."""
        assert get_or_create_part_manufacturer_by_name("") is None
        assert get_or_create_part_manufacturer_by_name("   ") is None
