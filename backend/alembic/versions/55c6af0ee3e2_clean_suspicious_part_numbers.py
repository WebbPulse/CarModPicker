"""null-out / GTIN-promote suspicious part_numbers

Tier-3 Item #7 cleanup half. The runtime now rejects four shapes through
``is_junk_part_number`` and the ingest helper promotes 12/13-digit pure-
numeric values into ``gtin``; this migration applies the same rules
retroactively to data that was already in the table.

Suspicious shapes this migration acts on:

  1. Bundle/list leakage: ``LENGTH > 40`` AND containing whitespace or ``+``
     ("Item A + Item B + Item C" written into the SKU slot from a multi-
     product variant string).
  2. Price-shape: bare ``\\d+\\.\\d{2}`` ("15109.14"), a stringified price.
  3. GTIN-shape: 12- or 13-digit pure numeric (UPC-A / EAN-13). When the
     row's ``gtin`` is null, the value is moved there; otherwise the
     ``part_number`` is nulled out.
  4. Make-token leakage: contains a whole-word car-make token (toyota,
     subaru, honda, ...). Title-shape synthesized SKUs land here.

Idempotent: re-running on an already-cleaned DB is a no-op (each rule's
WHERE clause filters to rows that still match the suspicious shape, and
once acted on the row no longer matches). Dialect-safe: uses
SQLAlchemy Core through ``op.get_bind()`` so the same code runs on
Postgres prod and the SQLite test suite. Make-token regex matching is
done in Python rather than via DB-side regex since SQLite stock has no
``REGEXP`` operator.

Revision ID: 55c6af0ee3e2
Revises: ca6ecd06b88c
Create Date: 2026-05-02 23:35:00.000000

"""

import re
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "55c6af0ee3e2"
down_revision: Union[str, None] = "ca6ecd06b88c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PRICE_SHAPE_RE = re.compile(r"^\d+\.\d{2}$")
_GTIN_SHAPE_RE = re.compile(r"^\d{12,13}$")
_MAKE_TOKENS = (
    "toyota", "subaru", "honda", "nissan", "ford", "chevrolet", "chevy",
    "mazda", "bmw", "audi", "porsche", "mitsubishi", "lexus", "infiniti",
    "acura", "volkswagen", "vw", "hyundai", "kia", "genesis", "tesla",
)
_MAKE_TOKEN_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_MAKE_TOKENS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_LENGTH_CAP = 40


def upgrade() -> None:
    """Walk every row with a non-null part_number and apply the four
    rules. The whole batch fits in one read pass + one update per match;
    on a multi-million-row prod table this is still cheap because the
    write only touches the ~few-percent of rows that actually match.
    """
    bind = op.get_bind()
    parts = sa.table(
        "parts",
        sa.column("id", sa.Uuid()),
        sa.column("part_number", sa.String()),
        sa.column("part_number_normalized", sa.String()),
        sa.column("gtin", sa.String()),
    )

    rows = bind.execute(
        sa.select(parts.c.id, parts.c.part_number, parts.c.gtin).where(
            parts.c.part_number.isnot(None)
        )
    ).all()

    for row in rows:
        raw = (row.part_number or "").strip()
        if not raw:
            continue

        # Rule 1: bundle/list leakage.
        if len(raw) > _LENGTH_CAP and (
            any(c.isspace() for c in raw) or "+" in raw
        ):
            bind.execute(
                sa.update(parts)
                .where(parts.c.id == row.id)
                .values(part_number=None, part_number_normalized=None)
            )
            continue

        # Rule 2: price-shape ("15109.14").
        if _PRICE_SHAPE_RE.match(raw):
            bind.execute(
                sa.update(parts)
                .where(parts.c.id == row.id)
                .values(part_number=None, part_number_normalized=None)
            )
            continue

        # Rule 3: GTIN shape (12/13 pure-numeric). Promote when gtin slot
        # is empty; otherwise just null out the part_number.
        if _GTIN_SHAPE_RE.match(raw):
            if not (row.gtin and row.gtin.strip()):
                bind.execute(
                    sa.update(parts)
                    .where(parts.c.id == row.id)
                    .values(part_number=None, part_number_normalized=None, gtin=raw)
                )
            else:
                bind.execute(
                    sa.update(parts)
                    .where(parts.c.id == row.id)
                    .values(part_number=None, part_number_normalized=None)
                )
            continue

        # Rule 4: contains a make token as a whole word.
        if _MAKE_TOKEN_RE.search(raw):
            bind.execute(
                sa.update(parts)
                .where(parts.c.id == row.id)
                .values(part_number=None, part_number_normalized=None)
            )
            continue


def downgrade() -> None:
    """No-op: the original junk strings can't be reconstructed from the
    nulled state, and re-introducing them would only re-pollute the
    canonical-link key. The runtime guard in ``is_junk_part_number``
    keeps re-ingest from re-importing them."""
    pass
