"""Unit tests for ``manufacturer_name_canonical`` and the canonical-key
fall-through path in ``_find_curated_pm_by_name`` / ``get_or_create_part_manufacturer_by_name``.

The canonical-key lookup is what backstops the Tier-1 manufacturer cleanup
migration (``080fc6916478``): once duplicate rows like ``"APR Performance"``
have been collapsed into ``"APR"``, an adapter that still emits ``"APR
Performance"`` must resolve to the existing ``"APR"`` row rather than
recreate the duplicate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.services.part_listing_service import (
    get_or_create_part_manufacturer_by_name,
    manufacturer_name_canonical,
)


class TestManufacturerNameCanonical:
    """The canonical key collapses casing, whitespace, punctuation, and a
    fixed set of trailing brand-suffix tokens (Performance, Tuning, Inc, etc.).
    """

    def test_empty_string_returns_empty(self) -> None:
        assert manufacturer_name_canonical("") == ""
        assert manufacturer_name_canonical("   ") == ""

    def test_brand_subdivision_collapses_to_parent(self) -> None:
        # The mandate clusters: ``APR Performance`` -> APR, ``AEM Electronics``
        # / ``AEM Induction`` -> AEM, ``PRL Motorsports`` -> PRL.
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
        # ``Katech Engineering`` / ``Katech Inc.`` -> ``katech``.
        assert manufacturer_name_canonical("Katech Engineering") == "katech"
        assert manufacturer_name_canonical("Katech Inc.") == "katech"
        assert manufacturer_name_canonical("Katech Inc") == "katech"
        assert manufacturer_name_canonical("Katech") == "katech"
        assert manufacturer_name_canonical("CSF Inc.") == "csf"
        assert manufacturer_name_canonical("CSF") == "csf"

    def test_iterative_trailing_token_strip(self) -> None:
        # ``Titan 7 LLC`` / ``Titan7`` -> ``titan7`` (LLC peeled off the tail).
        assert manufacturer_name_canonical("Titan 7 LLC") == "titan7"
        assert manufacturer_name_canonical("Titan 7") == "titan7"
        assert manufacturer_name_canonical("Titan7") == "titan7"

    def test_punctuation_and_whitespace_collapse(self) -> None:
        # Punctuation normalisation: apostrophes, hyphens, ampersands, spaces.
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
        # ``Genuine BMW`` and ``BMW OEM`` are NOT the same canonical key —
        # OEM-rename is a one-time migration step, not a runtime collapse.
        # Adapters going forward should emit ``<Make> OEM`` directly.
        assert manufacturer_name_canonical("BMW OEM") == "bmwoem"
        assert manufacturer_name_canonical("Genuine BMW") == "genuinebmw"
        assert manufacturer_name_canonical("Genuine BMW Motorsport") == "genuinebmw"


class TestCuratedPMResolution:
    """``get_or_create_part_manufacturer_by_name`` must route variant inputs
    to an existing canonical row instead of inserting a duplicate."""

    def _make_curated(self, db_session: Session, name: str) -> DBPartManufacturer:
        pm = DBPartManufacturer(
            name=name,
            is_active=True,
        )
        db_session.add(pm)
        db_session.flush()
        return pm

    def test_exact_case_insensitive_match_wins(self, db_session: Session) -> None:
        canonical = self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name(db_session, "apr")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_subdivision_resolves_to_parent_brand(self, db_session: Session) -> None:
        # Post-migration ``APR`` is the canonical row. An adapter still
        # emitting ``APR Performance`` must hit the existing row, not insert
        # a new one.
        canonical = self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name(db_session, "APR Performance")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_corporate_suffix_resolves_to_parent_brand(self, db_session: Session) -> None:
        canonical = self._make_curated(db_session, "Katech")
        resolved = get_or_create_part_manufacturer_by_name(db_session, "Katech Engineering")
        assert resolved is not None
        assert resolved.id == canonical.id
        also = get_or_create_part_manufacturer_by_name(db_session, "Katech Inc.")
        assert also is not None
        assert also.id == canonical.id

    def test_punctuation_variant_resolves(self, db_session: Session) -> None:
        canonical = self._make_curated(db_session, "Borg Warner")
        resolved = get_or_create_part_manufacturer_by_name(db_session, "BorgWarner")
        assert resolved is not None
        assert resolved.id == canonical.id

    def test_unrelated_brand_creates_new_row(self, db_session: Session) -> None:
        # Sanity: the canonical-key fallback must not accidentally collide
        # distinct brands that happen to share a prefix.
        self._make_curated(db_session, "APR")
        resolved = get_or_create_part_manufacturer_by_name(db_session, "AEM")
        assert resolved is not None
        assert resolved.name == "AEM"

    def test_empty_input_returns_none(self, db_session: Session) -> None:
        assert get_or_create_part_manufacturer_by_name(db_session, "") is None
        assert get_or_create_part_manufacturer_by_name(db_session, "   ") is None
