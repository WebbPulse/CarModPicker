"""
Tests for display_name sync in init_car_generations.

Verifies presentation-only display_name handling: code-owned, tri-state (absent/None
in source clears DB value), synced on both CarModel and CarGeneration create + update.
"""

from typing import Any
from unittest.mock import patch

import pytest

from app.core.car_generations_data import slugify
from app.core.init_cars import init_car_generations
from app.db.dynamo.catalog import (
    CarGeneration,
    CarGenerationRepository,
    CarMake,
    CarMakeRepository,
    CarModel,
    CarModelRepository,
)


def _fake_flattened(
    *,
    model: str = "Supra",
    model_slug: str | None = None,
    model_display_name: str | None = None,
    generation_name: str = "A80",
    generation_slug: str | None = None,
    display_name: str | None = None,
) -> list[dict[str, str | int | None]]:
    return [
        {
            "make": "Toyota",
            "model": model,
            "model_slug": model_slug if model_slug is not None else slugify(model),
            "model_display_name": model_display_name,
            "generation_name": generation_name,
            "generation_slug": generation_slug if generation_slug is not None else slugify(generation_name),
            "display_name": display_name,
            "start_year": 1993,
            "end_year": 2002,
        }
    ]


class _CatalogQuery:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def all(self) -> list[Any]:
        return self._repository.list_all()

    def one(self) -> Any:
        rows = self.all()
        assert len(rows) == 1, rows
        return rows[0]


class _Catalog:
    _repositories = {
        CarGeneration: CarGenerationRepository,
        CarModel: CarModelRepository,
        CarMake: CarMakeRepository,
    }

    def query(self, model: type) -> _CatalogQuery:
        return _CatalogQuery(self._repositories[model]())


@pytest.fixture
def clean_db(dynamo_tables: Any) -> _Catalog:
    return _Catalog()


class TestInitCarsDisplayName:
    def test_create_writes_generation_display_name(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(display_name="Mk4 Supra"),
        ):
            init_car_generations()

        gen = clean_db.query(CarGeneration).one()
        assert gen.display_name == "Mk4 Supra"

    def test_create_writes_model_display_name(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model_display_name="Supra (friendly)"),
        ):
            init_car_generations()

        model = clean_db.query(CarModel).one()
        assert model.display_name == "Supra (friendly)"

    def test_update_changes_generation_display_name(self, clean_db: _Catalog) -> None:
        # First pass: create with an initial display_name
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(display_name="OldName"),
        ):
            init_car_generations()

        # Second pass: source now has a different display_name
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(display_name="Mk4 Supra"),
        ):
            init_car_generations()

        gen = clean_db.query(CarGeneration).one()
        assert gen.display_name == "Mk4 Supra"

    def test_removing_generation_display_name_clears_db_value(self, clean_db: _Catalog) -> None:
        """Tri-state: source dropping display_name must clear the stale DB value."""
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(display_name="Mk4 Supra"),
        ):
            init_car_generations()

        # Second pass: source no longer sets display_name (None, simulating key removal)
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(display_name=None),
        ):
            init_car_generations()

        gen = clean_db.query(CarGeneration).one()
        assert gen.display_name is None

    def test_removing_model_display_name_clears_db_value(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model_display_name="Supra (friendly)"),
        ):
            init_car_generations()

        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model_display_name=None),
        ):
            init_car_generations()

        model = clean_db.query(CarModel).one()
        assert model.display_name is None

    def test_model_display_name_updated_when_changed(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model_display_name="Original"),
        ):
            init_car_generations()

        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model_display_name="Updated"),
        ):
            init_car_generations()

        model = clean_db.query(CarModel).one()
        assert model.display_name == "Updated"

    def test_display_name_defaults_to_null_when_not_in_source(self, clean_db: _Catalog) -> None:
        """A source row with no display_name field creates a row with NULL display_name."""
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(),
        ):
            init_car_generations()

        gen = clean_db.query(CarGeneration).one()
        model = clean_db.query(CarModel).one()
        assert gen.display_name is None
        assert model.display_name is None


class TestInitCarsSlugLookup:
    """Slug is the stable lookup key; `name` / `generation_name` are synced fields that follow."""

    def test_model_slug_defaults_to_slugify_name(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model="GR Supra"),
        ):
            init_car_generations()

        model = clean_db.query(CarModel).one()
        assert model.slug == "gr-supra"
        assert model.name == "GR Supra"

    def test_generation_slug_defaults_to_slugify_generation_name(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(generation_name="RX-7 FD"),
        ):
            init_car_generations()

        gen = clean_db.query(CarGeneration).one()
        assert gen.slug == "rx-7-fd"

    def test_renaming_model_name_with_pinned_slug_updates_in_place(self, clean_db: _Catalog) -> None:
        """Pinning slug lets seed renames mutate the existing row's `name` instead of creating a duplicate."""
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model="Supra"),
        ):
            init_car_generations()

        original = clean_db.query(CarModel).one()
        original_id = original.id
        assert original.slug == "supra"
        assert original.name == "Supra"

        # Rename "Supra" → "GR Supra" in seed, pin slug to preserve identity.
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model="GR Supra", model_slug="supra"),
        ):
            init_car_generations()

        # Same row (id stable), name updated, slug unchanged.
        models = clean_db.query(CarModel).all()
        assert len(models) == 1
        assert models[0].id == original_id
        assert models[0].slug == "supra"
        assert models[0].name == "GR Supra"

    def test_renaming_generation_name_with_pinned_slug_updates_in_place(self, clean_db: _Catalog) -> None:
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(generation_name="A80"),
        ):
            init_car_generations()

        original = clean_db.query(CarGeneration).one()
        original_id = original.id

        # Rename engineering code in seed, pin slug to the old form.
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(generation_name="A80 (JZA80)", generation_slug="a80"),
        ):
            init_car_generations()

        gens = clean_db.query(CarGeneration).all()
        assert len(gens) == 1
        assert gens[0].id == original_id
        assert gens[0].slug == "a80"
        assert gens[0].generation_name == "A80 (JZA80)"

    def test_renaming_without_pinned_slug_creates_new_row(self, clean_db: _Catalog) -> None:
        """Documents the invariant: without a pinned slug, a rename is treated as a new entity."""
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model="Supra"),
        ):
            init_car_generations()

        # Rename without pinning slug. slugify("GR Supra") = "gr-supra" ≠ "supra" → new row.
        with patch(
            "app.core.init_cars.get_all_car_generations",
            return_value=_fake_flattened(model="GR Supra"),
        ):
            init_car_generations()

        models = clean_db.query(CarModel).all()
        slugs = {m.slug for m in models}
        assert slugs == {"supra", "gr-supra"}

    def test_double_init_is_idempotent(self, clean_db: _Catalog) -> None:
        """Running init twice leaves row ids and counts unchanged."""
        source = _fake_flattened(display_name="Mk4 Supra", model_display_name="Supra (friendly)")
        with patch("app.core.init_cars.get_all_car_generations", return_value=source):
            init_car_generations()
            first_model_id = clean_db.query(CarModel).one().id
            first_gen_id = clean_db.query(CarGeneration).one().id

            init_car_generations()
            assert clean_db.query(CarModel).one().id == first_model_id
            assert clean_db.query(CarGeneration).one().id == first_gen_id
