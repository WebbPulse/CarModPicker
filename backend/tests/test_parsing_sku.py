"""Tests for SKU extraction + junk-SKU rejection in crawler parsing helpers."""

from app.crawlers.parsing import extract_sku_from_text, is_junk_part_number


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
