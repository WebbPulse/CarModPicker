"""purge inference FP attributions

Tier-1 data-quality cleanup (2026-05-02), companion to the
``car_inference.py`` slash-split tightening shipped in the same commit.

The pre-fix ``_build_phrase_triples`` was splitting gen_name strings on ``/``
and emitting 1-2 char standalone phrases that matched English words and SKU
fragments inside product titles. The audit measured ~62% of attributed parts
(11,658 of 18,648) as carrying at least one false-positive attribution. The
worst offenders, by absolute attribution count:

  * ``BE``/``BH``  -> Subaru Legacy / Legacy GT BE/BH    (~6,448 parts)
  * ``7``/``8``    -> BMW Z3 / Z3 M E36/7 / E36/8        (~3,000 parts)
  * ``Turbo``      -> Dodge Daytona Turbo/Shelby         (~2,900 parts)
  * ``R``          -> Dodge Stealth R/T Turbo            (~2,080 parts)
  * ``V1``         -> Volvo S40 / V40 V1                 (~456 parts)

This migration deletes the part_cars rows that point at those generations.
Going forward the inference rules block the standalone-phrase emission, so
re-crawls cannot re-attribute these false positives.

Idempotent: re-running is a no-op once the rows are gone (DELETE WHERE on a
zero-row match is a no-op).

Dialect-safe: uses a portable ``DELETE FROM part_cars WHERE car_id IN (SELECT
... FROM car_generations JOIN ...)`` pattern. Both PostgreSQL and SQLite
support correlated/subquery-based DELETEs in this form.

Downgrade is a no-op: the original part->car attributions cannot be
reconstructed from the migration's perspective (we only know which were FPs
in aggregate, not which specific rows were correct vs. incorrect). Re-running
the crawler is the correct way to repopulate legitimate (non-FP) attributions
for the affected generations.

Revision ID: 12546c6ae607
Revises: f99b709f371a
Create Date: 2026-05-02 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12546c6ae607"
down_revision: Union[str, None] = "d1a4f7c2e8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (make_name, [model_names], [generation_names]) tuples for the worst Tier-1
# false-positive lineages. Keyed by (make, model, gen_name) text — portable
# across environments where car_generations.id values differ.
_FP_LINEAGES: list[tuple[str, list[str], list[str]]] = [
    # Subaru Legacy / Legacy GT BE/BH
    ("Subaru", ["Legacy", "Legacy GT"], ["BE/BH"]),
    # Dodge Daytona Turbo/Shelby
    ("Dodge", ["Daytona"], ["Turbo/Shelby"]),
    # Dodge Stealth R/T Turbo
    ("Dodge", ["Stealth"], ["R/T Turbo"]),
    # BMW Z3 / Z3 M E36/7 / E36/8 (and the combined "E36/7 E36/8" gen_name)
    ("BMW", ["Z3", "Z3 M"], ["E36/7", "E36/8", "E36/7 E36/8"]),
    # Volvo S40 / V40 V1
    ("Volvo", ["S40", "V40"], ["V1"]),
]


def _make_in_clause(values: list[str]) -> str:
    """Render a list of strings as an SQL IN-clause (single-quoted, comma-joined).

    Values come exclusively from the ``_FP_LINEAGES`` literal above (no user
    input), so straight quoting is safe and avoids dialect-specific bind-param
    handling inside ``op.execute``.
    """
    quoted = [f"'{v.replace(chr(39), chr(39) + chr(39))}'" for v in values]
    return "(" + ", ".join(quoted) + ")"


def upgrade() -> None:
    """Delete part_cars rows pointing at the worst Tier-1 FP generations.

    Each DELETE is keyed by (car_makes.name, car_models.name,
    car_generations.generation_name) so the migration is portable across
    environments that have different car_generations.id values for the same
    logical row.
    """
    for make_name, model_names, gen_names in _FP_LINEAGES:
        models_in = _make_in_clause(model_names)
        gens_in = _make_in_clause(gen_names)
        # Subquery form is supported by both PostgreSQL and SQLite.
        # car_generations.car_model_id -> car_models.id -> car_makes.id chain.
        op.execute(
            f"""
            DELETE FROM part_cars
            WHERE car_id IN (
                SELECT cg.id
                FROM car_generations cg
                JOIN car_models cmd ON cg.car_model_id = cmd.id
                JOIN car_makes cm ON cmd.car_make_id = cm.id
                WHERE cm.name = '{make_name}'
                  AND cmd.name IN {models_in}
                  AND cg.generation_name IN {gens_in}
            )
            """
        )


def downgrade() -> None:
    """No-op: the original part->car attributions were a mix of true and false
    positives, and we cannot reliably distinguish them from this side of the
    cleanup. Re-running the crawler is the correct way to repopulate
    legitimate (non-FP) attributions for the affected generations."""
    # Intentionally empty.
    pass
