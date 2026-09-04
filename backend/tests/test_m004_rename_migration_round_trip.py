"""Postgres-gated round-trip test for an emitted M004 rename migration.

Skipped automatically when ``POSTGRES_TEST_URL`` is unset (per the
``@pytest.mark.postgres`` convention).

What this asserts:

* Render an emit_rename migration body.
* Stage a ``car_generations`` row with the OLD ``generation_name``.
* Execute the migration's ``upgrade()`` (a single
  ``op.execute(sa.text("UPDATE car_generations SET generation_name = :new ..."))``
  call) inside an alembic ``EnvironmentContext`` bound to a real Postgres
  connection.
* Re-read the row: ``id`` preserved, ``generation_name`` is the NEW form.
* Execute ``downgrade()``.
* Re-read: ``generation_name`` is back to the OLD form.

Why exec the migration directly rather than driving ``alembic upgrade``: the
emitter writes a plain Python module whose ``upgrade()``/``downgrade()`` use
``op.execute()``, and we want to exercise *that body* end-to-end without
mutating the project's real ``alembic/versions/`` directory inside a test.
The alembic ``MigrationContext`` is bound to the live SQLAlchemy connection
so ``op`` resolves correctly at module-import time.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# Ensure backend/ is on sys.path for `import scripts.m004_emit_rename`.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts import m004_emit_rename as emit  # noqa: E402

pytestmark = pytest.mark.postgres


def _load_module_from_source(source: str, module_name: str) -> object:
    """Compile + import a Python module from a source string."""
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, f"<{module_name}>", "exec"), module.__dict__)  # nosec B102 — controlled test source
    sys.modules[module_name] = module
    return module


@pytest.fixture
def round_trip_seed(postgres_engine: "Engine"):
    """Insert one car_generations row and return its id + the unique slug used.

    Cleans up the row after the test (regardless of whether the migration body
    completed). Uses a per-worker, per-test unique slug so concurrent xdist
    workers cannot collide (per the WARN 8 convention in ``conftest.py``).
    """
    from app.db.dynamo.catalog import CarGeneration, CarMake, CarModel

    worker = sys.modules.get("xdist", None)
    unique = uuid.uuid4().hex[:12]
    make_name = f"M004RT-Make-{unique}"
    model_name = f"M004RT-Model-{unique}"
    model_slug = f"m004rt-model-{unique}"
    gen_slug = f"m004rt-gen-{unique}"
    old_name = "OLD-A80"

    with postgres_engine.begin() as conn:
        make_id = conn.execute(
            sa.insert(CarMake.__table__).values(name=make_name).returning(CarMake.__table__.c.id)
        ).scalar_one()
        model_id = conn.execute(
            sa.insert(CarModel.__table__)
            .values(car_make_id=make_id, slug=model_slug, name=model_name)
            .returning(CarModel.__table__.c.id)
        ).scalar_one()
        gen_id = conn.execute(
            sa.insert(CarGeneration.__table__)
            .values(
                car_model_id=model_id,
                slug=gen_slug,
                generation_name=old_name,
                start_year=1993,
                end_year=2002,
            )
            .returning(CarGeneration.__table__.c.id)
        ).scalar_one()

    yield {"gen_id": gen_id, "old_name": old_name}

    with postgres_engine.begin() as conn:
        conn.execute(sa.delete(CarGeneration.__table__).where(CarGeneration.__table__.c.id == gen_id))
        conn.execute(sa.delete(CarModel.__table__).where(CarModel.__table__.c.id == model_id))
        conn.execute(sa.delete(CarMake.__table__).where(CarMake.__table__.c.id == make_id))


def test_emitted_rename_migration_round_trip_preserves_row_id(
    postgres_engine: "Engine", round_trip_seed: dict[str, Any]
) -> None:
    from app.db.dynamo.catalog import CarGeneration

    gen_id = round_trip_seed["gen_id"]
    assert isinstance(gen_id, uuid.UUID)
    old_name = str(round_trip_seed["old_name"])
    new_name = "NEW-A80 (JZA80)"

    decision = emit.Decision(
        canonical_id=gen_id,
        old_generation_name=old_name,
        new_generation_name=new_name,
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    body = emit.render_migration(
        new_revision="rt0000000001",
        down_revision="rt0000000000",
        decision=decision,
        audit_source="round-trip-test",
        decided_at="2026-04-27 00:00:00.000000",
    )

    module = _load_module_from_source(body, "m004_rt_test_migration")

    # Sanity: docstring carries the audit-trail tuple.
    assert module.__doc__ is not None
    assert "round-trip-test" in module.__doc__
    assert "corpus_count     = 12" in module.__doc__

    with postgres_engine.connect() as conn:
        with conn.begin():
            ctx = MigrationContext.configure(conn)
            # Bind alembic.op to OUR connection's Operations for the duration of
            # the upgrade()/downgrade() calls. Alembic's `op` proxy resolves
            # against the most-recent Operations.context().
            with Operations.context(ctx):
                module.upgrade()  # type: ignore[attr-defined]

            row = conn.execute(
                sa.select(CarGeneration.__table__.c.id, CarGeneration.__table__.c.generation_name).where(
                    CarGeneration.__table__.c.id == gen_id
                )
            ).one()
            assert row.id == gen_id
            assert row.generation_name == new_name

            with Operations.context(ctx):
                module.downgrade()  # type: ignore[attr-defined]

            row = conn.execute(
                sa.select(CarGeneration.__table__.c.id, CarGeneration.__table__.c.generation_name).where(
                    CarGeneration.__table__.c.id == gen_id
                )
            ).one()
            assert row.id == gen_id
            assert row.generation_name == old_name
