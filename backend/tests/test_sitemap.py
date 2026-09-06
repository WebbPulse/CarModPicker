"""Coverage for the dynamic XML sitemap (SEO / Google Search Console).

Verifies the sitemap index fans out to child sitemaps, that parts are listed
by canonical id only (duplicates excluded), build lists are listed, child
sitemaps are valid XML, pagination is bounded, and unknown names 404.
"""

from __future__ import annotations

import uuid
from typing import Any
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from app.api.services import sitemap_service
from app.db.dynamo.build_lists import BuildList, BuildListRepository
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.users import User
from tests.conftest import get_default_category_id, save_catalog

SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _locs(xml: str) -> list[str]:
    """All non-empty <loc> text values in a sitemap document."""
    root = ET.fromstring(xml)
    return [e.text for e in root.iter(f"{SM_NS}loc") if e.text]


def _make_part(
    db: Any,
    user: User,
    *,
    canonical_part_id: uuid.UUID | None = None,
    name: str = "Sitemap Part",
) -> DBPart:
    return save_catalog(
        DBPart(
            name=name,
            category_id=get_default_category_id(db),
            user_id=user.id,
            is_universal=True,
            canonical_part_id=canonical_part_id,
        )
    )


def test_sitemap_index_lists_child_sitemaps(client: TestClient) -> None:
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "max-age=3600" in resp.headers.get("cache-control", "")

    assert ET.fromstring(resp.text).tag == f"{SM_NS}sitemapindex"
    locs = _locs(resp.text)
    assert any(loc.endswith("/sitemap-static.xml") for loc in locs)
    assert any(loc.endswith("/sitemap-parts.xml") for loc in locs)
    assert any(loc.endswith("/sitemap-cars.xml") for loc in locs)
    assert any(loc.endswith("/sitemap-build-lists.xml") for loc in locs)


def test_static_sitemap_is_valid_and_has_landing_pages(
    client: TestClient,
) -> None:
    resp = client.get("/sitemap-static.xml")
    assert resp.status_code == 200
    assert ET.fromstring(resp.text).tag == f"{SM_NS}urlset"
    locs = _locs(resp.text)
    assert any(loc.endswith("/") for loc in locs)
    assert any(loc.endswith("/about") for loc in locs)
    # Anything disallowed in robots.txt must never be advertised here.
    assert not any("/admin" in loc or "/profile" in loc for loc in locs)


def test_parts_sitemap_lists_canonical_only(client: TestClient, db_session: Any, test_user: User) -> None:
    canonical = _make_part(db_session, test_user, name="Canonical")
    duplicate = _make_part(
        db_session,
        test_user,
        name="Duplicate",
        canonical_part_id=canonical.id,
    )

    resp = client.get("/sitemap-parts.xml")
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    locs = _locs(resp.text)

    assert any(loc.endswith(f"/parts/{canonical.id}") for loc in locs)
    # The duplicate redirects to the canonical, so it must be excluded.
    assert not any(loc.endswith(f"/parts/{duplicate.id}") for loc in locs)
    # <lastmod> must be present for entity URLs.
    assert root.find(f"{SM_NS}url/{SM_NS}lastmod") is not None


def test_build_lists_sitemap_lists_entries(client: TestClient, db_session: Any, test_user: User) -> None:
    bl = BuildListRepository().create(BuildList(name="My Build", user_id=test_user.id))

    resp = client.get("/sitemap-build-lists.xml")
    assert resp.status_code == 200
    locs = _locs(resp.text)
    assert any(loc.endswith(f"/build-lists/{bl.id}") for loc in locs)


def test_empty_entity_sitemap_is_valid_xml(client: TestClient) -> None:
    # No car generations seeded in the test DB -> still a valid empty urlset.
    resp = client.get("/sitemap-cars.xml")
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.tag == f"{SM_NS}urlset"


def test_unknown_child_sitemap_404s(client: TestClient) -> None:
    resp = client.get("/sitemap-bogus.xml")
    assert resp.status_code == 404


def test_page_count_respects_url_cap() -> None:
    cap = sitemap_service.URLS_PER_PAGE
    assert sitemap_service.page_count(0) == 1
    assert sitemap_service.page_count(1) == 1
    assert sitemap_service.page_count(cap) == 1
    assert sitemap_service.page_count(cap + 1) == 2
    assert sitemap_service.page_count(cap * 3) == 3


def test_pagination_offsets_results(client: TestClient, db_session: Any, test_user: User, monkeypatch) -> None:
    # Shrink the page size so two parts span two pages without bulk seeding.
    monkeypatch.setattr(sitemap_service, "URLS_PER_PAGE", 1)
    p1 = _make_part(db_session, test_user, name="P1")
    p2 = _make_part(db_session, test_user, name="P2")

    page1 = client.get("/sitemap-parts.xml")
    page2 = client.get("/sitemap-parts.xml", params={"page": 2})
    assert page1.status_code == 200 and page2.status_code == 200

    locs1 = _locs(page1.text)
    locs2 = _locs(page2.text)
    assert len(locs1) == 1 and len(locs2) == 1
    all_ids = {str(p1.id), str(p2.id)}
    seen = {loc.rsplit("/", 1)[-1] for loc in locs1 + locs2}
    assert seen == all_ids

    # Index should now advertise multiple part pages.
    idx = client.get("/sitemap.xml")
    assert any("sitemap-parts.xml?page=2" in loc for loc in _locs(idx.text))
