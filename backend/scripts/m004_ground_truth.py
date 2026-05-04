"""M004 accuracy-harness programmatic ground-truth extractors.

Reads raw HTML and returns the *richer-than-production* signal that the live
extractors are scored against. This module is a measurement tool — it lives
under ``backend/scripts/`` rather than ``backend/app/`` because it deliberately
shares blind spots with the production extractor (both look at the same HTML
per S01-RESEARCH risk #4) and must NEVER be wired into the ingest path. Hand-
labeled gold-set numbers remain the only honest absolute accuracy gate; this
module provides the directional ``--corpus full`` numbers.

Public entry point::

    truth_from_html(html: str, *, retailer: Optional[str] = None) -> dict

Returns a dict shaped to feed directly into ``m004_scoring.score_*`` functions::

    {
      "car_triples":      list[tuple[str, str, str]],
      "manufacturer":     Optional[str],
      "category":         Optional[str],
    }

Three helpers expose the brand-resolution layers used internally::

    extract_jsonld_product(html)   -> Optional[dict]
    extract_microdata_brand(html)  -> Optional[str]
    extract_opengraph_brand(html)  -> Optional[str]

Brand precedence is JSON-LD > microdata > OpenGraph (per T03-PLAN.md).

Defensive contract
------------------
Every public function in this module is non-raising. Corrupt JSON-LD,
truncated tags, oversized inputs, ``None`` arguments — all degrade silently
to an empty / ``None`` result with a structured log line carrying the failure
reason (``truth_extraction_failed`` or ``truth_extraction_skipped``). The
harness MUST be able to iterate 28k+ ``CrawledPage`` rows without any single
broken page aborting the run.

Load profile
------------
Per-part HTML parse is ~10–100ms (BeautifulSoup ``html.parser``). 28k corpus
≈ 5–50 min wall-clock — acceptable for ``--corpus full`` directional checks.
Inputs over ``HTML_SIZE_CAP_BYTES`` (5MB) are short-circuited to an empty
result to bound parse time on adversarial / accidentally-saved-DOM inputs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from app.crawlers.parsing import (
    extract_json_ld_product as _extract_json_ld_product_from_parsing,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Limits & constants
# ---------------------------------------------------------------------------

HTML_SIZE_CAP_BYTES: int = 5 * 1024 * 1024
"""Reject HTML inputs longer than this (5MB) — silently returns empty truth.

