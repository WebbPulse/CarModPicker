"""Tests for engine-platform fallback inference (issue #1).

`infer_car_generations_via_engine` resolves titles that reference an engine
platform by name (e.g. "6.7L Cummins") to the OEM cars that came with that
engine. Designed to run as a fallback when the universal pipeline returns
no triples.
"""

from app.core.car_generations_data import CAR_GENERATIONS
from app.core.car_inference import (
    ENGINE_PLATFORMS,
    infer_car_generations_via_engine,
)


class TestEnginePlatformsLoad:
    def test_every_fitment_resolves_to_a_real_seed_entry(self) -> None:
        """The loader validates this at import; the test pins the contract.
        If a future seed change drops a model row that an engine fitment
        depends on, import will fail and so will this test."""
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
    def test_67_cummins_resolves_to_ram_hd_3rd_4th_5th_gen(self) -> None:
        triples = infer_car_generations_via_engine("6.7L Cummins Boost Pipe")
        assert ("Dodge", "Ram 2500", "3rd Gen") in triples
        assert ("Dodge", "Ram 2500", "4th Gen") in triples
        assert ("Dodge", "Ram 2500", "5th Gen") in triples
        assert ("Dodge", "Ram 3500", "3rd Gen") in triples
        # And not the 2nd Gen Ram (5.9L only).
        assert ("Dodge", "Ram 2500", "2nd Gen") not in triples

    def test_59_cummins_resolves_to_ram_hd_2nd_3rd_gen(self) -> None:
        triples = infer_car_generations_via_engine("BorgWarner S300GX 5.9L Cummins Turbo Upgrade")
        assert ("Dodge", "Ram 2500", "2nd Gen") in triples
        assert ("Dodge", "Ram 2500", "3rd Gen") in triples
        assert ("Dodge", "Ram 3500", "2nd Gen") in triples
        # Not 4th/5th Gen Ram (no 5.9L past MY2007.5).
        assert ("Dodge", "Ram 2500", "4th Gen") not in triples

    def test_61_hemi_resolves_to_srt8_lx_platform_lineup(self) -> None:
        triples = infer_car_generations_via_engine("6.1L HEMI Forged Pistons")
        assert ("Chrysler", "300", "LX") in triples
        assert ("Dodge", "Charger", "LX") in triples
        assert ("Dodge", "Challenger", "3rd Gen") in triples
        assert ("Dodge", "Magnum", "SRT-8") in triples
        assert ("Jeep", "Grand Cherokee", "WK") in triples
        # Not the LD-platform sedans (6.1L was LX-only).
        assert ("Chrysler", "300", "LD") not in triples
        assert ("Dodge", "Charger", "LD") not in triples

    def test_67_powerstroke_resolves_to_super_duty(self) -> None:
        triples = infer_car_generations_via_engine("6.7L Powerstroke Air-to-Water Intercooler")
        assert ("Ford", "F-Series Super Duty", "3rd Gen") in triples
        assert ("Ford", "F-Series Super Duty", "4th Gen") in triples
        assert ("Ford", "F-Series Super Duty", "5th Gen") in triples
        # Not the 2nd Gen (6.4L Powerstroke era) or 1st Gen (6.0L era).
        assert ("Ford", "F-Series Super Duty", "1st Gen") not in triples
        assert ("Ford", "F-Series Super Duty", "2nd Gen") not in triples

    def test_4g63_resolves_across_dsm_and_evo_lineup(self) -> None:
        triples = infer_car_generations_via_engine("4G63 Forged Connecting Rods")
        assert ("Mitsubishi", "Eclipse", "1st Gen") in triples
        assert ("Mitsubishi", "Eclipse", "2nd Gen") in triples
        assert ("Mitsubishi", "Lancer Evolution", "VIII") in triples
        assert ("Mitsubishi", "Lancer Evolution", "IX") in triples
        assert ("Plymouth", "Laser", "1G") in triples
        # Not Evo X (switched to 4B11T).
        assert ("Mitsubishi", "Lancer Evolution", "X") not in triples

    def test_no_engine_name_returns_empty(self) -> None:
        assert infer_car_generations_via_engine("Stainless Steel Pressure Washer Wand") == []

    def test_empty_input_returns_empty(self) -> None:
        assert infer_car_generations_via_engine("") == []
        assert infer_car_generations_via_engine(None) == []

    def test_multiple_engines_in_title_unions_fitments(self) -> None:
        """A title that mentions two engines with explicit phrases (each
        having its own surrounding context, not slash-separated) matches
        both and unions fitments. Slash-separated lists like
        "Hemi 5.7/6.1/6.4" only match the engine whose phrase is adjacent
        to "Hemi" — in that title only "Hemi 5.7" matches as a substring;
        6.1 and 6.4 are bracketed by slashes. Documenting that limitation
        here so future work on slash-list parsing has a baseline."""
        triples = infer_car_generations_via_engine("Forged rotating assembly fits 5.7L Hemi and 6.4L Hemi blocks")
        # 5.7L fitments
        assert ("Dodge", "Ram 1500", "3rd Gen") in triples
        # 6.4L fitments
        assert ("Dodge", "Durango", "SRT 392") in triples
        # Sanity: both engines contributed.
        assert ("Dodge", "Charger", "LD") in triples  # in both 5.7 and 6.4
        assert ("Jeep", "Grand Cherokee", "WK2") in triples  # 6.4 specifically

    def test_slash_separated_engine_list_only_matches_first_engine(self) -> None:
        """Document the slash-list limitation as a regression check.
        Title "Hemi 5.7/6.1/6.4" matches 5.7 (via "hemi 5.7" substring)
        but neither 6.1 nor 6.4 (no adjacent "hemi" token).
        If the resolver later gains slash-list awareness, this test should
        be updated to assert all three match."""
        triples = infer_car_generations_via_engine("550cc Injectors RT/SRT8 Hemi 5.7/6.1/6.4")
        assert ("Dodge", "Ram 1500", "3rd Gen") in triples  # 5.7L matched
        # 6.1L unique fitment NOT matched — slash before "6.1" breaks adjacency.
        assert ("Dodge", "Magnum", "SRT-8") not in triples  # 6.1L-only fitment
        assert ("Dodge", "Durango", "SRT 392") not in triples  # 6.4L unique — also not matched

    def test_description_field_is_consulted(self) -> None:
        """Some retailers put the engine in description, not name."""
        triples = infer_car_generations_via_engine("Forged Rods", description="Fits 6.4L Hemi (392) applications")
        assert ("Dodge", "Charger", "LD") in triples
