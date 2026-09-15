"""The stable, url-safe slug shared by the catalog rows and the car seed data.

Lives in common because `app/common/db/dynamo/catalog.py` derives slugs on write
while the vehicles domain derives the same slugs for its seed rows. Both must
agree, and a domain may not own a helper a common module calls.
"""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    """Convert a name into the stable, url-safe slug rows are looked up by.

    Lowercases, collapses non-alphanumeric runs to single hyphens, and trims
    them from both ends.
    """
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")
