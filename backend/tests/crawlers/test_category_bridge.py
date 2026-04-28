"""
Contract tests for ``app.crawlers.specs.category_bridge.category_to_subslug``.

Locks in the DB-category-name → SpecRegistry-sub-slug mapping the ingest hook
relies on to find a concrete spec model for a payload. Three buckets covered:

  (a) ``category_name is None`` → ``None`` (caller skips validation entirely)
  (b) Single-sub-slug parents (``"brakes"`` / ``"wheels"``) resolve unconditionally
  (c) Keyword-gated parents (``"suspension"`` / ``"engine"``) resolve only when
      the disambiguating keyword is present in name/description; otherwise
      they fall through to the universal catch-all
  (d) Non-mapped DB categories fall through to ``"universal"``

The M004/S06 wheel-bridge addition is the primary driver for this module
existing — `test_category_bridge.py` did not exist before S06.
"""

from __future__ import annotations

from app.crawlers.specs.category_bridge import (
    UNIVERSAL_SUBSLUG,
    category_to_subslug,
)


class TestNoneCategoryPassesThrough:
    def test_none_category_returns_none(self) -> None:
        # Caller skips validation entirely when infer_category returned None.
        assert category_to_subslug(None) is None
        assert category_to_subslug(None, name="anything", description="anything") is None

    def test_empty_string_category_returns_none(self) -> None:
        assert category_to_subslug("") is None
        assert category_to_subslug("   ") is None


class TestSingleSubslugCategories:
    def test_brakes_resolves_unconditionally(self) -> None:
        # No keyword in name/description needed.
        assert category_to_subslug("brakes") == "brake"
        assert category_to_subslug("brakes", name="", description="") == "brake"

    def test_wheels_resolves_unconditionally_to_wheel(self) -> None:
        # M004/S06: wheels → wheel. Mirrors brakes → brake.
        assert (
            category_to_subslug("wheels", name="Volk Racing TE37 18x9.5 5x114.3", description="")
            == "wheel"
        )
        # Even with no name/description hint, parent alone resolves.
        assert category_to_subslug("wheels") == "wheel"

    def test_wheels_case_insensitive(self) -> None:
        assert category_to_subslug("WHEELS") == "wheel"
        assert category_to_subslug("Wheels") == "wheel"


class TestKeywordGatedSubslugs:
    def test_suspension_with_coilover_keyword_resolves_to_coilover(self) -> None:
        result = category_to_subslug(
            "suspension",
            name="Premium Coilover Kit",
            description="Adjustable damper.",
        )
        assert result == "coilover"

    def test_suspension_without_coilover_keyword_falls_through_to_universal(self) -> None:
        # Sway bar text — no coilover keyword — falls through to universal.
        result = category_to_subslug(
            "suspension",
            name="Performance Sway Bar",
            description="Adjustable sway bar end links.",
        )
        assert result == UNIVERSAL_SUBSLUG

    def test_engine_with_turbo_keyword_resolves_to_turbo(self) -> None:
        result = category_to_subslug(
            "engine",
            name="GT2860RS Turbocharger",
            description="Ball-bearing turbo.",
        )
        assert result == "turbo"


class TestNonWheelsParentsDoNotAccidentallyResolveToWheel:
    """The wheels-bridge addition must not leak across parent categories.

    A non-`wheels` parent that mentions wheels-related text in its description
    must NOT resolve to ``"wheel"``. Single-sub-slug resolution is keyed on the
    parent category name only.
    """

    def test_suspension_with_wheel_text_does_not_resolve_to_wheel(self) -> None:
        result = category_to_subslug(
            "suspension",
            name="Coilover for 18x9.5 wheel setup",
            description="Suspension kit suited for wheel-and-tire upgrades.",
        )
        # Coilover keyword wins → coilover, NOT wheel.
        assert result == "coilover"

    def test_engine_with_wheel_text_does_not_resolve_to_wheel(self) -> None:
        result = category_to_subslug(
            "engine",
            name="Intake manifold for 18-inch wheel cars",
            description="Engine intake.",
        )
        # No turbo keyword, parent is engine, falls through to universal.
        assert result == UNIVERSAL_SUBSLUG

    def test_other_parent_with_wheel_text_falls_through_to_universal(self) -> None:
        result = category_to_subslug(
            "exterior",
            name="Wheel-arch flares",
            description="Plastic flares for wheels.",
        )
        assert result == UNIVERSAL_SUBSLUG


class TestUnmappedCategoryFallsThroughToUniversal:
    def test_unmapped_category_returns_universal(self) -> None:
        # Any non-None DB category that doesn't match a mapping → universal.
        assert category_to_subslug("interior") == UNIVERSAL_SUBSLUG
        assert category_to_subslug("electrical") == UNIVERSAL_SUBSLUG
