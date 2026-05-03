"""Tests for SKU extraction + junk-SKU rejection in crawler parsing helpers."""

from app.crawlers.parsing import (
    extract_sku_from_text,
    gtin_candidate_for_pn,
    is_junk_part_number,
    part_number_canonical,
)


class TestExtractSkuFromText:
    """extract_sku_from_text should only fire on explicit cue words, not any prose."""

    def test_plain_sku_colon(self) -> None:
        assert extract_sku_from_text("Specs. SKU: WGCR425MA2. Fits.") == "WGCR425MA2"

    def test_part_number_spelled_out(self) -> None:
        assert extract_sku_from_text("Details. Part Number: A14A10-1201.") == "A14A10-1201"

    def test_pn_abbrev(self) -> None:
        assert extract_sku_from_text("P/N: CSF8317 — high flow.") == "CSF8317"

    def test_part_hash(self) -> None:
        assert extract_sku_from_text("More info. Part #: FXXHHL / Red.") == "FXXHHL"

    def test_bare_part_does_not_match_partners(self) -> None:
        # Regression: bare "Part" in "partners" used to capture "ners" as a part number.
        assert extract_sku_from_text("Our partners ship worldwide.") is None

    def test_bare_part_alone_does_not_match(self) -> None:
        # Bare "Part" with no # / Number / No. should not be a SKU cue.
        assert extract_sku_from_text("This Part replaces the OEM unit.") is None

    def test_bare_item_does_not_match_items(self) -> None:
        assert extract_sku_from_text("Items ship fast.") is None

    def test_short_captured_value_rejected(self) -> None:
        # "Part #: CSF" — 3 chars, almost certainly a brand/word, not a SKU.
        assert extract_sku_from_text("Part #: CSF high-flow radiator") is None

    def test_empty_input(self) -> None:
        assert extract_sku_from_text("") is None
        assert extract_sku_from_text(None) is None  # type: ignore[arg-type]


class TestIsJunkPartNumber:
    """is_junk_part_number is the last-mile guard applied in ingest_payload."""

    def test_none_is_junk(self) -> None:
        assert is_junk_part_number(None, "CSF") is True

    def test_empty_is_junk(self) -> None:
        assert is_junk_part_number("", "CSF") is True
        assert is_junk_part_number("   ", "CSF") is True

    def test_short_alpha_only_is_junk(self) -> None:
        # Alpha-only ≤3 char tokens are almost always brand acronyms in the SKU slot.
        assert is_junk_part_number("CSF", "CSF") is True
        assert is_junk_part_number("ABC", "Some Brand") is True

    def test_short_numeric_is_real_sku(self) -> None:
        # Road Sport Supply / Girodisc / others ship real 3-digit catalog SKUs
        # like "326", "608", "302". A brand name cannot collide with a number,
        # so the short-length floor only applies to alpha-only tokens.
        assert is_junk_part_number("326", "RSS") is False
        assert is_junk_part_number("608", "Cargraphic") is False
        assert is_junk_part_number("B1", "Some Brand") is False  # alphanum
        assert is_junk_part_number("30", None) is False

    def test_equals_manufacturer_case_and_space_insensitive(self) -> None:
        # JSON-LD sometimes puts the brand where the SKU should go.
        assert is_junk_part_number("CSF Radiators", "CSF Radiators") is True
        assert is_junk_part_number("csfradiators", "CSF Radiators") is True
        assert is_junk_part_number("ADRO", "adro") is True

    def test_real_sku_passes(self) -> None:
        assert is_junk_part_number("CSF8317", "CSF") is False
        assert is_junk_part_number("A14A10-1201", "ADRO") is False
        assert is_junk_part_number("FXXHHL", "ADRO") is False

    def test_no_manufacturer_only_alpha_length_matters(self) -> None:
        assert is_junk_part_number("AB", None) is True  # alpha-only, < 4
        assert is_junk_part_number("ABCD", None) is False
        assert is_junk_part_number("12", None) is False  # numeric short OK

    def test_option_label_words_are_junk(self) -> None:
        # Pure-alpha option-label words ("FUEL", "SIZE", "TURBO", ...) leak from
        # Wix/Shopify variant dropdowns when the page's SKU field is empty —
        # see sheepeyrace and mackin-ind for concrete cases. Match is case-
        # insensitive.
        assert is_junk_part_number("FUEL", "Sheepey Race") is True
        assert is_junk_part_number("Fuel", "Sheepey Race") is True
        assert is_junk_part_number("TURBO", "Sheepey Race") is True
        assert is_junk_part_number("CORE", "Sheepey Race") is True
        assert is_junk_part_number("SIZE", "Mackin Industries") is True
        assert is_junk_part_number("PRODUCT", "Mackin Industries") is True
        assert is_junk_part_number("COLOR", "Mackin Industries") is True
        # Anything carrying a digit or hyphen passes — real SKUs in the same
        # neighborhood ("TURBO-2", "CORE-450") must not be rejected.
        assert is_junk_part_number("TURBO-2", "Sheepey Race") is False
        assert is_junk_part_number("CORE450", "Sheepey Race") is False

    def test_bundle_concatenation_is_junk(self) -> None:
        # > 40 chars carrying whitespace or ``+`` is a multi-product variant
        # string, not a SKU.
        with_space = "Stage1 Tune Map A + Stage2 Tune Map B + Stage3 Map"
        assert len(with_space) > 40
        assert is_junk_part_number(with_space, "COBB") is True

        with_plus = "AB-1234567890" + "+CD-1234567890" + "+EF-1234567890"
        assert len(with_plus) > 40
        assert is_junk_part_number(with_plus, "COBB") is True

        # A long token without separators is allowed through (ridiculously
        # long real SKUs are uncommon but legitimate manufacturer codes can
        # run 30-40 chars; we only catch the bundle-shape).
        long_unbroken = "A" * 50
        assert is_junk_part_number(long_unbroken, "COBB") is False

    def test_price_shape_is_junk(self) -> None:
        # ``offers.price`` mis-mapped onto ``sku``.
        assert is_junk_part_number("15109.14", "AEM") is True
        assert is_junk_part_number("99.95", "AEM") is True
        # Real SKUs that happen to contain a decimal still pass.
        assert is_junk_part_number("AEM30-2400", "AEM") is False

    def test_gtin_shape_is_junk(self) -> None:
        # 12/13 digit pure numeric belongs in the gtin column.
        assert is_junk_part_number("012345678901", "AEM") is True
        assert is_junk_part_number("0123456789012", "AEM") is True
        # 11 digits or 14 digits don't match GTIN shapes.
        assert is_junk_part_number("01234567890", "AEM") is False
        assert is_junk_part_number("01234567890123", "AEM") is False

    def test_make_token_leakage_is_junk(self) -> None:
        # Title-shape synthesized SKUs that embed a make token as a whole word.
        assert is_junk_part_number("Toyota-Supra-A91-Pure800", "Pure Turbos") is True
        assert is_junk_part_number("Subaru-WRX-STi-Tune", "COBB") is True
        assert is_junk_part_number("HONDA-Civic-FK8-Header", "PRL") is True
        # Substring inside a longer alphanumeric run is OK ("TOYO225",
        # "INFINITRONIC"). The match is word-boundary-scoped.
        assert is_junk_part_number("TOYO225", "Toyo Tires") is False
        assert is_junk_part_number("INFINITRONIC42", "Infinitronic") is False


