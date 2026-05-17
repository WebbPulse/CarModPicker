"""Dynamic XML sitemap generation for Google Search Console.

The frontend is a static SPA on S3/CloudFront and cannot generate a sitemap
from the database, so the backend produces one here. A sitemap *index* is
served at ``/sitemap.xml`` and points at per-type child sitemaps:

    /sitemap.xml              -> sitemap index
    /sitemap-static.xml       -> hand-curated landing/marketing pages
    /sitemap-parts.xml        -> every canonical part
    /sitemap-cars.xml         -> every car generation (seed data)
    /sitemap-build-lists.xml  -> every build list (all are publicly readable)

URLs are absolute against ``settings.frontend_base_url`` (the SPA origin),
not the API host. User profiles are intentionally excluded — they are thin,
low-value pages and listing them invites privacy/SEO noise.

Sitemaps protocol limits each file to 50,000 URLs / 50MB. Each child sitemap
is paginated via ``?page=N`` and the index enumerates one entry per page so
we never exceed the per-file cap even as the catalog grows.
"""

from __future__ import annotations

from datetime import datetime
from html import escape as _html_escape

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car_generation import CarGeneration as DBCarGeneration
from app.api.models.part import Part as DBPart
from app.core.config import settings

# Sitemaps protocol hard cap is 50,000 URLs per file; stay well under it so a
# single page is always a valid sitemap even with metadata overhead.
URLS_PER_PAGE = 20_000

# Child sitemap identifiers (also the URL path segment: /sitemap-<name>.xml).
SITEMAP_STATIC = "static"
SITEMAP_PARTS = "parts"
SITEMAP_CARS = "cars"
SITEMAP_BUILD_LISTS = "build-lists"

# Static, hand-maintained pages. Mirrors the public, indexable routes from the
# frontend router (kept in sync with frontend/public/robots.txt Disallow list:
# anything disallowed there must NOT appear here). (path, changefreq, priority)
_STATIC_PAGES: list[tuple[str, str, str]] = [
    ("/", "daily", "1.0"),
    ("/build-lists", "daily", "0.9"),
    ("/search", "weekly", "0.7"),
    ("/about", "monthly", "0.6"),
    ("/pricing", "monthly", "0.6"),
    ("/support", "monthly", "0.5"),
    ("/contact-us", "monthly", "0.4"),
    ("/privacy-policy", "yearly", "0.3"),
    ("/terms-of-service", "yearly", "0.3"),
]


def _base_url() -> str:
    """SPA origin without trailing slash, e.g. https://www.carmodpicker.com."""
    return settings.frontend_base_url.rstrip("/")


def _api_base_url() -> str:
    """Origin the sitemap files themselves are served from (this backend).

    The index must reference child sitemaps by absolute URL, and they live on
    the API host, not the SPA host."""
    if not settings.is_production:
        return "http://localhost:8000"
    if settings.APP_ENVIRONMENT.lower() == "staging":
        return "https://api.staging.carmodpicker.com"
    return "https://api.carmodpicker.com"


def escape(text: str) -> str:
    """Escape a string for safe inclusion in XML text/attribute content.

    Uses ``html.escape`` (escapes & < > " ') purely for *output* — this
    module never parses XML, so the XML-parsing attack class does not apply
    here."""
    return _html_escape(text, quote=True)


def _w3c_datetime(dt: datetime) -> str:
    """Format a datetime as a W3C/ISO-8601 string for <lastmod>."""
    return dt.replace(microsecond=0).isoformat()


