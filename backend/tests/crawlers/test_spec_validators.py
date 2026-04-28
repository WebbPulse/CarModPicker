"""
Per-validator tests for the M004/S05 ``@field_validator(mode='before')`` coercion
on ``CategorySpec`` (five universal fields) and per-category specs
(``CoiloverSpec``, ``BrakeSpec``, ``TurboSpec``).

Coverage matrix:
  - 1 happy-path test per validator (10 total): canonical numeric/typed input
    pass-through AND a coercion-trigger string both produce the canonical
    typed value.
  - 1 negative test per validator (10 total): unrecognizable input raises
    ``pydantic.ValidationError`` (drop-to-None path at ingest, MEM015).
  - 1 inheritance test: ``CategorySpec`` validators fire when validating a
    subclass instance (Pydantic v2 documented behavior).
  - 1 ``extra='forbid'`` regression test: validator output preserves the
    no-extra-keys contract that the spec layer was built around.

These tests are intentionally separated from
``test_spec_registry_contract.py`` (registry+payload acceptance) and
``test_ingest_spec_validation.py`` (ingest fail-soft behaviour) so a future
validator regression surfaces in a single, focused module.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.crawlers.specs.brake import BrakeSpec
from app.crawlers.specs.coilover import CoiloverSpec
from app.crawlers.specs.turbo import TurboSpec
from app.crawlers.specs.universal import UniversalSpec
from app.crawlers.specs.wheel import WheelSpec


# ---------------------------------------------------------------------------
# Universal-field validators (declared on CategorySpec, exercised here via
# UniversalSpec — the catch-all subclass that adds no fields of its own).
# ---------------------------------------------------------------------------


class TestUniversalValidators:
    def test_weight_grams_numeric_passthrough_and_string_coercion(self) -> None:
        # numeric pass-through
        assert UniversalSpec.model_validate({"weight_grams": 1500.0}).weight_grams == 1500.0
        # string → grams via shared unit table (1.5 kg = 1500 g)
        assert UniversalSpec.model_validate({"weight_grams": "1.5 kg"}).weight_grams == 1500.0
        # bare numeric string passes through float-cast
        assert UniversalSpec.model_validate({"weight_grams": "1500"}).weight_grams == 1500.0

    def test_weight_grams_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"weight_grams": "5 stone"})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"weight_grams": "heavy"})

    def test_material_lowercase_strip_collapse(self) -> None:
        # Title Case → lowercase
        assert UniversalSpec.model_validate({"material": "Stainless Steel"}).material == "stainless steel"
        # leading/trailing whitespace + internal multi-space → collapsed
        assert UniversalSpec.model_validate({"material": "  Carbon   Fiber  "}).material == "carbon fiber"

    def test_material_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"material": "   "})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"material": ["nope"]})

    def test_finish_lowercase_strip_collapse(self) -> None:
        assert UniversalSpec.model_validate({"finish": "Anodized Black"}).finish == "anodized black"
        assert UniversalSpec.model_validate({"finish": "  Powder   Coated  "}).finish == "powder coated"

    def test_finish_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"finish": ""})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"finish": 42})

    def test_warranty_days_numeric_and_string_units(self) -> None:
        # numeric pass-through
        assert UniversalSpec.model_validate({"warranty_days": 730.5}).warranty_days == 730.5
        # 'lifetime' literal → 36500 (matches T03 extractor sentinel)
        assert UniversalSpec.model_validate({"warranty_days": "lifetime"}).warranty_days == 36500.0
        # 30 days → 30 days
        assert UniversalSpec.model_validate({"warranty_days": "30 days"}).warranty_days == 30.0
        # 3 years uses the same factor as the parsing.py extractor (365.25)
        result = UniversalSpec.model_validate({"warranty_days": "3 years"}).warranty_days
        assert result == pytest.approx(3 * 365.25)
        # 6 months uses 30.44 (matches parsing.py)
        result = UniversalSpec.model_validate({"warranty_days": "6 months"}).warranty_days
        assert result == pytest.approx(6 * 30.44)

    def test_warranty_days_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"warranty_days": "forever"})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"warranty_days": "5 fortnights"})

    def test_fitment_notes_strip_collapse_and_cap(self) -> None:
        # internal whitespace collapse
        assert (
            UniversalSpec.model_validate({"fitment_notes": "Fits   E46\n M3 only"}).fitment_notes
            == "Fits E46 M3 only"
        )
        # 500-char cap: 600-char input truncates to 500
        capped = UniversalSpec.model_validate({"fitment_notes": "x" * 600}).fitment_notes
        assert capped is not None
        assert len(capped) == 500

    def test_fitment_notes_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"fitment_notes": ""})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"fitment_notes": ["a"]})

    def test_manufacturer_part_number_strip_collapse_uppercase(self) -> None:
        # whitespace-collapse + upper-case canonicalization (matches T03 extractor)
        assert (
            UniversalSpec.model_validate({"manufacturer_part_number": "  abc-123  "}).manufacturer_part_number
            == "ABC-123"
        )
        # internal multi-space collapses to single space then uppercases
        assert (
            UniversalSpec.model_validate({"manufacturer_part_number": "kw   12345"}).manufacturer_part_number
            == "KW 12345"
        )

    def test_manufacturer_part_number_unrecognizable_raises(self) -> None:
        # non-str raises
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"manufacturer_part_number": 12345})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"manufacturer_part_number": ["abc"]})
        # empty-after-strip raises
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"manufacturer_part_number": "   "})
        with pytest.raises(ValidationError):
            UniversalSpec.model_validate({"manufacturer_part_number": ""})


# ---------------------------------------------------------------------------
# CoiloverSpec validators.
# ---------------------------------------------------------------------------


class TestCoiloverValidators:
    def test_spring_rate_front_numeric_and_string_lb_in(self) -> None:
        # numeric pass-through
        assert CoiloverSpec.model_validate({"spring_rate_front": 600.0}).spring_rate_front == 600.0
        # lb/in suffix is identity (the canonical unit)
        assert CoiloverSpec.model_validate({"spring_rate_front": "600 lb/in"}).spring_rate_front == 600.0
        # lbf/in is also identity
        assert CoiloverSpec.model_validate({"spring_rate_front": "650 lbf/in"}).spring_rate_front == 650.0

    def test_spring_rate_front_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"spring_rate_front": "stiff"})
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"spring_rate_front": "600 g/mm"})

    def test_spring_rate_rear_kg_per_mm_conversion(self) -> None:
        # 10 kg/mm = 559.97 lb/in (per the spec's standard JDM conversion)
        result = CoiloverSpec.model_validate({"spring_rate_rear": "10 kg/mm"}).spring_rate_rear
        assert result == pytest.approx(559.97)
        # bare number passes through
        assert CoiloverSpec.model_validate({"spring_rate_rear": "550"}).spring_rate_rear == 550.0

    def test_spring_rate_rear_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"spring_rate_rear": "very stiff"})
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"spring_rate_rear": "10 N/mm"})

    def test_damper_adjustability_canonical_passthrough_and_coercion(self) -> None:
        # Existing canonical Literal — pass-through
        assert (
            CoiloverSpec.model_validate({"damper_adjustability": "rebound-only"}).damper_adjustability
            == "rebound-only"
        )
        # Free-form coercion variants
        assert (
            CoiloverSpec.model_validate({"damper_adjustability": "single adjustable"}).damper_adjustability
            == "rebound-only"
        )
        assert (
            CoiloverSpec.model_validate({"damper_adjustability": "2-way adjustable"}).damper_adjustability
            == "rebound-and-compression"
        )
        assert (
            CoiloverSpec.model_validate({"damper_adjustability": "Rebound and Compression"}).damper_adjustability
            == "rebound-and-compression"
        )
        assert (
            CoiloverSpec.model_validate({"damper_adjustability": "Fixed"}).damper_adjustability
            == "non-adjustable"
        )

    def test_damper_adjustability_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"damper_adjustability": "magical"})
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"damper_adjustability": 42})


# ---------------------------------------------------------------------------
# BrakeSpec validator.
# ---------------------------------------------------------------------------


class TestBrakeValidators:
    def test_rotor_diameter_mm_numeric_and_inch_conversion(self) -> None:
        # numeric pass-through
        assert BrakeSpec.model_validate({"rotor_diameter_mm": 355.0}).rotor_diameter_mm == 355.0
        # mm suffix is identity
        assert BrakeSpec.model_validate({"rotor_diameter_mm": "355 mm"}).rotor_diameter_mm == 355.0
        # inch → mm (× 25.4)
        result = BrakeSpec.model_validate({"rotor_diameter_mm": "14 inch"}).rotor_diameter_mm
        assert result == pytest.approx(355.6)
        # bare number passes through
        assert BrakeSpec.model_validate({"rotor_diameter_mm": "330"}).rotor_diameter_mm == 330.0

    def test_rotor_diameter_mm_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            BrakeSpec.model_validate({"rotor_diameter_mm": "big"})
        with pytest.raises(ValidationError):
            BrakeSpec.model_validate({"rotor_diameter_mm": "330 cm"})


# ---------------------------------------------------------------------------
# TurboSpec validators.
# ---------------------------------------------------------------------------


class TestTurboValidators:
    def test_compressor_wheel_mm_numeric_and_inch_conversion(self) -> None:
        assert TurboSpec.model_validate({"compressor_wheel_mm": 62.0}).compressor_wheel_mm == 62.0
        assert TurboSpec.model_validate({"compressor_wheel_mm": "62 mm"}).compressor_wheel_mm == 62.0
        result = TurboSpec.model_validate({"compressor_wheel_mm": "2.5 inch"}).compressor_wheel_mm
        assert result == pytest.approx(63.5)

    def test_compressor_wheel_mm_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"compressor_wheel_mm": "huge"})
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"compressor_wheel_mm": "62 cm"})

    def test_turbine_wheel_mm_numeric_and_inch_conversion(self) -> None:
        assert TurboSpec.model_validate({"turbine_wheel_mm": 70.0}).turbine_wheel_mm == 70.0
        assert TurboSpec.model_validate({"turbine_wheel_mm": "70 mm"}).turbine_wheel_mm == 70.0
        result = TurboSpec.model_validate({"turbine_wheel_mm": "2 inch"}).turbine_wheel_mm
        assert result == pytest.approx(50.8)

    def test_turbine_wheel_mm_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"turbine_wheel_mm": "spinny"})
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"turbine_wheel_mm": "70 ft"})

    def test_journal_or_bb_canonical_and_coercion(self) -> None:
        # Existing canonical Literal — pass-through
        assert TurboSpec.model_validate({"journal_or_bb": "journal"}).journal_or_bb == "journal"
        assert TurboSpec.model_validate({"journal_or_bb": "ballbearing"}).journal_or_bb == "ballbearing"
        # Free-form coercion variants
        assert TurboSpec.model_validate({"journal_or_bb": "ball bearing"}).journal_or_bb == "ballbearing"
        assert TurboSpec.model_validate({"journal_or_bb": "Ball-Bearing"}).journal_or_bb == "ballbearing"
        assert TurboSpec.model_validate({"journal_or_bb": "journal bearing"}).journal_or_bb == "journal"
        assert TurboSpec.model_validate({"journal_or_bb": "BB"}).journal_or_bb == "ballbearing"

    def test_journal_or_bb_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"journal_or_bb": "roller bearing"})
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"journal_or_bb": ["ballbearing"]})


# ---------------------------------------------------------------------------
# WheelSpec validators (M004/S06).
# ---------------------------------------------------------------------------


class TestWheelValidators:
    def test_diameter_inches_numeric_passthrough(self) -> None:
        assert WheelSpec.model_validate({"diameter_inches": 18.0}).diameter_inches == 18.0
        assert WheelSpec.model_validate({"diameter_inches": 19}).diameter_inches == 19.0

    def test_diameter_inches_strips_inch_suffix(self) -> None:
        assert WheelSpec.model_validate({"diameter_inches": "18 in"}).diameter_inches == 18.0
        assert WheelSpec.model_validate({"diameter_inches": "19 inch"}).diameter_inches == 19.0
        assert WheelSpec.model_validate({"diameter_inches": "20 inches"}).diameter_inches == 20.0
        assert WheelSpec.model_validate({"diameter_inches": '18"'}).diameter_inches == 18.0
        # bare numeric string passes through
        assert WheelSpec.model_validate({"diameter_inches": "17"}).diameter_inches == 17.0

    def test_diameter_inches_none_passes_through(self) -> None:
        assert WheelSpec.model_validate({"diameter_inches": None}).diameter_inches is None

    def test_diameter_inches_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"diameter_inches": "huge"})
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"diameter_inches": "18 cm"})
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"diameter_inches": []})

    def test_width_inches_happy_paths(self) -> None:
        assert WheelSpec.model_validate({"width_inches": 8.5}).width_inches == 8.5
        assert WheelSpec.model_validate({"width_inches": '8.5"'}).width_inches == 8.5
        assert WheelSpec.model_validate({"width_inches": "9 inch"}).width_inches == 9.0
        assert WheelSpec.model_validate({"width_inches": None}).width_inches is None

    def test_width_inches_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"width_inches": "wide"})
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"width_inches": "8.5 cm"})

    def test_offset_mm_numeric_passthrough(self) -> None:
        assert WheelSpec.model_validate({"offset_mm": 35}).offset_mm == 35
        assert WheelSpec.model_validate({"offset_mm": -12}).offset_mm == -12
        # float rounds to int
        assert WheelSpec.model_validate({"offset_mm": 35.4}).offset_mm == 35
        assert WheelSpec.model_validate({"offset_mm": 35.6}).offset_mm == 36

    def test_offset_mm_signed_string_with_unit(self) -> None:
        assert WheelSpec.model_validate({"offset_mm": "+45mm"}).offset_mm == 45
        assert WheelSpec.model_validate({"offset_mm": "-12 mm"}).offset_mm == -12
        assert WheelSpec.model_validate({"offset_mm": "20"}).offset_mm == 20
        assert WheelSpec.model_validate({"offset_mm": None}).offset_mm is None

    def test_offset_mm_unrecognizable_raises(self) -> None:
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"offset_mm": "low"})
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"offset_mm": "20 cm"})
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"offset_mm": "12.5"})  # decimal not accepted

    def test_bolt_pattern_canonicalizes(self) -> None:
        # Identity case (already canonical).
        assert WheelSpec.model_validate({"bolt_pattern": "5x114.3"}).bolt_pattern == "5x114.3"
        # Whitespace-tolerant.
        assert WheelSpec.model_validate({"bolt_pattern": "5 x 114.3"}).bolt_pattern == "5x114.3"
        # Asterisk separator canonicalizes to 'x'.
        assert WheelSpec.model_validate({"bolt_pattern": "4*100"}).bolt_pattern == "4x100"
        # Capital X separator canonicalizes to 'x'.
        assert WheelSpec.model_validate({"bolt_pattern": "4X100"}).bolt_pattern == "4x100"
        # Leading zero strips.
        assert WheelSpec.model_validate({"bolt_pattern": "05x100"}).bolt_pattern == "5x100"

    def test_bolt_pattern_none_passes_through(self) -> None:
        assert WheelSpec.model_validate({"bolt_pattern": None}).bolt_pattern is None

    def test_bolt_pattern_unrecognizable_raises(self) -> None:
        # bad shape
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"bolt_pattern": "five-by-one-fourteen"})
        # empty
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"bolt_pattern": ""})
        # missing pcd
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"bolt_pattern": "5x"})
        # non-string raises
        with pytest.raises(ValidationError):
            WheelSpec.model_validate({"bolt_pattern": 5})


# ---------------------------------------------------------------------------
# Cross-class behavior.
# ---------------------------------------------------------------------------


class TestValidatorInheritance:
    """CategorySpec validators must fire on every concrete subclass — Pydantic
    v2 docs guarantee this for fields declared on a parent class. This test
    pins the contract so a future refactor that accidentally shadows the
    declarations (e.g. by re-declaring weight_grams on a subclass) trips
    here before it reaches the ingest path."""

    def test_weight_grams_validator_fires_on_coilover_subclass(self) -> None:
        # String-with-unit reaches CoiloverSpec and is coerced via the
        # CategorySpec.weight_grams validator declared on the parent.
        result = CoiloverSpec.model_validate({"weight_grams": "1 kg"}).weight_grams
        assert result == 1000.0

    def test_material_validator_fires_on_brake_subclass(self) -> None:
        result = BrakeSpec.model_validate({"material": "Stainless Steel"}).material
        assert result == "stainless steel"

    def test_warranty_validator_fires_on_turbo_subclass(self) -> None:
        # 'lifetime' string reaches TurboSpec and is coerced via the
        # CategorySpec.warranty_days validator declared on the parent.
        result = TurboSpec.model_validate({"warranty_days": "lifetime"}).warranty_days
        assert result == 36500.0


class TestExtraForbidRegression:
    """Validators that return a coerced value must NOT introduce new keys —
    ``extra='forbid'`` on CategorySpec would raise ValidationError if any
    validator were to leak unintended attributes back into the model."""

    def test_validator_output_preserves_no_extra_keys(self) -> None:
        # Canonical valid payload still passes (the spec was already accepting
        # this shape via test_spec_registry_contract; this test pins that the
        # before-validator additions did NOT accidentally produce extras).
        spec = CoiloverSpec.model_validate(
            {
                "weight_grams": "1 kg",  # triggers CategorySpec validator
                "material": "Steel",  # triggers CategorySpec validator
                "spring_rate_front": "600 lb/in",  # triggers CoiloverSpec validator
                "damper_adjustability": "rebound only",  # triggers CoiloverSpec validator
            }
        )
        # Dump and confirm the only keys present are the declared field names —
        # no validator-leaked extras.
        dumped = spec.model_dump(exclude_none=True)
        declared = set(CoiloverSpec.model_fields.keys())
        assert set(dumped.keys()).issubset(declared)
        assert dumped["weight_grams"] == 1000.0
        assert dumped["material"] == "steel"
        assert dumped["spring_rate_front"] == 600.0
        assert dumped["damper_adjustability"] == "rebound-only"

    def test_unknown_extra_key_still_rejected(self) -> None:
        # The before-validator additions must NOT relax extra='forbid'.
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate(
                {"spring_rate_front": 600.0, "frob_nub": "no"}
            )
