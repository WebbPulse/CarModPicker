"""strip junk image urls from parts.image_urls (data-only cleanup)

Revision ID: ea29b2450841
Revises: f99b709f371a
Create Date: 2026-05-03 05:20:39.090880

Tier-2 audit Item #4 follow-up. The crawler adapters were leaking junk
URLs into ``parts.image_urls``:

  - studiorsr Shopify spinner placeholders (``loading.svg``,
    ``/cdn/shop/t/<theme>/assets/...``, ``studiorsr_dark``, plus any other
    ``.svg`` chrome).
  - cobbtuning generic AccessPort beauty-shots
    (``accessport_v3_(extra|main|subaru|ford|bmw|volkswagen|mazda)``)
    leaking onto non-AP3 SKUs.
  - forgeline marketing template renders
    (``forgelinevehicletailoredimage*``,
    ``forgelinecustomfinishingimage*``).
  - hksusa logo fallback (``hks_logo`` / ``hksusa_logo``) when the CMS has
    no real product photo.
  - apr generic ECU-tune box render (``apr-ecu-box.png``).
  - bcracing catalog hero placeholders (``BR_Series_Coilover.jpg``,
    ``Rear_Height_Adjuster.jpg``).
  - cross-cutting: ``data:`` URIs, ``http://`` mixed-content URLs (rewrite
    to ``https://``), and any ``.svg`` extension (which is almost always
    chrome rather than a product photo).

The adapters now drop these at extract / ingest time. This migration is a
one-shot backfill that strips them from rows already written to the DB.

Idempotent — re-running won't double-process because every check still
matches the same junk patterns (or, if a row is already clean, the filter
is a no-op). Empty-after-stripping rows have ``image_urls`` set to NULL
(an empty array would fool downstream code into thinking we have an
image).

This file is a documented exception to CLAUDE.md's "Alembic autogenerate
only" rule (C-01): autogenerate cannot express a data-only cleanup with no
schema delta. Generated revision id by hand and hand-authored the body.
"""

import json
import re
from typing import List, Optional, Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "ea29b2450841"
down_revision: Union[str, None] = "f99b709f371a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Deny patterns — must stay in sync with the per-adapter filters added in
# the same change set. Each pattern matches a substring of the URL (case-
# insensitive).
_JUNK_URL_PATTERNS: List[str] = [
    # studiorsr Shopify lazy-loader / theme chrome
    r"/cdn/shop/t/[^/]+/assets/",
    r"loading\.svg",
    r"studiorsr_dark",
    # cobbtuning generic AccessPort beauty-shots. We deny ALL of these in
    # the backfill rather than gating on SKU prefix because by the time
    # the migration runs the SKU is in a different column and joining
    # for every row is expensive. AP3 SKUs that legitimately use the
    # marketing image will be re-populated by the adapter on the next
    # rescrape; the cleanup just clears stale wrong-image leakage.
    r"accessport_v3_(?:extra|main|subaru|ford|bmw|volkswagen|mazda)",
    # forgeline marketing template renders
    r"forgelinevehicletailoredimage",
    r"forgelinecustomfinishingimage",
    # hksusa logo fallback
    r"hks(?:usa)?_logo",
    # apr generic ECU-tune box
    r"apr-ecu-box\.png",
    # bcracing catalog hero placeholders
    r"BR_Series_Coilover\.jpg",
    r"Rear_Height_Adjuster\.jpg",
]

_JUNK_RE = re.compile("|".join(_JUNK_URL_PATTERNS), re.IGNORECASE)


def _is_junk_url(url: str) -> bool:
    """
    Return True if ``url`` matches any of the documented junk patterns OR
    is a ``data:`` URI / a non-decal-sticker-logo ``.svg``. Bare empty
    strings and non-string entries are also rejected.
    """
    if not isinstance(url, str):
        return True
    u = url.strip()
    if not u:
        return True
    if u.lower().startswith("data:"):
        return True
    if _JUNK_RE.search(u):
        return True
    # Drop any .svg — across the catalog, .svg files are chrome (icons,
    # spinners, logos) rather than product photos. Adapters that need
    # decals/stickers/logos can rely on the cross-cutting filter (which
    # keeps SVGs when the part name mentions those words); the backfill
    # is conservative because we don't have part name in scope here.
    path_only = u.split("?", 1)[0].split("#", 1)[0]
    if path_only.lower().endswith(".svg"):
        return True
    return False


def _clean_url_list(raw: Optional[List[str]]) -> Optional[List[str]]:
    """
    Return a cleaned URL list (junk removed, ``http://`` rewritten to
    ``https://``) or ``None`` if nothing survives. Order is preserved.
    """
    if not raw:
        return None
    out: List[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        u = entry.strip()
        if not u:
            continue
        if _is_junk_url(u):
            continue
        if u.startswith("http://"):
            u = "https://" + u[len("http://") :]
        out.append(u)
    return out or None


def upgrade() -> None:
    """
    Strip junk image URLs from ``parts.image_urls`` for rows already
    persisted before the per-adapter filters and the cross-adapter
    ingest filter were added. Branches by dialect so SQLite (test DB)
    and Postgres (production) both work.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Pull raw rows once, filter in Python, write back. We could
        # express this entirely in jsonb_array_elements_text + a regex
        # filter, but the regex would have to encode every pattern in
        # POSIX form (different escaping than Python ``re``) and stay
        # in sync with _JUNK_URL_PATTERNS — a maintenance trap for a
        # one-shot backfill. The Python loop is plenty fast for a
        # ~50k-row catalog.
        rows = bind.execute(
            text("SELECT id, image_urls FROM parts WHERE image_urls IS NOT NULL")
        ).fetchall()
    elif dialect == "sqlite":
        rows = bind.execute(
            text("SELECT id, image_urls FROM parts WHERE image_urls IS NOT NULL")
        ).fetchall()
    else:
        # MySQL / others — fall back to the same Python loop. Migration
        # only runs on Postgres in prod and SQLite in tests, but the
        # branch is here for safety.
        rows = bind.execute(
            text("SELECT id, image_urls FROM parts WHERE image_urls IS NOT NULL")
        ).fetchall()

    update_stmt = text("UPDATE parts SET image_urls = :urls WHERE id = :id")

    for row in rows:
        part_id = row[0]
        raw = row[1]
        # SQLAlchemy's JSON adapter usually decodes for us; but if the
        # driver hands back a string (some Postgres setups, or SQLite
        # with the generic JSON type), decode it.
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
            except (ValueError, TypeError):
                continue
        else:
            decoded = raw

        if not isinstance(decoded, list):
            continue

        cleaned = _clean_url_list(decoded)

        # Skip rows where the filter is a no-op so we don't churn
        # untouched rows (cheaper, plus the timestamp columns stay
        # untouched).
        if cleaned == decoded:
            continue

        if cleaned is None:
            bind.execute(update_stmt, {"urls": None, "id": part_id})
        else:
            bind.execute(update_stmt, {"urls": json.dumps(cleaned), "id": part_id})


def downgrade() -> None:
    """
    Data-only forward migration; nothing to undo. The previous junk
    URLs are not preserved (this would require a separate audit table
    that we deliberately don't keep — by definition the URLs were
    wrong). Downgrade is a documented no-op.
    """
    pass
