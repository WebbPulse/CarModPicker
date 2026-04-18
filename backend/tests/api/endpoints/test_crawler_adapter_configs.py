"""Tests for the /admin/crawler-adapter-configs router."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.crawler_adapter_config import CrawlerAdapterConfig
from app.core.config import settings
from tests.api.endpoints.test_admin import create_and_login_admin_user, create_and_login_user
from tests.conftest import get_default_category_id


@pytest.fixture(autouse=True)
def _seed_configs(db_session: Session) -> None:
    from app.crawlers.adapters import ADAPTER_REGISTRY

    category_id = get_default_category_id(db_session)
    for name in ADAPTER_REGISTRY.keys():
        existing = db_session.query(CrawlerAdapterConfig).filter(CrawlerAdapterConfig.adapter_name == name).first()
        if existing is None:
            db_session.add(
                CrawlerAdapterConfig(
                    adapter_name=name,
                    delay_sec=2.5,
                    per_run_limit=None,
                    skip_known_urls=False,
                    default_category_id=category_id,
                )
            )
    db_session.commit()


def _url(suffix: str = "") -> str:
    return f"{settings.API_STR}/admin/crawler-adapter-configs{suffix}"


def test_list_requires_admin(client: TestClient, db_session: Session) -> None:
    token = create_and_login_user(client, db_session, "cfg_non_admin")
    response = client.get(_url("/"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_returns_all_configs(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "cfg_list")
    response = client.get(_url("/"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    names = [row["adapter_name"] for row in response.json()["items"]]
    assert "a90shop" in names
    assert "studiorsr" in names


def test_patch_updates_delay_no_boto_call(client: TestClient, db_session: Session) -> None:
    """Editing adapter tuning must not require any AWS/boto reconcile."""
    token = create_and_login_admin_user(client, db_session, "cfg_patch")
    response = client.patch(
        _url("/a90shop"),
        headers={"Authorization": f"Bearer {token}"},
        json={"delay_sec": 12.5, "per_run_limit": 100, "skip_known_urls": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["delay_sec"] == 12.5
    assert body["per_run_limit"] == 100
    assert body["skip_known_urls"] is True


def test_patch_clear_per_run_limit(client: TestClient, db_session: Session) -> None:
    row = db_session.query(CrawlerAdapterConfig).filter(CrawlerAdapterConfig.adapter_name == "a90shop").first()
    assert row is not None
    row.per_run_limit = 42
    db_session.commit()

    token = create_and_login_admin_user(client, db_session, "cfg_clear")
    response = client.patch(
        _url("/a90shop"),
        headers={"Authorization": f"Bearer {token}"},
        json={"clear_per_run_limit": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["per_run_limit"] is None


def test_patch_unknown_adapter_404(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "cfg_404")
    response = client.patch(
        _url("/not-a-real-adapter"),
        headers={"Authorization": f"Bearer {token}"},
        json={"delay_sec": 5},
    )
    assert response.status_code == 404
