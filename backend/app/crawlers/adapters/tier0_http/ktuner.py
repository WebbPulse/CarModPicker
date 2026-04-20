"""
KTuner (ktuner.com) crawler adapter.

KTuner runs a small, direct-to-consumer Honda/Acura flash-tuning catalog on
WordPress. Unlike a normal storefront it has **no per-product detail pages** —
the entire hardware catalog is rendered inline on a single ``/products/`` page
as a sequence of text sections separated by ``<hr />`` horizontal rules. There
is no JSON-LD Product schema, no ``og:product:*`` meta, no add-to-cart flow
(KTuner sells through dealers or direct phone/email).

To fit the framework's one-URL-per-product contract we emit four discovery
URLs pointing at ``/products/`` with a distinct ``?sku=<slug>`` query string
per product:

- ``ktunerflash-v2-touch``
- ``ktunerflash-v1-2``
- ``ktunerecu-rev1``
- ``ktuner-flex-fuel-converter``

``sku`` is not in ``_TRACKING_PARAMS`` so ``canonicalize_url`` preserves it;
WordPress ignores the unknown param and returns the identical catalog HTML for
all four. ``parse_product_page`` then reads the slug, walks the ``<hr />``-
delimited sections of ``.post-content``, and extracts the section whose
header ``<strong>`` text matches the slug's keyword set.

The TunerView Android app ($4.99 Google Play listing) is intentionally not
crawled — it's a third-party app, not a KTuner-sold hardware SKU, and pricing
lives on Google Play.

Part numbers: only the Flex Fuel Converter exposes a real public MPN on the
page (``FFC100``). The three flash-tuning units are sold by name without a
printed SKU, so we fall back to a stable, slug-derived code
(``KTUNERFLASH-V2-TOUCH``, etc.) so cross-retailer dedupe against eventual
dealer listings has something to match on.
"""

import re
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    normalize_description_text,
    parse_price_cents,
)

KTUNER_BASE = "https://ktuner.com"
PRODUCTS_URL = KTUNER_BASE + "/products/"
KTUNER_BRAND = "KTuner"

# One entry per catalog row. ``keywords`` are lowercased substrings that must
# all appear in the section header ``<strong>`` text for that section to be
# matched to this slug. ``fallback_part_number`` is used when no explicit MPN
# is visible in the section body (KTuner doesn't print SKUs for the flash
# units themselves).
_KtunerProduct = Tuple[str, Tuple[str, ...], str]
KTUNER_PRODUCTS: List[_KtunerProduct] = [
    ("ktunerflash-v2-touch", ("ktunerflash", "v2", "touch"), "KTUNERFLASH-V2-TOUCH"),
    ("ktunerflash-v1-2", ("ktunerflash", "v1.2"), "KTUNERFLASH-V1.2"),
    ("ktunerecu-rev1", ("ktunerecu",), "KTUNERECU-REV1"),
    ("ktuner-flex-fuel-converter", ("flex fuel converter",), "FFC100"),
]

_SLUGS_IN_ORDER: List[str] = [p[0] for p in KTUNER_PRODUCTS]
_SLUG_TO_PRODUCT: Dict[str, _KtunerProduct] = {p[0]: p for p in KTUNER_PRODUCTS}

# Matches an inline MPN written like ``FFC100 –<strong> $99</strong>`` or
# ``FFC100 - $99``. Restricted to 2+ letters followed by 2+ digits so we don't
# pick up stray uppercase words like "OBD" or "USB" from the feature bullets.
_INLINE_MPN_RE = re.compile(
    r"\b([A-Z]{2,}[0-9]{2,}[A-Z0-9]*)\s*[–\-]\s*\$",
)


def _upgrade_to_https(src: str) -> str:
    """KTuner serves ``/images/*`` over ``http://www.ktuner.com`` in the page
    source. Force ``https://`` so stored image URLs don't mixed-content-block
    when rendered from the HTTPS frontend."""
    s = src.strip()
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    return s


def _slug_from_url(url: str) -> Optional[str]:
    """Pull the ``?sku=<slug>`` value from a discovery URL. Returns ``None``
    when the URL is the bare ``/products/`` page — in that case the caller
    can't know which section to parse and should bail."""
    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        return None
    raw = (query.get("sku") or [""])[0].strip().lower()
    return raw if raw in _SLUG_TO_PRODUCT else None


def _split_into_sections(post_content: Tag) -> List[List[Tag]]:
    """Split ``.post-content`` into ``<hr />``-delimited sections. Only direct
    element children are considered — text nodes and inline whitespace are
    dropped. The intro paragraph and warranty trailer end up in their own
    sections and are filtered out by caller (they have no product header)."""
    sections: List[List[Tag]] = [[]]
    for child in post_content.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "hr":
            sections.append([])
            continue
        sections[-1].append(child)
    return [s for s in sections if s]


def _section_header_with_index(section: List[Tag]) -> Optional[Tuple[str, int]]:
    """First ``<strong>`` text in the section and the section index of the
    tag containing it. The index matters because the page's pre-first-
    ``<hr/>`` section includes the ``"Here is some information about…"``
    intro paragraph *before* the V2 Touch header; callers need to know
    where the header sits so they can ignore anything earlier as
    non-product copy. Returns ``None`` for sections with no ``<strong>``
    (warranty trailer, blank fragments)."""
    for i, tag in enumerate(section):
        strong = tag.find("strong") if hasattr(tag, "find") else None
        if isinstance(strong, Tag):
            text = strong.get_text(strip=True)
            if text:
                return text.rstrip(":").strip(), i
    return None