def _url_element(
    loc: str,
    *,
    lastmod: datetime | None = None,
    changefreq: str | None = None,
    priority: str | None = None,
) -> str:
    parts = [f"  <url>\n    <loc>{escape(loc)}</loc>"]
    if lastmod is not None:
        parts.append(f"    <lastmod>{_w3c_datetime(lastmod)}</lastmod>")
    if changefreq is not None:
        parts.append(f"    <changefreq>{changefreq}</changefreq>")
    if priority is not None:
        parts.append(f"    <priority>{priority}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


def _urlset(url_elements: list[str]) -> str:
    body = "\n".join(url_elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


# --- Per-type counting + row queries -------------------------------------


def _parts_query():
    # Only canonical parts: a non-null canonical_part_id means this row is a
    # duplicate whose surface page redirects to the canonical, so indexing it
    # would create duplicate-content URLs.
    return select(DBPart).where(DBPart.canonical_part_id.is_(None))


def _build_lists_query():
    # Every build list is publicly readable by id (no privacy flag exists).
    return select(DBBuildList)


def _cars_query():
    return select(DBCarGeneration)


def _count(db: Session, base_stmt) -> int:
    return db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0


def page_count(total: int) -> int:
    """Number of sitemap pages for a total row count (>=1 so an empty type
    still yields one valid, empty child sitemap)."""
    if total <= 0:
        return 1
    return (total + URLS_PER_PAGE - 1) // URLS_PER_PAGE


# --- Public API ----------------------------------------------------------


def generate_sitemap_index(db: Session) -> str:
    """Sitemap index referencing every child sitemap page."""
    api = _api_base_url()
    now = _w3c_datetime(datetime.now().astimezone())

    sitemaps: list[str] = []

    def add(name: str, pages: int) -> None:
        for page in range(1, pages + 1):
            suffix = "" if page == 1 else f"?page={page}"
            loc = f"{api}/sitemap-{name}.xml{suffix}"
            sitemaps.append(
                "  <sitemap>\n" f"    <loc>{escape(loc)}</loc>\n" f"    <lastmod>{now}</lastmod>\n" "  </sitemap>"
            )

    add(SITEMAP_STATIC, 1)
    add(SITEMAP_PARTS, page_count(_count(db, _parts_query())))
    add(SITEMAP_CARS, page_count(_count(db, _cars_query())))
    add(SITEMAP_BUILD_LISTS, page_count(_count(db, _build_lists_query())))

    body = "\n".join(sitemaps)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</sitemapindex>\n"
    )


def generate_static_sitemap() -> str:
    base = _base_url()
    elements = [
        _url_element(f"{base}{path}", changefreq=changefreq, priority=priority)
        for path, changefreq, priority in _STATIC_PAGES
    ]
    return _urlset(elements)


def _entity_sitemap(
    db: Session,
    base_stmt,
    id_attr: str,
    url_prefix: str,
    page: int,
    *,
    changefreq: str,
    priority: str,
) -> str:
    """Build one page of a child sitemap for a DB-backed entity type.

    Ordered by id so pagination is stable across requests."""
    base = _base_url()
    offset = (page - 1) * URLS_PER_PAGE
    model = base_stmt.column_descriptions[0]["entity"]
    stmt = base_stmt.order_by(model.id).offset(offset).limit(URLS_PER_PAGE)
    elements: list[str] = []
    for row in db.scalars(stmt).all():
        loc = f"{base}{url_prefix}/{getattr(row, id_attr)}"
        elements.append(
            _url_element(
                loc,
                lastmod=getattr(row, "updated_at", None),
                changefreq=changefreq,
                priority=priority,
            )
        )
    return _urlset(elements)


def generate_child_sitemap(db: Session, name: str, page: int) -> str | None:
    """Render child sitemap ``name`` page ``page`` (1-based).

    Returns None for an unknown name so the route can 404."""
    if page < 1:
        page = 1
    if name == SITEMAP_STATIC:
        return generate_static_sitemap()
    if name == SITEMAP_PARTS:
        return _entity_sitemap(
            db,
            _parts_query(),
            "id",
            "/parts",
            page,
            changefreq="weekly",
            priority="0.7",
        )
    if name == SITEMAP_CARS:
        return _entity_sitemap(
            db,
            _cars_query(),
            "id",
            "/car-generations",
            page,
            changefreq="monthly",
            priority="0.6",
        )
    if name == SITEMAP_BUILD_LISTS:
        return _entity_sitemap(
            db,
            _build_lists_query(),
            "id",
            "/build-lists",
            page,
            changefreq="weekly",
            priority="0.6",
        )
    return None
