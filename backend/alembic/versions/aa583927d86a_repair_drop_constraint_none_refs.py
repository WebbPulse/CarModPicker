"""repair invalid drop_constraint(None) — see SAFE-08

Revision ID: aa583927d86a
Revises: 5971a893dd8e
Create Date: 2026-04-22 00:52:00.175697

Three legacy migrations contain drop_constraint(None, ...) calls with a None constraint name
in their downgrade() blocks:
  - 097024200e60_add_canonical_part_id_to_parts.py (line 33) — parts
  - 172d1c205fb3_add_build_list_phases.py (line 45)        — build_list_parts
  - 6eae6b1393c5_add_brand_model.py (line 48)              — global_parts (now parts)

With None as the constraint name, Alembic cannot resolve which FK to drop, so
`alembic downgrade` through any of these revisions fails hard. Because these
revisions are already applied on prod, we cannot rewrite history — the FIX is
a new forward-only migration whose upgrade() is a no-op (schema is already
correct) and whose downgrade() performs the three properly-named drops.

The constraint names below were obtained by introspecting prod (see SAFE-08
Task 1 output in the PR description). At the time this repair migration's
downgrade() runs, the DB is at the current HEAD state (all rename migrations
including d2e9c4a1f57b and c1f3e8a92d45 are still applied), so the third
constraint from 6eae6b1393c5 lives on the renamed table 'parts' under its
renamed constraint 'parts_part_manufacturer_id_fkey'.

SAFE-08 introspection (run 2026-04-22):
- prod alembic_version: confirmed at head (>= 5971a893dd8e)
- 097024200e60 applied on prod: YES
- 172d1c205fb3 applied on prod: YES
- 6eae6b1393c5 applied on prod: YES
- Chosen branch: B (forward-only repair)
- parts.canonical_part_id FK name: parts_canonical_part_id_fkey
- build_list_parts.build_list_phase_id FK name: build_list_parts_build_list_phase_id_fkey
- global_parts.brand_id (renamed to parts.part_manufacturer_id) FK name: parts_part_manufacturer_id_fkey

This file is a documented exception to CLAUDE.md's "Alembic autogenerate only"
rule (C-01): autogenerate cannot express a no-op upgrade paired with a named
downgrade. Generated via `alembic revision --autogenerate` to obtain the
correct revision chain, then body hand-authored.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa583927d86a"
down_revision: Union[str, None] = "5971a893dd8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op forward: current prod schema is already correct."""
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    pass


def downgrade() -> None:
    """Drop the three FKs that the legacy migrations should have named.

    At downgrade time (DB is at current HEAD minus this repair migration):
      - parts_canonical_part_id_fkey exists on table 'parts'
      - build_list_parts_build_list_phase_id_fkey exists on table 'build_list_parts'
      - parts_part_manufacturer_id_fkey exists on table 'parts'
        (originally global_parts.brand_id FK, renamed via c1f3e8a92d45 + d2e9c4a1f57b)
    """
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint("parts_canonical_part_id_fkey", "parts", type_="foreignkey")
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint(
        "build_list_parts_build_list_phase_id_fkey",
        "build_list_parts",
        type_="foreignkey",
    )
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint("parts_part_manufacturer_id_fkey", "parts", type_="foreignkey")