class TestPartNumberCanonical:
    """``part_number_canonical`` is the dedup-key builder used by the linker."""

    def test_styling_drift_collapses(self) -> None:
        # Same code, three styling forms — all map to one canonical key.
        assert part_number_canonical("AEM-30-2400") == "AEM302400"
        assert part_number_canonical("aem 30/2400") == "AEM302400"
        assert part_number_canonical("AEM_30_2400") == "AEM302400"

    def test_empty_input_returns_none(self) -> None:
        assert part_number_canonical(None) is None
        assert part_number_canonical("") is None
        assert part_number_canonical("   ") is None

    def test_under_4_chars_returns_none(self) -> None:
        assert part_number_canonical("ab") is None
        assert part_number_canonical("X-1") is None  # collapses to "X1"
        assert part_number_canonical("abc") is None

    def test_4_chars_passes(self) -> None:
        assert part_number_canonical("A14A") == "A14A"
        assert part_number_canonical("a-1-4-a") == "A14A"

    def test_car_model_blacklist(self) -> None:
        # Z4M / E46 etc. land in the blacklist via the inner normalize.
        assert part_number_canonical("Z4M") is None
        assert part_number_canonical("E46") is None
        assert part_number_canonical("e92") is None

    def test_prefix_strip_then_canonicalize(self) -> None:
        # Inner normalize_part_number strips "SKU:" / "Part #:" prefixes; the
        # canonical form should reflect the post-strip code.
        assert part_number_canonical("SKU: AEM-30-2400") == "AEM302400"
        assert part_number_canonical("Part #: A14A10-1201") == "A14A101201"


class TestGtinCandidateForPn:
    """``gtin_candidate_for_pn`` promotes 12/13-digit pure-numeric values."""

    def test_upc_a_is_promoted(self) -> None:
        assert gtin_candidate_for_pn("012345678901") == "012345678901"

    def test_ean_13_is_promoted(self) -> None:
        assert gtin_candidate_for_pn("0123456789012") == "0123456789012"

    def test_non_numeric_is_not_promoted(self) -> None:
        assert gtin_candidate_for_pn("AEM-30-2400") is None
        assert gtin_candidate_for_pn("CSF8317") is None

    def test_wrong_length_is_not_promoted(self) -> None:
        assert gtin_candidate_for_pn("01234567890") is None  # 11
        assert gtin_candidate_for_pn("01234567890123") is None  # 14

    def test_empty_returns_none(self) -> None:
        assert gtin_candidate_for_pn(None) is None
        assert gtin_candidate_for_pn("") is None
        assert gtin_candidate_for_pn("   ") is None
