"""
Contract tests for the SpecRegistry and per-category CategorySpec subclasses.

Three goals per concrete spec (CoiloverSpec, BrakeSpec, TurboSpec):
  (a) ``default_registry.resolve('<slug>')`` returns the expected concrete class
  (b) the class accepts a representative valid payload via ``model_validate``
  (c) the class rejects malformed payloads (extra='forbid' violation, type
      coercion failure, or invalid Literal value) with ``pydantic.ValidationError``

Plus a top-level test that ``default_registry.resolve('unknown_slug')`` returns
``None`` so the ingest pass-through path stays trustworthy.

These tests lock in the M002/S01 schema contract: any future change that
breaks resolution, valid-payload acceptance, or extra-field rejection will
fail here at suite collection / run time before reaching downstream slices.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.crawlers.specs import (
    BrakeSpec,
    CoiloverSpec,
    TurboSpec,
    default_registry,
)


def test_unknown_slug_resolves_to_none() -> None:
    """Unregistered slugs return None — ingest pass-through depends on this."""
    assert default_registry.resolve("unknown_slug") is None
    assert default_registry.resolve("") is None


class TestCoiloverSpec:
    SLUG = "coilover"

    def test_registry_resolves_to_coilover_spec(self) -> None:
        assert default_registry.resolve(self.SLUG) is CoiloverSpec

    def test_accepts_valid_payload(self) -> None:
        payload = {
            "spring_rate_front": 600.0,
            "spring_rate_front_confidence": "high",
            "spring_rate_rear": 700.0,
            "damper_adjustability": "rebound-and-compression",
            "height_adjustable": True,
        }
        validated = CoiloverSpec.model_validate(payload)
        assert validated.spring_rate_front == 600.0
        assert validated.damper_adjustability == "rebound-and-compression"
        assert validated.height_adjustable is True

    def test_accepts_empty_payload(self) -> None:
        # All fields are Optional → empty dict is a valid spec.
        validated = CoiloverSpec.model_validate({})
        assert validated.model_dump(exclude_none=True) == {}

    def test_rejects_unknown_field_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"unknown_field": 1})

    def test_rejects_invalid_literal_for_damper_adjustability(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"damper_adjustability": "magic"})

    def test_rejects_non_numeric_spring_rate(self) -> None:
        with pytest.raises(ValidationError):
            CoiloverSpec.model_validate({"spring_rate_front": "not-a-number"})


class TestBrakeSpec:
    SLUG = "brake"

    def test_registry_resolves_to_brake_spec(self) -> None:
        assert default_registry.resolve(self.SLUG) is BrakeSpec

    def test_accepts_valid_payload(self) -> None:
        payload = {
            "rotor_diameter_mm": 380.0,
            "rotor_diameter_mm_confidence": "high",
            "pad_compound": "RS19",
            "piston_count": 6,
            "vented": True,
        }
        validated = BrakeSpec.model_validate(payload)
        assert validated.rotor_diameter_mm == 380.0
        assert validated.piston_count == 6
        assert validated.vented is True

    def test_rejects_unknown_field_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            BrakeSpec.model_validate({"bogus_extra": "x"})

    def test_rejects_non_integer_piston_count(self) -> None:
        # piston_count is Optional[int]; a non-coercible string must error.
        with pytest.raises(ValidationError):
            BrakeSpec.model_validate({"piston_count": "many"})

    def test_rejects_invalid_confidence_literal(self) -> None:
        with pytest.raises(ValidationError):
            BrakeSpec.model_validate({"vented_confidence": "extreme"})


class TestTurboSpec:
    SLUG = "turbo"

    def test_registry_resolves_to_turbo_spec(self) -> None:
        assert default_registry.resolve(self.SLUG) is TurboSpec

    def test_accepts_valid_payload(self) -> None:
        payload = {
            "compressor_wheel_mm": 67.0,
            "turbine_wheel_mm": 60.0,
            "journal_or_bb": "ballbearing",
            "housing_ar": 0.82,
            "housing_ar_confidence": "medium",
        }
        validated = TurboSpec.model_validate(payload)
        assert validated.compressor_wheel_mm == 67.0
        assert validated.journal_or_bb == "ballbearing"
        assert validated.housing_ar == 0.82

    def test_rejects_unknown_field_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"random_key": 1})

    def test_rejects_invalid_journal_or_bb_literal(self) -> None:
        # journal_or_bb is Literal['journal', 'ballbearing'] — anything else fails.
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"journal_or_bb": "magnetic"})

    def test_rejects_non_numeric_housing_ar(self) -> None:
        with pytest.raises(ValidationError):
            TurboSpec.model_validate({"housing_ar": "very-big"})
