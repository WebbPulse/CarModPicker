"""
Unit tests for the ``category_to_subslug`` bridge that translates DB category
names (the output of ``app.core.category_inference.infer_category``) to
SpecRegistry sub-slugs.

These tests pin the contract that:

* ``"suspension"`` resolves to ``"coilover"`` only when a coilover keyword
  appears in name/description.
* ``"engine"`` resolves to ``"turbo"`` only when a turbo keyword appears in
  name/description.
* ``"brakes"`` always resolves to ``"brake"`` (single sub-slug under brakes).
* Any other non-None category name (or suspension/engine without the
  disambiguating keyword) falls through to ``"universal"`` so the
  UniversalSpec validation fires for the long tail.
* ``category_name is None`` returns ``None`` so the ingest hook can preserve
  S01 pass-through.

For every non-None resolution, the resulting slug must resolve via
``default_registry.resolve()`` to a CategorySpec subclass. That round-trip
keeps the bridge honest: a slug the bridge can return must always be one the
registry knows about.

T05 will extend this file with a deeper coverage matrix; T03 lands the
verification minimum that the bridge contract holds.
"""

from __future__ import annotations

import pytest

from app.crawlers.specs import default_registry
from app.crawlers.specs.base import CategorySpec
from app.crawlers.specs.category_bridge import (
    UNIVERSAL_SUBSLUG,
    category_to_subslug,
)


class TestCategoryToSubslugMapping:
    """Branch-by-branch coverage of the bridge contract."""

    def test_none_category_returns_none(self) -> None:
        # Pass-through preserves S01 behaviour for payloads where infer_category
        # returns None (no name/description).
        assert category_to_subslug(None) is None
        assert category_to_subslug(None, name="anything", description="anything") is None

    def test_empty_category_returns_none(self) -> None:
        # Empty / whitespace-only string is treated as "no category at all".
        assert category_to_subslug("") is None
        assert category_to_subslug("   ") is None

    def test_suspension_with_coilover_keyword_resolves_to_coilover(self) -> None:
        assert (
            category_to_subslug(
                "suspension",
                name="ST X35 Coilovers",
                description="Adjustable coilover suspension.",
            )
            == "coilover"
        )

    def test_suspension_with_coil_over_variant_resolves_to_coilover(self) -> None:
        # Hyphen / space variants must all bridge so adapter-supplied prose
        # doesn't sneak past the gate.
        assert (
            category_to_subslug(
                "suspension",
                name="Premium Coil-Over Kit",
            )
            == "coilover"
        )
        assert (
            category_to_subslug(
                "suspension",
                description="Coil over damper rebuild.",
            )
            == "coilover"
        )

    def test_suspension_without_coilover_keyword_falls_through_to_universal(
        self,
    ) -> None:
        # "Strut" parts under suspension don't have a sub-slug yet — universal
        # is the right answer so the validation hook still fires on universal
        # fields like weight_grams.
        assert (
            category_to_subslug(
                "suspension",
                name="Bilstein B6 Strut",
                description="Monotube strut, replacement OEM fitment.",
            )
            == UNIVERSAL_SUBSLUG
        )

    def test_brakes_always_resolves_to_brake(self) -> None:
        # Single sub-slug under brakes today; no keyword check.
        assert category_to_subslug("brakes") == "brake"
        assert (
            category_to_subslug(
                "brakes",
                name="Big Brake Kit",
                description="Front BBK with 6-piston calipers.",
            )
            == "brake"
        )

    def test_engine_with_turbo_keyword_resolves_to_turbo(self) -> None:
        assert (
            category_to_subslug(
                "engine",
                name="K04 Turbo Upgrade",
                description="Hybrid turbo with billet wheel.",
            )
            == "turbo"
        )
        assert (
            category_to_subslug(
                "engine",
                name="Replacement Turbocharger",
            )
            == "turbo"
        )

    def test_engine_without_turbo_keyword_falls_through_to_universal(self) -> None:
        # Cold-air intake under engine has no sub-slug yet.
        assert (
            category_to_subslug(
                "engine",
                name="Cold Air Intake",
                description="High-flow CAI for naturally aspirated engines.",
            )
            == UNIVERSAL_SUBSLUG
        )

    def test_other_categories_fall_through_to_universal(self) -> None:
        # No DB category outside suspension/engine/brakes has a registered
        # sub-slug yet — every one must bridge to universal so the hook fires.
        for category in ("wheels", "exhaust", "body", "interior", "lighting", "drivetrain", "other"):
            assert (
                category_to_subslug(category, name="Sample Part", description="")
                == UNIVERSAL_SUBSLUG
            ), f"category={category!r} should resolve to universal"

    def test_keyword_in_wrong_parent_does_not_hijack_subslug(self) -> None:
        # A coilover keyword in a wheels-categorized part must NOT resolve to
        # the coilover sub-slug — the parent category gates the bridge so the
        # wrong schema can't be picked up by stray prose.
        assert (
            category_to_subslug(
                "wheels",
                name="Wheel Spacer with Coilover Compatibility Note",
            )
            == UNIVERSAL_SUBSLUG
        )
        assert (
            category_to_subslug(
                "exhaust",
                name="Turbo-back Exhaust System",
            )
            == UNIVERSAL_SUBSLUG
        )


class TestBridgeRoundTripsWithRegistry:
    """Every non-None bridge result must resolve to a CategorySpec subclass."""

    @pytest.mark.parametrize(
        "category_name, name, description, expected_subslug",
        [
            ("suspension", "ST X35 Coilovers", None, "coilover"),
            ("brakes", "Big Brake Kit", None, "brake"),
            ("engine", "K04 Turbo", None, "turbo"),
            ("wheels", "Forged Wheel Set", None, UNIVERSAL_SUBSLUG),
            ("exhaust", "Catback Exhaust", None, UNIVERSAL_SUBSLUG),
            ("suspension", "Generic Strut", None, UNIVERSAL_SUBSLUG),
        ],
    )
    def test_resolved_subslug_is_in_default_registry(
        self,
        category_name: str,
        name: str,
        description: str | None,
        expected_subslug: str,
    ) -> None:
        subslug = category_to_subslug(category_name, name=name, description=description)
        assert subslug == expected_subslug
        spec_model = default_registry.resolve(subslug)
        assert spec_model is not None, (
            f"Bridge produced subslug {subslug!r} but default_registry has no model for it. "
            f"Either register a model under that slug or stop returning it from the bridge."
        )
        assert issubclass(spec_model, CategorySpec)
