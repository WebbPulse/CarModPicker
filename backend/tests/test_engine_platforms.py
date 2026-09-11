"""Tests for engine-platform fallback inference.

Titles naming an engine platform resolve to the OEM cars that carried it.
"""

from app.core.car_generations_data import CAR_GENERATIONS
from app.core.car_inference import (
    ENGINE_PLATFORMS,
    infer_car_generations_via_engine,
)


class TestEnginePlatformsLoad:
    """The engine platform table agrees with the car generation seed data."""

    def test_every_fitment_resolves_to_a_real_seed_entry(self) -> None:
        """Every engine fitment names a make, model and generation that exist in the seed."""
        for engine_name, payload in ENGINE_PLATFORMS.items():
            for fitment in payload.get("fitments", []):
                make = fitment["make"]
                model = fitment["model"]
                gen_name = fitment["gen_name"]
                models = CAR_GENERATIONS.get(make)
                assert models is not None, f"{engine_name}: unknown make {make}"
                model_entry = next((m for m in models if m["model"] == model), None)
                assert model_entry is not None, f"{engine_name}: unknown ({make}, {model})"
                assert any(
                    g["generation_name"] == gen_name for g in model_entry["generations"]
                ), f"{engine_name}: unknown ({make}, {model}, {gen_name})"


class TestInferCarGenerationsViaEngine:
    """Title and description resolution through the engine platform table."""

    def test_67_cummins_resolves_to_ram_hd_3rd_4th_5th_gen(self) -> None:
        """A 6.7L Cummins title resolves to the Ram HD generations that carried it."""
        triples = infer_car_generations_via_engine("6.7L Cummins Boost Pipe")
        assert ("Dodge", "Ram 2500", "3rd Gen") in triples
        assert ("Dodge", "Ram 2500", "4th Gen") in triples
        assert ("Dodge", "Ram 2500", "5th Gen") in triples
        assert ("Dodge", "Ram 3500", "3rd Gen") in triples
        assert ("Dodge", "Ram 2500", "2nd Gen") not in triples

    def test_59_cummins_resolves_to_ram_hd_2nd_3rd_gen(self) -> None:
        """A 5.9L Cummins title resolves to the earlier Ram HD generations only."""
        triples = infer_car_generations_via_engine("BorgWarner S300GX 5.9L Cummins Turbo Upgrade")
        assert ("Dodge", "Ram 2500", "2nd Gen") in triples
        assert ("Dodge", "Ram 2500", "3rd Gen") in triples
        assert ("Dodge", "Ram 3500", "2nd Gen") in triples
        assert ("Dodge", "Ram 2500", "4th Gen") not in triples

    def test_61_hemi_resolves_to_srt8_lx_platform_lineup(self) -> None:
        """A 6.1L HEMI title resolves to the SRT8 LX lineup and not to later platforms."""
        triples = infer_car_generations_via_engine("6.1L HEMI Forged Pistons")
        assert ("Chrysler", "300", "LX") in triples
        assert ("Dodge", "Charger", "LX") in triples
        assert ("Dodge", "Challenger", "3rd Gen") in triples
        assert ("Dodge", "Magnum", "SRT-8") in triples
        assert ("Jeep", "Grand Cherokee", "WK") in triples
        assert ("Chrysler", "300", "LD") not in triples
        assert ("Dodge", "Charger", "LD") not in triples

    def test_67_powerstroke_resolves_to_super_duty(self) -> None:
        """A 6.7L Powerstroke title resolves to the Super Duty generations that carried it."""
        triples = infer_car_generations_via_engine("6.7L Powerstroke Air-to-Water Intercooler")
        assert ("Ford", "F-Series Super Duty", "3rd Gen") in triples
        assert ("Ford", "F-Series Super Duty", "4th Gen") in triples
        assert ("Ford", "F-Series Super Duty", "5th Gen") in triples
        assert ("Ford", "F-Series Super Duty", "1st Gen") not in triples
        assert ("Ford", "F-Series Super Duty", "2nd Gen") not in triples

    def test_4g63_resolves_across_dsm_and_evo_lineup(self) -> None:
        """A 4G63 title resolves across the DSM and Evolution lineup."""
        triples = infer_car_generations_via_engine("4G63 Forged Connecting Rods")
        assert ("Mitsubishi", "Eclipse", "1st Gen") in triples
        assert ("Mitsubishi", "Eclipse", "2nd Gen") in triples
        assert ("Mitsubishi", "Lancer Evolution", "VIII") in triples
        assert ("Mitsubishi", "Lancer Evolution", "IX") in triples
        assert ("Plymouth", "Laser", "1G") in triples
        assert ("Mitsubishi", "Lancer Evolution", "X") not in triples

    def test_no_engine_name_returns_empty(self) -> None:
        """A title with no engine name resolves to nothing."""
        assert infer_car_generations_via_engine("Stainless Steel Pressure Washer Wand") == []

    def test_empty_input_returns_empty(self) -> None:
        """Empty and missing input resolve to nothing."""
        assert infer_car_generations_via_engine("") == []
        assert infer_car_generations_via_engine(None) == []

    def test_multiple_engines_in_title_unions_fitments(self) -> None:
        """Two engines named in their own phrases union their fitments."""
        triples = infer_car_generations_via_engine("Forged rotating assembly fits 5.7L Hemi and 6.4L Hemi blocks")
        assert ("Dodge", "Ram 1500", "3rd Gen") in triples
        assert ("Dodge", "Durango", "SRT 392") in triples
        assert ("Dodge", "Charger", "LD") in triples
        assert ("Jeep", "Grand Cherokee", "WK2") in triples

    def test_slash_separated_engine_list_only_matches_first_engine(self) -> None:
        """A slash-separated engine list matches only the engine adjacent to the platform word."""
        triples = infer_car_generations_via_engine("550cc Injectors RT/SRT8 Hemi 5.7/6.1/6.4")
        assert ("Dodge", "Ram 1500", "3rd Gen") in triples
        assert ("Dodge", "Magnum", "SRT-8") not in triples
        assert ("Dodge", "Durango", "SRT 392") not in triples

    def test_description_field_is_consulted(self) -> None:
        """The description is searched too, since some retailers put the engine there."""
        triples = infer_car_generations_via_engine("Forged Rods", description="Fits 6.4L Hemi (392) applications")
        assert ("Dodge", "Charger", "LD") in triples
