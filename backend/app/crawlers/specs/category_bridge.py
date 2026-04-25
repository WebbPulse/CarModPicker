"""
Bridge from ``infer_category()`` DB category names to ``SpecRegistry`` sub-slugs.

The crawler ingest pipeline uses ``app.core.category_inference.infer_category``
to assign a part category from name + description. That function returns the
*DB category name* (``"suspension"``, ``"brakes"``, ``"engine"``, ``"wheels"``,
``"other"``, …) — not a SpecRegistry sub-slug like ``"coilover"`` /
``"brake"`` / ``"turbo"``. Without translation, the S01 validation hook
(``ingest_payload`` → ``default_registry.resolve(inferred_name)``) never finds
a registered spec model for any production payload — every call hits the
"no model registered" pass-through and the spec block is never validated.

``category_to_subslug`` closes that gap. Given the DB category name plus the
part's name and description, it returns the most specific sub-slug it can
defend (e.g. coilover-keyword text under suspension → ``"coilover"``), or the
``"universal"`` catch-all when nothing more specific applies. Returning
``"universal"`` for any non-None category name is what makes the validation
hook fire across the catalog: combined with ``UniversalSpec`` (registered in
``app.crawlers.specs.__init__``), every category with universal-field content
gets validated — concrete sub-categories against their dedicated spec, the
long tail against UniversalSpec.

Pass-through behaviour: when ``category_name is None`` (caller couldn't infer
a category at all), the bridge returns ``None`` so the ingest hook continues
to skip validation entirely — preserves the S01 contract.

Keyword-scoring shape mirrors ``app/core/category_inference.py``: small
per-slug keyword lists, word-boundary matches, best-score-wins. Keep the
keyword tables small and explicit; precision matters more than recall here
because every false match validates the wrong schema.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# Per-slug keyword lists. Each keyword must be linear-time when escaped and
# wrapped in word-boundary anchors. Order does not affect the result; the
# best-score per (slug, text) pair wins.
_SUBSLUG_KEYWORDS: Dict[str, List[str]] = {
    "coilover": [
        "coilover",
        "coilovers",
        "coil over",
        "coil-over",
    ],
    "turbo": [
        "turbo",
        "turbocharger",
    ],
}

# Valid parent DB categories that gate sub-slug resolution. A coilover keyword
# in a wheels-categorized part shouldn't hijack the schema; the parent
# category must agree with the sub-slug's home category before we resolve it.
_PARENT_FOR_SUBSLUG: Dict[str, str] = {
    "coilover": "suspension",
    "turbo": "engine",
}

# Single-sub-slug DB categories that resolve unconditionally — no disambiguating
# keyword needed because there is only one registered sub-slug under that
# parent category. Today this only applies to brakes; suspension/engine each
# have multiple potential sub-slugs (only one shipped today, but the keyword
# gate keeps the door open for additions in S03+).
_SINGLE_SUBSLUG_CATEGORIES: Dict[str, str] = {
    "brakes": "brake",
}

#: Catch-all slug returned when a category is set but no sub-slug applies.
#: Must match the slug ``UniversalSpec`` is registered under in
#: ``app.crawlers.specs.__init__``.
UNIVERSAL_SUBSLUG = "universal"


def _score_text(text: str, keywords: List[str]) -> int:
    """
    Count how many keywords match ``text`` on word boundaries. Each keyword
    counts at most once. Mirrors ``category_inference._score_text``.
    """
    if not text or not keywords:
        return 0
    lower = text.lower()
    count = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower):
            count += 1
    return count


def category_to_subslug(
    category_name: Optional[str],
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve a DB category name to a SpecRegistry sub-slug.

    Mapping (initial S02 set):

    * ``"suspension"`` + (coilover keyword in name/description) → ``"coilover"``
    * ``"brakes"`` (always — the only brake sub-slug today) → ``"brake"``
    * ``"engine"`` + (turbo keyword in name/description) → ``"turbo"``
    * Any other non-None ``category_name`` (or ``"suspension"``/``"engine"``
      without their disambiguating keywords) → ``"universal"``
    * ``category_name is None`` → ``None`` (caller skips validation entirely)

    The keyword-gated branches ensure a misclassified part doesn't get
    validated against the wrong concrete spec — falling through to
    ``"universal"`` is always safe because UniversalSpec only declares the
    five universal fields plus their confidence companions.
    """
    if category_name is None:
        return None

    parent = category_name.strip().lower() if category_name.strip() else ""
    if not parent:
        return None

    # Single-sub-slug parent categories (currently brakes → brake) resolve
    # unconditionally; no keyword check needed.
    direct = _SINGLE_SUBSLUG_CATEGORIES.get(parent)
    if direct is not None:
        return direct

    # Keyword-gated sub-slugs (coilover under suspension, turbo under engine).
    # Concatenate name + description once and score every gated sub-slug whose
    # parent category matches.
    text = " ".join(part for part in (name, description) if part)
    if text.strip():
        for subslug, keywords in _SUBSLUG_KEYWORDS.items():
            if _PARENT_FOR_SUBSLUG.get(subslug) != parent:
                continue
            if _score_text(text, keywords) > 0:
                return subslug

    # Non-None category but no specific sub-slug matched — fall through to the
    # universal catch-all so the validation hook still fires against the five
    # universal fields.
    return UNIVERSAL_SUBSLUG
