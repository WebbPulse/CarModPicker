"""Admin canonical tools: link-group inspection, promote/unlink/link, rescan."""

import logging
import os
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.endpoints.parts import PartService
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer
from app.api.models.retailer import Retailer
from app.api.models.user import User
from app.api.schemas.part import PartCreate
from app.core.config import settings
from tests.conftest import get_default_category_id

logger = logging.getLogger(__name__)


def _auth_headers(client: TestClient, username: str) -> dict[str, str]:
    login = {"username": username, "password": "testpassword"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_retailer(db_session: Session, slug: str) -> Retailer:
    retailer = Retailer(
        name=f"retailer_{slug}_{os.getpid()}",
        domain=f"{slug}{os.getpid()}example.com",
        base_url=f"https://{slug}-example.com",
        is_active=True,
    )
    db_session.add(retailer)
    db_session.commit()
    db_session.refresh(retailer)
    return retailer


def _create_part(
    db_session: Session,
    user: User,
    manufacturer: PartManufacturer,
    *,
    product_url: str | None = None,
    retailer_id: UUID | None = None,
    part_number: str | None = None,
    gtin: str | None = None,
    image_urls: list[str] | None = None,
    description: str | None = None,
    name: str = "Test part",
) -> DBPart:
    svc = PartService()
    payload = PartCreate(
        name=name,
        description=description,
        image_urls=image_urls,
        category_id=get_default_category_id(db_session),
        part_manufacturer_id=manufacturer.id,
        part_number=part_number,
        gtin=gtin,
        retailer_id=retailer_id,
        product_url=product_url,
        is_universal=True,
    )
    return svc.create(db_session, payload, user, logger, additional_data={"source": "scraped"})


def test_link_group_endpoint_returns_canonical_and_siblings(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer_a = _make_retailer(db_session, "link-a")
    retailer_b = _make_retailer(db_session, "link-b")
    gtin = "012345679056"
    canonical = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://link-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    sibling = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://link-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert sibling.canonical_part_id == canonical.id

    headers = _auth_headers(client, test_admin_user.username)
    response = client.get(f"/api/admin/parts/{canonical.id}/link-group", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["canonical_id"] == str(canonical.id)
    ids = [m["id"] for m in body["members"]]
    assert str(canonical.id) in ids
    assert str(sibling.id) in ids
    # Canonical comes first in the ordering.
    assert body["members"][0]["id"] == str(canonical.id)
    assert body["members"][0]["is_canonical"] is True


def test_link_group_endpoint_requires_admin(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer = _make_retailer(db_session, "reject")
    part = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://reject-{os.getpid()}.example.com/p/1",
        retailer_id=retailer.id,
    )
    headers = _auth_headers(client, test_user.username)
    response = client.get(f"/api/admin/parts/{part.id}/link-group", headers=headers)
    assert response.status_code == 403


def test_promote_canonical_swaps_roles(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer_a = _make_retailer(db_session, "promote-a")
    retailer_b = _make_retailer(db_session, "promote-b")
    gtin = "012345679063"
    first = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://promote-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://promote-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id

    headers = _auth_headers(client, test_admin_user.username)
    response = client.post(
        "/api/admin/parts/promote-canonical",
        json={"part_id": str(second.id)},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["canonical_id"] == str(second.id)

    db_session.expire_all()
    refreshed_first = db_session.get(DBPart, first.id)
    refreshed_second = db_session.get(DBPart, second.id)
    assert refreshed_second is not None and refreshed_second.canonical_part_id is None
    assert refreshed_first is not None and refreshed_first.canonical_part_id == second.id


def test_unlink_detaches_part(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer_a = _make_retailer(db_session, "unlink-adm-a")
    retailer_b = _make_retailer(db_session, "unlink-adm-b")
    gtin = "012345679070"
    first = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://unlink-adm-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://unlink-adm-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id

    headers = _auth_headers(client, test_admin_user.username)
    response = client.post(
        "/api/admin/parts/unlink",
        json={"part_id": str(second.id)},
        headers=headers,
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(DBPart, second.id)
    assert refreshed is not None and refreshed.canonical_part_id is None


def test_manual_link_requires_canonical_target(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer_a = _make_retailer(db_session, "manlink-a")
    retailer_b = _make_retailer(db_session, "manlink-b")
    gtin = "012345679087"
    canonical = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://manlink-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    already_linked = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://manlink-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert already_linked.canonical_part_id == canonical.id

    # Create a standalone part the admin wants to link under the duplicate (not allowed).
    retailer_c = _make_retailer(db_session, "manlink-c")
    standalone = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://manlink-c-{os.getpid()}.example.com/p/3",
        retailer_id=retailer_c.id,
    )

    headers = _auth_headers(client, test_admin_user.username)
    bad = client.post(
        "/api/admin/parts/link",
        json={"duplicate_id": str(standalone.id), "canonical_id": str(already_linked.id)},
        headers=headers,
    )
    assert bad.status_code == 409

    ok = client.post(
        "/api/admin/parts/link",
        json={"duplicate_id": str(standalone.id), "canonical_id": str(canonical.id)},
        headers=headers,
    )
    assert ok.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(DBPart, standalone.id)
    assert refreshed is not None and refreshed.canonical_part_id == canonical.id


def test_rescan_dry_run_reports_diff_without_mutating(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    """A dry-run rescan should not modify any canonical_part_id."""
    retailer_a = _make_retailer(db_session, "rescan-a")
    retailer_b = _make_retailer(db_session, "rescan-b")
    gtin = "012345679094"
    first = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://rescan-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://rescan-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id

    # Break the existing link deliberately so the rescan should recreate it.
    second.canonical_part_id = None
    db_session.add(second)
    db_session.commit()

    headers = _auth_headers(client, test_admin_user.username)
    response = client.post(
        "/api/admin/parts/rescan",
        json={"dry_run": True, "batch_size": 100},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["changes"] >= 1
    # Nothing mutated.
    db_session.expire_all()
    refreshed = db_session.get(DBPart, second.id)
    assert refreshed is not None and refreshed.canonical_part_id is None


def test_rescan_execute_repairs_broken_links(
    db_session: Session,
    test_admin_user: User,
    test_part_manufacturer: PartManufacturer,
    client: TestClient,
) -> None:
    retailer_a = _make_retailer(db_session, "rescanx-a")
    retailer_b = _make_retailer(db_session, "rescanx-b")
    gtin = "012345679100"
    first = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://rescanx-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_admin_user,
        test_part_manufacturer,
        product_url=f"https://rescanx-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    second.canonical_part_id = None
    db_session.add(second)
    db_session.commit()

    headers = _auth_headers(client, test_admin_user.username)
    response = client.post(
        "/api/admin/parts/rescan",
        json={"dry_run": False, "batch_size": 100},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["changes"] >= 1

    db_session.expire_all()
    refreshed = db_session.get(DBPart, second.id)
    assert refreshed is not None and refreshed.canonical_part_id == first.id