def _section_header(section: List[Tag]) -> Optional[str]:
    """Convenience wrapper around ``_section_header_with_index`` for
    callers that only need the header text."""
    found = _section_header_with_index(section)
    return found[0] if found else None


def _section_matches_slug(header: str, keywords: Tuple[str, ...]) -> bool:
    """Case-insensitive substring match: every keyword must appear in the
    header. ``"v1.2"`` vs ``"v2"`` discriminates the two flash units; the
    other pairs are unambiguous on a single keyword."""
    h = header.lower()
    return all(kw in h for kw in keywords)


def _find_section_for_slug(post_content: Tag, slug: str) -> Optional[List[Tag]]:
    """Return the ``<hr />``-delimited section whose header matches the given
    slug's keyword set, or ``None`` when no section matches (site edit, slug
    drift)."""
    product = _SLUG_TO_PRODUCT.get(slug)
    if product is None:
        return None
    _, keywords, _ = product
    for section in _split_into_sections(post_content):
        header = _section_header(section)
        if header and _section_matches_slug(header, keywords):
            return section
    return None


def _extract_price_cents(section: List[Tag]) -> Optional[int]:
    """Find the first ``$NNN`` pattern in the section text. Each section has
    exactly one price callout (in the header paragraph); feature bullets
    don't mention dollar amounts, so the first hit is always authoritative."""
    for tag in section:
        text = tag.get_text(separator=" ", strip=True)
        if "$" not in text:
            continue
        match = re.search(r"\$\s?[\d,]+(?:\.\d+)?", text)
        if match:
            cents = parse_price_cents(match.group(0))
            if cents is not None:
                return cents
    return None


def _extract_image_url(section: List[Tag]) -> Optional[str]:
    """Return the first ``<img>`` src found anywhere in the section,
    upgraded to https. KTuner puts one hero image per section — either
    inline in the header ``<p>`` (V2 Touch, V1.2, FFC) or in its own ``<p>``
    immediately after (KTunerECU). No gallery, so we don't bother scanning
    for extras."""
    for tag in section:
        img = tag.find("img") if hasattr(tag, "find") else None
        if isinstance(img, Tag):
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                return _upgrade_to_https(src)
    return None


def _extract_description(section: List[Tag], header_index: int) -> Optional[str]:
    """Concatenate paragraph + list text that appears *after* the header
    tag. Anything before ``header_index`` is non-product copy (the
    ``"Here is some information…"`` intro paragraph lives in the same
    pre-first-``<hr/>`` section as the V2 Touch header, for example).
    Drops the ``"list of supported vehicles"`` boilerplate footer each
    section ends with — it's identical across products."""
    parts: List[str] = []
    for tag in section[header_index + 1 :]:
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue
        if "list of supported vehicles" in text.lower():
            continue
        parts.append(text)
    if not parts:
        return None
    combined = " ".join(parts)
    return normalize_description_text(combined, max_len=2000)


def _extract_part_number(section: List[Tag], fallback: str) -> str:
    """Prefer an explicit inline MPN like ``FFC100`` when the section prints
    one; otherwise use the stable slug-derived fallback so dedupe has a key."""
    for tag in section:
        text = tag.get_text(separator=" ", strip=True)
        match = _INLINE_MPN_RE.search(text)
        if match:
            return match.group(1)
    return fallback


def _name_from_header(header: str) -> str:
    """Header text is already the product name (e.g. ``"KTunerFlash V2 Touch
    – Flash Based Hardware"``). Collapse the Unicode em-dash to a plain ``-``
    for cleaner storage; KTuner uses both in the page and our downstream
    normalization doesn't treat them the same for display."""
    return header.replace("\u2013", "-").replace("\u2014", "-").strip()


class KTunerAdapter(RetailerCrawlerAdapter):
    """
    KTuner adapter. All four hardware SKUs live on the single ``/products/``
    page; discovery yields four ``?sku=<slug>`` variants so each product
    gets its own ``ScrapedPayload`` row. Parsing splits the page's
    ``.post-content`` on ``<hr />`` and matches the requested slug's section
    by keyword.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield one URL per product, distinguished by a ``?sku=<slug>``
        query param so canonicalized URLs stay unique and the runner
        processes each product as a separate ingest row."""
        for slug in _SLUGS_IN_ORDER:
            yield f"{PRODUCTS_URL}?sku={slug}"

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse the KTuner catalog page, extracting only the product
        section identified by ``?sku=<slug>`` in ``url``. Returns ``None``
        when the URL has no slug (e.g. a bare ``/products/`` URL posted
        from the chrome extension) or when the page's DOM has drifted
        enough that no section matches the slug's keywords."""
        slug = _slug_from_url(url)
        if slug is None:
            return None

        soup = BeautifulSoup(html, "html.parser")
        post_content = soup.select_one(".post-content")
        if not isinstance(post_content, Tag):
            return None

        section = _find_section_for_slug(post_content, slug)
        if section is None:
            return None

        found = _section_header_with_index(section)
        if not found:
            return None
        header, header_index = found

        name = _name_from_header(header)
        _, _, fallback_pn = _SLUG_TO_PRODUCT[slug]
        body = section[header_index:]

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_extract_description(section, header_index),
            price_cents=_extract_price_cents(body),
            part_manufacturer=KTUNER_BRAND,
            part_number=_extract_part_number(body, fallback_pn),
            image_urls=[img] if (img := _extract_image_url(body)) else None,
        )
