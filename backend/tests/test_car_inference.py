"""Tests for car make/model/generation inference from part name and description."""

import pytest

from app.core.car_inference import infer_car_generations


class TestInferCarGenerations:
    """Test infer_car_generations returns expected (make, model, generation_name) triples."""

    def test_mkv_supra_a90(self) -> None:
        # MKV / GR Supra A90 aliases
        result = infer_car_generations(
            "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
            "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_supra_gr_a90_from_name(self) -> None:
        result = infer_car_generations("Remark Toyota Supra GR A90 Full Titanium Cat-Back Exhaust", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_a90_a91_phrase(self) -> None:
        result = infer_car_generations("KW 2 Way Clubsport Coilover Kit - MKV Supra A90 / A91", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_bmw_m4_g82(self) -> None:
        result = infer_car_generations(
            "FI Exhaust - BMW M4 G82 Valvetronic Catback Exhaust",
            "BMW G82 M4 Fi Exhaust.",
        )
        assert ("BMW", "M4", "G82/G83") in result

    def test_g82_phrase(self) -> None:
        result = infer_car_generations("Vorsteiner BMW G8X M3 | M4 Gloss Black Front Grille", "G82 M4.")
        assert ("BMW", "M4", "G82/G83") in result

    def test_empty_input(self) -> None:
        assert infer_car_generations("", "") == []
        assert infer_car_generations(None, None) == []
        assert infer_car_generations("  ", None) == []

    def test_no_match_returns_empty(self) -> None:
        result = infer_car_generations("Random Universal Part XYZ", "Fits many cars.")
        assert result == []

    def test_product_url_included_in_match(self) -> None:
        # URL might contain car hints in some retailers
        result = infer_car_generations(
            "Exhaust System",
            "High performance exhaust.",
            product_url="https://example.com/supra-a90-exhaust",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_word_boundary_short_code(self) -> None:
        # "A90" should not match inside unrelated tokens (e.g. "BA90" or "A901")
        result = infer_car_generations("Some Part BA90", "Description.")
        assert ("Toyota", "Supra", "A90") not in result
        result2 = infer_car_generations("Some Part A90 Supra", "Description.")
        assert ("Toyota", "Supra", "A90") in result2

    def test_civic_10th_gen(self) -> None:
        result = infer_car_generations("Honda Civic 10th Gen Cold Air Intake", None)
        assert ("Honda", "Civic", "10th Gen") in result

    def test_fk8_civic_type_r(self) -> None:
        result = infer_car_generations("FK8 Civic Type R Front Lip", "FK8 Type R.")
        assert ("Honda", "Civic Type R", "FK8") in result
