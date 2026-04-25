"""
Mackin Industries (mackinindustries.com / mackin-ind.com) crawler adapter — Tier 1 (TLS).

Product URLs (two shapes, both handled):

- ``https://mackin-ind.com/item/<slug>/`` — custom post type that backs the
  wheel / accessory catalog (Volk Racing, Gram Lights, Advan, Project Mu,
  KYO-EI, MXP, Wheel Mate). Most of the catalog. **No price, no SKU** —
  Mackin is a distributor and publishes spec sheets, not MSRP.
- ``https://mackin-ind.com/product/<slug>/`` — WooCommerce storefront for
  merchandise (t-shirts, stickers, tools). Small catalog; does carry
  ``<span class="price">`` and ``<span class="sku">``.

Domain note: the user-visible domain ``mackinindustries.com`` is a tiny
UTF-16 encoded landing page whose only content is a ``<meta http-equiv="Refresh">``
pointing at ``www.mackin-ind.com``. The canonical origin with the catalog is
``mackin-ind.com`` (no ``www.``). ``_canonicalize_product_url`` rewrites any
input URL to that host so archive dedupe stays consistent whichever domain the
user typed.

Fetcher tier: Mackin is WordPress on WP Engine behind Cloudflare. Plain curl
with a current Chrome UA gets **intermittent 403s** served by wpewaf.com
(``product-sitemap.xml`` blocked; ``item-sitemap.xml`` allowed on the same
session). Same client-fingerprint posture as Vivid Racing / Cobb Tuning —
``FETCHER_TIER = "tls"`` routes both discovery and product fetches through
curl_cffi's Chrome impersonation.

Parsing: Yoast SEO emits a JSON-LD graph with ``WebPage`` / ``ImageObject`` /
``BreadcrumbList`` / ``WebSite`` — **no ``Product`` item** — so the shared
``extract_json_ld_product`` helper does not fire here. We parse the og:* meta
tags (name, description, image) + the H1 + WooCommerce DOM selectors for the
/product/ subset. ``og:title`` carries a trailing ``" - Mackin Industries"``
site-name suffix from Yoast; stripped.

Brand: Mackin distributes a fixed short list — RAYS (Volk Racing, Gram Lights,
including the 57* and G* model families), Yokohama Wheel (Advan Racing),
Project Mu, KYO-EI (including KICS, Bull Lock, Muteki sub-brands), MXP, and
Wheel Mate Products. The slug/title token map covers every catalog entry; a
slug that matches none of them (generic accessories like ``wheel-rack``,
``magnetic-drain-bolt``, ``optional-decal-set``) gets ``None`` — the
ingest-time default of ``"Unknown"`` is honest and better than mis-attributing.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse, urlunparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

MACKIN_HOST = "mackin-ind.com"
MACKIN_BASE = f"https://{MACKIN_HOST}"
SITEMAP_INDEX_URL = f"{MACKIN_BASE}/sitemap_index.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical product URL: /item/<slug>/ (catalog) or /product/<slug>/ (WooCommerce).
# Slugs are kebab-case ASCII. Trailing slash optional so a URL that round-trips
# through canonicalization (which normalizes to include the slash) still matches.
_PRODUCT_PATH_RE = re.compile(r"^/(item|product)/[a-z0-9][a-z0-9\-]*/?$", re.IGNORECASE)

# Yoast's "Document Title" template appends " - Mackin Industries" to every
# page, product or not. Stripped from og:title so stored names read cleanly.
_NAME_SITE_SUFFIX_RE = re.compile(r"\s*-\s*Mackin\s+Industries\s*$", re.IGNORECASE)

# WordPress generates thumbnail variants as "<base>-<W>x<H>.<ext>" alongside
# the full-size "<base>.<ext>". Dedupe the gallery by stripping that suffix
# and the extension so we keep one URL per distinct source photo.
_IMAGE_SIZE_SUFFIX_RE = re.compile(r"-(\d{2,4})x(\d{2,4})(?=\.[A-Za-z]+$)")

# Any image referenced on the page that lives under /wp-content/uploads/ is a
# candidate product image. Brand logos live under /wp-content/themes/... and
# are excluded by virtue of not matching this path.
_WP_UPLOADS_IMAGE_EXT_RE = re.compile(r"\.(?:jpe?g|png|webp|gif)$", re.IGNORECASE)

# Site-chrome / template images that leak into the page but aren't product
# photography. The Mackin logo is the most common false positive — the theme
# includes it in the header and footer on every page.
_NOISE_IMAGE_RE = re.compile(
    r"/wp-content/uploads/2020/07/Mackin-Logo",
    re.IGNORECASE,
)

# Wheel/accessory catalog — this URL is a stable smoke test for the /item/
# parse path (gramLIGHTS 57CR in the limited Glossy Gray finish). Override
# with CRAWLER_MACKINDUSTRIES_START_URLS for ad-hoc runs.
DEFAULT_START_URLS = [
    "https://mackin-ind.com/item/57cr-glossy-gray/",
]

# Mackin's distribution book. Each token regex matches somewhere in the slug
# (or the cleaned title, lowercased) and maps to the brand name Mackin sells
# it under. Ordered most-specific → least-specific so, e.g., "advan-racing"
# picks Yokohama Wheel before any stray "rays" in the name can hijack it.
#
# RAYS is an umbrella brand — Volk Racing, Gram Lights (57*, 029M, G-Games),
# the TE37 / ZE40 / G12 / G25 model lines, and the mark-ii / glossy-color
# variants all sit under it. That's why the regex is broad.
#
# Yokohama Wheel's sport line is Advan Racing. Advan-branded SKUs go under
# Yokohama Wheel, not RAYS.
_BRAND_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|-)(advan|yokohama)(-|$)", re.IGNORECASE), "Yokohama Wheel"),
    (re.compile(r"(^|-)(project-mu|projectmu)(-|$)", re.IGNORECASE), "Project Mu"),
    (re.compile(r"(^|-)(kyo-ei|kyoei|kics|bull-lock|muteki)(-|$)", re.IGNORECASE), "KYO-EI"),
    (re.compile(r"(^|-)(mxp)(-|$)", re.IGNORECASE), "MXP"),
    (re.compile(r"(^|-)(wheel-mate)(-|$)", re.IGNORECASE), "Wheel Mate"),
    # RAYS umbrella (Volk Racing, Gram Lights, TE37, ZE40, 57*, 029*, G12, G25,
    # G-Games, gramlights, homura). Keep last so the more specific sub-brands
    # above win when both match (rare — distribution lines don't overlap).
    (
        re.compile(
            r"(^|-)(rays|volk|gram-?lights|gramlights|te37|ze40|homura|g-?games" r"|g12|g25|57[a-z]*|029[a-z]*)(-|$)",
            re.IGNORECASE,
        ),
        "RAYS",
    ),
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Mackin product URL (``/item/<slug>/`` or ``/product/<slug>/``)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == MACKIN_HOST or host.endswith("." + MACKIN_HOST) or host in _ALIAS_HOSTS):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


# Hostnames that redirect or alias to the canonical mackin-ind.com origin.
# ``mackinindustries.com`` is the marketing domain in the retailer backlog;
# its only content is a UTF-16 meta-refresh to www.mackin-ind.com, but user-
# or extension-submitted URLs may still point at it. We accept them at the
# URL-gate layer and canonicalize the host before emitting.
_ALIAS_HOSTS = frozenset(
    {
        "mackinindustries.com",
        "www.mackinindustries.com",
        "www.mackin-ind.com",
    }
)


def _canonicalize_product_url(url: str) -> Optional[str]:
    """
    Rewrite a Mackin URL to canonical ``https://mackin-ind.com/<path>/`` form.

    - Host folded to ``mackin-ind.com`` (drops ``www.`` and the legacy
      ``mackinindustries.com`` alias).
    - Scheme forced to https.
    - Trailing slash added on ``/item/...`` and ``/product/...`` paths
      (WordPress redirects both shapes to the slashed form, and the sitemap
      emits them slashed).
    - Query string dropped — no product-level query params exist on Mackin.

    Returns None when the URL isn't a Mackin product URL.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not (host == MACKIN_HOST or host.endswith("." + MACKIN_HOST) or host in _ALIAS_HOSTS):
        return None
    path = parsed.path or ""
    if not _PRODUCT_PATH_RE.match(path):
        return None
    if not path.endswith("/"):
        path = path + "/"
    return urlunparse(("https", MACKIN_HOST, path, "", "", ""))


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_MACKINDUSTRIES_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_MACKINDUSTRIES_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _slug_from_url(url: str) -> str:
    """Return the kebab-case slug portion of a Mackin product URL (empty on no match)."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return ""
    # path is /item/<slug>/ or /product/<slug>/ — take the non-empty segment after the type.
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return parts[1]
    return ""


def _brand_from_tokens(*sources: str) -> Optional[str]:
    """
    Walk the brand token map against each source (slug, title) and return the
    first match. Sources are tried in order; within a source the map's
    own order (most-specific → least-specific) controls precedence.
    """
    for src in sources:
        if not src:
            continue
        for pattern, brand in _BRAND_MAP:
            if pattern.search(src):
                return brand
    return None


def _strip_site_suffix(name: str) -> str:
    """Drop the trailing ``" - Mackin Industries"`` suffix Yoast appends."""
    stripped = _NAME_SITE_SUFFIX_RE.sub("", name).strip()
    return stripped or name


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer og:title (Yoast emits it on every product) with the site-name
    suffix stripped. Fall back to H1, which on /item/ pages is the clean
    product name and on /product/ pages is ``h1.product_title``.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        raw = meta_content(og_title)
        if raw and raw.strip():
            return _strip_site_suffix(raw.strip())
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    og:description (short, marketing-safe) → WooCommerce short-description div
    → first <p> under the product detail column on /item/ pages.

    Yoast emits a concise og:description for every page, so it's the most
    reliable source across both URL types. WooCommerce's
    ``.woocommerce-product-details__short-description`` supplements with the
    seller's own short copy on /product/ pages (og:description there is the
    Yoast fallback, sometimes just "FINAL SALE").
    """
    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        raw = meta_content(og_desc)
        if raw and raw.strip():
            return normalize_description_text(raw, max_len=2000)

    short = soup.find(class_=re.compile(r"woocommerce-product-details__short-description"))
    if isinstance(short, Tag):
        text = short.get_text(separator=" ", strip=True)
        if text:
            return normalize_description_text(text, max_len=2000)

    # /item/ pages: the first <p> after the H1 inside the product detail
    # column carries the marketing blurb. There's no stable wrapper class,
    # so we scope by the <article class="type-item"> root when present.
    article = soup.find("article", class_=re.compile(r"\btype-item\b"))
    if isinstance(article, Tag):
        p = article.find("p")
        if isinstance(p, Tag):
            text = p.get_text(separator=" ", strip=True)
            if text:
                return normalize_description_text(text, max_len=2000)

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        raw = meta_content(meta_desc)
        if raw and raw.strip():
            return normalize_description_text(raw, max_len=2000)
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    /product/ (WooCommerce) only — /item/ pages never emit a price.

    Pick the **current** (sale-aware) price: WooCommerce wraps the striked-out
    original in ``<del>`` and the current figure in ``<ins>``. When both are
    present we want the ``<ins>`` amount; when only a single ``<span
    class="woocommerce-Price-amount amount">`` is present (non-sale product)
    we use that.
    """
    price_p = soup.find("p", class_=re.compile(r"\bprice\b"))
    if not isinstance(price_p, Tag):
        price_p = soup.find("span", class_=re.compile(r"\bprice\b"))
    if not isinstance(price_p, Tag):
        return None

    ins = price_p.find("ins")
    container: Tag = ins if isinstance(ins, Tag) else price_p
    amount = container.find(class_=re.compile(r"woocommerce-Price-amount"))
    if isinstance(amount, Tag):
        text = amount.get_text(strip=True)
        if text:
            return parse_price_cents(text)
    return None


def _extract_part_number(soup: BeautifulSoup) -> Optional[str]:
    """
    /product/ (WooCommerce) only — the WooCommerce SKU lives in
    ``<span class="sku">`` inside the product_meta block. /item/ pages
    expose no SKU or MPN (distributor catalog), so we return None there.
    """
    meta = soup.find(class_=re.compile(r"\bproduct_meta\b"))
    if not isinstance(meta, Tag):
        return None
    sku = meta.find(class_=re.compile(r"\bsku\b"))
    if isinstance(sku, Tag):
        text = sku.get_text(strip=True)
        if text and text.lower() != "n/a":
            return normalize_part_number(text)
    return None


def _image_dedup_key(url: str) -> str:
    """
    Collapse WordPress resize variants. ``foo.jpg``, ``foo-600x450.jpg``,
    ``foo-300x300.jpg`` all key to ``foo``. Query string is stripped first so
    CDN cache-bust params don't fragment the dedup.
    """
    base = url.split("?", 1)[0]
    tail = base.rsplit("/", 1)[-1]
    tail = _IMAGE_SIZE_SUFFIX_RE.sub("", tail)
    dot = tail.rfind(".")
    if dot > 0:
        tail = tail[:dot]
    return tail.lower()


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery images. WordPress generates many sized variants
    of the same source photo; we keep at most one per distinct source.

    Sources, in priority order:
    1. og:image — primary hero, full-size.
    2. Lightbox anchors (``a[href]`` under ``.lightbox-container`` and
       ``.included-pieces``) — always link the original full-resolution jpg.
    3. Slider / gallery ``<img data-srcset>`` — several resolutions per photo;
       we take the largest URL from the srcset.

    The Mackin site-chrome logo (``/wp-content/uploads/2020/07/Mackin-Logo*``)
    is filtered; WooCommerce variation thumbnails are kept since they show
    the product.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = raw.strip()
        if not u:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = MACKIN_BASE + u
        if not u.startswith("http"):
            return
        if not _WP_UPLOADS_IMAGE_EXT_RE.search(u.split("?", 1)[0]):
            return
        if _NOISE_IMAGE_RE.search(u):
            return
        key = _image_dedup_key(u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    # Lightbox anchors always point at the full-size original. Scope to the
    # product detail and variation blocks so we don't pick up unrelated
    # gallery-lightbox usages elsewhere on the template.
    for container_re in (r"lightbox-container", r"included-pieces", r"variations-container"):
        for container in soup.find_all(class_=re.compile(container_re)):
            if not isinstance(container, Tag):
                continue
            for anchor in container.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue
                href = anchor.get("href")
                if isinstance(href, str):
                    add(href)

    # Fallback: slider and lazy-load <img> with data-srcset/src inside the
    # main article. Take the largest URL from each srcset.
    article = soup.find("article", class_=re.compile(r"\btype-(item|product)\b"))
    scope: Tag | BeautifulSoup = article if isinstance(article, Tag) else soup
    for img in scope.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        srcset = img.get("data-srcset") or img.get("srcset")
        if isinstance(srcset, str) and srcset.strip():
            # Parse "url1 100w, url2 600w, ..." and pick the largest width.
            best_url: Optional[str] = None
            best_w: int = -1
            for part in srcset.split(","):
                bits = part.strip().split()
                if not bits:
                    continue
                candidate_url = bits[0]
                width = 0
                if len(bits) >= 2 and bits[1].endswith("w"):
                    try:
                        width = int(bits[1][:-1])
                    except ValueError:
                        width = 0
                if width > best_w:
                    best_w = width
                    best_url = candidate_url
            add(best_url)
            continue
        for attr in ("src", "data-src"):
            val = img.get(attr)
            if isinstance(val, str):
                add(val)
                break

    return ordered[:12]


def _extract_part_manufacturer(
    soup: BeautifulSoup,
    *,
    url: str,
    name: Optional[str],
) -> Optional[str]:
    """
    /product/ pages may carry a WooCommerce Brands plugin anchor
    (``.pwb-product-brands-list a``); use it when present. Otherwise fall
    back to the slug/title token map against Mackin's fixed distribution book.
    Generic accessories (``wheel-rack``, ``magnetic-drain-bolt``) return None.
    """
    pwb = soup.find(class_=re.compile(r"pwb-product-brands-list"))
    if isinstance(pwb, Tag):
        anchor = pwb.find("a")
        if isinstance(anchor, Tag):
            text = anchor.get_text(strip=True)
            if text:
                return text
    slug = _slug_from_url(url)
    lowered_name = (name or "").lower()
    return _brand_from_tokens(slug, lowered_name)


class MackinIndustriesAdapter(RetailerCrawlerAdapter):
    """
    Mackin Industries adapter.

    Fetcher tier: ``tls`` — WP Engine + Cloudflare WAF intermittently 403s
    plain requests at the TLS handshake (``wpewaf.com`` interstitial). Same
    client-fingerprint posture as Vivid Racing and Cobb Tuning; curl_cffi
    Chrome impersonation clears it.

    Discovery: ``CRAWLER_MACKINDUSTRIES_START_URLS`` env var wins. Otherwise
    we walk Yoast's ``/sitemap_index.xml`` and fetch the child urlsets whose
    path is ``item-sitemap*.xml`` (the ~1k wheel/accessory catalog) or
    ``product-sitemap.xml`` (the small WooCommerce merch catalog). All URLs
    are canonicalized to the ``mackin-ind.com`` host before emitting.

    Parsing: no JSON-LD Product (Yoast graph only emits WebPage +
    ImageObject + BreadcrumbList + WebSite). We use og:title with the site-
    name suffix stripped, og:description, wp-content/uploads images deduped
    across size variants, and — on /product/ only — the WooCommerce price
    (<ins> wins on sale) and SKU. /item/ pages never carry price or SKU.
    """

    ADAPTER_NAME: ClassVar[str] = "mackinindustries"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield canonical product URLs. Env override wins; otherwise walk the
        Yoast sitemap index and fall back to ``DEFAULT_START_URLS`` when
        discovery comes back empty.
        """
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                canonical = _canonicalize_product_url(url)
                if canonical:
                    yield canonical
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            canonical = _canonicalize_product_url(url)
            if canonical:
                yield canonical

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch ``/sitemap_index.xml`` via the TLS fetcher, then each
        ``item-sitemap*.xml`` / ``product-sitemap.xml`` child. Returns the
        deduplicated list of product URLs; empty on any failure.
        """
        seen: set[str] = set()
        product_urls: List[str] = []

        def parse_urlset_locs(xml_text: str) -> None:
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                return
            for loc in _loc_elements(root):
                if not loc.text:
                    continue
                canonical = _canonicalize_product_url(loc.text.strip())
                if not canonical or canonical in seen:
                    continue
                seen.add(canonical)
                product_urls.append(canonical)

        try:
            index_text = self.fetcher.fetch(SITEMAP_INDEX_URL, timeout=15)
            root = ET.fromstring(index_text)
        except Exception:
            return []

        tag = root.tag
        is_index = tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag
        if not is_index:
            # Sitemap index shape changed — treat as a flat urlset anyway.
            parse_urlset_locs(index_text)
            return product_urls

        child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
        fetched = 0
        for child_url in child_sitemap_urls:
            if not _is_catalog_child_sitemap(child_url):
                continue
            if fetched > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            fetched += 1
            try:
                child_text = self.fetcher.fetch(child_url, timeout=30)
            except Exception:
                continue
            parse_urlset_locs(child_text)

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Mackin product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL isn't product-shaped or when no name surfaces.
        Price and SKU are only emitted for /product/ (WooCommerce) pages;
        /item/ pages have neither.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        # RAYS/Advan wheel models are routinely 2 chars ("M8", "S5", "R6") —
        # a 3-char floor silently drops those. Drop empty only; the JSON-LD
        # graph always emits a WebPage.name so empty means genuinely no page.
        if not name:
            return None

        description = _extract_description(soup)
        price_cents = _extract_price_cents(soup)
        part_number = _extract_part_number(soup)
        part_manufacturer = _extract_part_manufacturer(soup, url=url, name=name)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=_canonicalize_product_url(url) or url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )


# Yoast's index ships many child urlsets (post, page, item, item2, dealer,
# product, category, pwb-brand, product_cat, product_shipping_class). Only
# the item* and product children carry product URLs we can parse.
_CATALOG_CHILD_SITEMAP_RE = re.compile(
    r"/(item-sitemap\d*|product-sitemap)\.xml$",
    re.IGNORECASE,
)


def _is_catalog_child_sitemap(url: str) -> bool:
    """True if ``url`` points at a Yoast child sitemap that carries products."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return bool(_CATALOG_CHILD_SITEMAP_RE.search(path))