Real product pages are <500KB; anything past 5MB is almost certainly a saved
multi-page DOM dump or pathological input. Capping bounds parse time for the
``--corpus full`` 28k iteration."""


# ---------------------------------------------------------------------------
# Helpers — JSON-LD, microdata, OpenGraph brand resolution
# ---------------------------------------------------------------------------


def extract_jsonld_product(html: str) -> Optional[dict]:
    """Return the first JSON-LD ``Product`` block as a dict, or ``None``.

    Thin wrapper over ``app.crawlers.parsing.extract_json_ld_product`` that
    preserves the defensive contract: any unexpected error returns ``None``
    with a logged ``truth_extraction_failed`` reason rather than propagating.
    """
    if not html or not isinstance(html, str) or not html.strip():
        return None
    try:
        item = _extract_json_ld_product_from_parsing(html)
    except Exception as exc:  # noqa: BLE001 — defensive harness boundary
        logger.debug(
            "truth_extraction_failed",
            extra={"reason": "jsonld_parser_error", "error": repr(exc)},
        )
        return None
    if isinstance(item, dict):
        return item
    return None


def _stringify_microdata_value(tag: Tag) -> Optional[str]:
    """Pull a sane string out of an itemprop element.

    Handles three shapes: ``<meta itemprop="x" content="...">``,
    ``<a itemprop="x" href="...">`` (rare for brand), and the common
    ``<span itemprop="x">Text</span>``. Returns ``None`` for empty values so
    callers can fall through to the next layer.
    """
    if not isinstance(tag, Tag):
        return None

    # <meta content="..."> takes precedence — it's the canonical microdata
    # form for non-text values and avoids picking up nested element text.
    if tag.name == "meta":
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None

    # Nested schema.org Brand: <span itemprop="brand"><span itemprop="name">X</span></span>.
    # Prefer the inner ``itemprop="name"`` when present; otherwise fall back to
    # the element's own text content.
    name_child = tag.find(attrs={"itemprop": "name"})
    if isinstance(name_child, Tag):
        # Avoid infinite recursion when the brand element IS the name element.
        if name_child is not tag:
            inner = _stringify_microdata_value(name_child)
            if inner:
                return inner

    text = tag.get_text(separator=" ", strip=True)
    if text:
        return text
    return None


def extract_microdata_brand(html: str) -> Optional[str]:
    """Find a brand/manufacturer via schema.org microdata ``itemprop`` attrs.

    Tries ``itemprop="brand"`` first (canonical schema.org Product field)
    then ``itemprop="manufacturer"`` as fallback. Returns ``None`` when no
    microdata block is present or the value is empty.
    """
    if not html or not isinstance(html, str) or not html.strip():
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "truth_extraction_failed",
            extra={"reason": "microdata_parser_error", "error": repr(exc)},
        )
        return None

    for prop in ("brand", "manufacturer"):
        candidate = soup.find(attrs={"itemprop": prop})
        if isinstance(candidate, Tag):
            value = _stringify_microdata_value(candidate)
            if value:
                return value
    return None


_OPENGRAPH_BRAND_PROPS: tuple[str, ...] = (
    "og:brand",
    "product:brand",
    "og:product:brand",
)


def extract_opengraph_brand(html: str) -> Optional[str]:
    """Find a brand via OpenGraph / product:* meta tags.

    Checks ``og:brand``, ``product:brand``, and ``og:product:brand`` in order.
    Returns the first non-empty content value or ``None``.
    """
    if not html or not isinstance(html, str) or not html.strip():
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "truth_extraction_failed",
            extra={"reason": "opengraph_parser_error", "error": repr(exc)},
        )
        return None

    for prop in _OPENGRAPH_BRAND_PROPS:
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


# ---------------------------------------------------------------------------
# Category resolution — JSON-LD / microdata / OpenGraph
# ---------------------------------------------------------------------------


def _category_from_jsonld(item: Optional[dict]) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    cat = item.get("category")
    if isinstance(cat, str) and cat.strip():
        return cat.strip()
    if isinstance(cat, list):
        for c in cat:
            if isinstance(c, str) and c.strip():
                return c.strip()
            if isinstance(c, dict):
                name = c.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    if isinstance(cat, dict):
        name = cat.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _category_from_microdata(soup: BeautifulSoup) -> Optional[str]:
    candidate = soup.find(attrs={"itemprop": "category"})
    if isinstance(candidate, Tag):
        value = _stringify_microdata_value(candidate)
        if value:
            return value
    return None


def _category_from_opengraph(soup: BeautifulSoup) -> Optional[str]:
    for prop in ("product:category", "og:category", "article:section"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


# ---------------------------------------------------------------------------
# truth_from_html — public entry point
# ---------------------------------------------------------------------------


def _empty_truth() -> dict[str, Any]:
    return {
        "car_triples": [],
        "manufacturer": None,
        "category": None,
    }


def truth_from_html(
    html: str, *, retailer: Optional[str] = None
) -> dict[str, Any]:
    """Derive a programmatic ground-truth dict from raw product HTML.

    Layered resolution — first hit wins per signal:

    * ``manufacturer``: JSON-LD ``brand`` → microdata ``itemprop="brand"|"manufacturer"`` → ``og:brand`` / ``product:brand``.
    * ``category``: JSON-LD ``category`` → microdata ``itemprop="category"`` → ``product:category`` / ``og:category``.
    * ``car_triples``: empty in this iteration; richer car-extraction lives downstream and is not yet wired into ground truth.

    The ``retailer`` keyword is reserved for per-retailer CSS-selector hints
    (``.product-brand``, ``.spec-table tr``) but the current iteration has no
    per-retailer overrides — passing it is accepted and a no-op.

    Defensive contract
    ------------------
    * ``html`` is ``None`` / empty / whitespace-only → ``_empty_truth()``.
    * ``len(html) > HTML_SIZE_CAP_BYTES`` → ``_empty_truth()`` with a
      ``truth_extraction_skipped`` warning log.
    * Any unexpected parser exception → ``_empty_truth()`` with a
      ``truth_extraction_failed`` debug log. Never raises.
    """
    if html is None or not isinstance(html, str):
        return _empty_truth()

    if not html.strip():
        return _empty_truth()

    if len(html) > HTML_SIZE_CAP_BYTES:
        logger.warning(
            "truth_extraction_skipped",
            extra={
                "reason": "oversized_input",
                "size_bytes": len(html),
                "cap_bytes": HTML_SIZE_CAP_BYTES,
                "retailer": retailer,
            },
        )
        return _empty_truth()

    out = _empty_truth()

    # ---- Manufacturer: JSON-LD → microdata → OpenGraph ---------------------
    try:
        item = extract_jsonld_product(html)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "truth_extraction_failed",
            extra={"reason": "jsonld_outer_error", "error": repr(exc)},
        )
        item = None

    if item is not None:
        brand = _brand_from_jsonld_item(item)
        if brand:
            out["manufacturer"] = brand

    if out["manufacturer"] is None:
        try:
            md = extract_microdata_brand(html)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "truth_extraction_failed",
                extra={"reason": "microdata_outer_error", "error": repr(exc)},
            )
            md = None
        if md:
            out["manufacturer"] = md

    if out["manufacturer"] is None:
        try:
            og = extract_opengraph_brand(html)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "truth_extraction_failed",
                extra={"reason": "opengraph_outer_error", "error": repr(exc)},
            )
            og = None
        if og:
            out["manufacturer"] = og

    # ---- Category: JSON-LD → microdata → OpenGraph -------------------------
    cat = _category_from_jsonld(item)
    if not cat:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "truth_extraction_failed",
                extra={"reason": "category_soup_error", "error": repr(exc)},
            )
            soup = None
        if soup is not None:
            cat = _category_from_microdata(soup) or _category_from_opengraph(soup)
    if cat:
        out["category"] = cat

    # car_triples: not yet derived from HTML in this iteration. The slice
    # plan calls out that car-triple extraction is the live extractor's
    # primary signal; programmatic truth here only mirrors it where the live
    # signal was absent. For the v1 harness, leave empty so score_car runs
    # against the live prediction's own triples vs. hand-labeled gold only.
    return out


def _brand_from_jsonld_item(item: dict) -> Optional[str]:
    """Pull a brand string out of a JSON-LD Product item dict.

    Mirrors the live extractor's brand-resolution but stays inside this
    module so changes to the production code don't silently shift ground
    truth.
    """
    brand = item.get("brand")
    if isinstance(brand, str) and brand.strip():
        return brand.strip()
    if isinstance(brand, dict):
        name = brand.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    if isinstance(brand, list):
        for b in brand:
            if isinstance(b, str) and b.strip():
                return b.strip()
            if isinstance(b, dict):
                name = b.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    # Schema.org "manufacturer" is a separate field but some retailers ship
    # it instead of brand — treat as fallback.
    mfr = item.get("manufacturer")
    if isinstance(mfr, str) and mfr.strip():
        return mfr.strip()
    if isinstance(mfr, dict):
        name = mfr.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


# Re-export json for any future per-retailer JSON parsing — kept here so the
# import isn't flagged as unused while the per-retailer hint table is empty.
_ = json
