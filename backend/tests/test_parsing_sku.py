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

    def test_shorter_than_four_chars(self) -> None:
        assert is_junk_part_number("CSF", "CSF") is True
        assert is_junk_part_number("ABC", "Some Brand") is True

    def test_equals_manufacturer_case_and_space_insensitive(self) -> None:
        # JSON-LD sometimes puts the brand where the SKU should go.
        assert is_junk_part_number("CSF Radiators", "CSF Radiators") is True
        assert is_junk_part_number("csfradiators", "CSF Radiators") is True
        assert is_junk_part_number("ADRO", "adro") is True

    def test_real_sku_passes(self) -> None:
        assert is_junk_part_number("CSF8317", "CSF") is False
        assert is_junk_part_number("A14A10-1201", "ADRO") is False
        assert is_junk_part_number("FXXHHL", "ADRO") is False

    def test_no_manufacturer_only_length_matters(self) -> None:
        assert is_junk_part_number("AB", None) is True
        assert is_junk_part_number("ABCD", None) is False
