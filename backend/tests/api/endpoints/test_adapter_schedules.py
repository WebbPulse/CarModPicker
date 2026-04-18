"""Tests for the /admin/adapter-schedules router."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.adapter_schedule import AdapterSchedule
from app.api.services import adapter_schedule_service
from app.core.config import settings
from tests.api.endpoints.test_admin import (
    create_and_login_admin_user,
    create_and_login_user,
)
from tests.conftest import get_default_category_id


@pytest.fixture(autouse=True)
def _seed_adapter_rows_and_stub_boto(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Seed rows for the registered adapters and inject a shared mock scheduler."""
    from app.crawlers.adapters import ADAPTER_REGISTRY

    category_id = get_default_category_id(db_session)
    for name in ADAPTER_REGISTRY.keys():
        existing = db_session.query(AdapterSchedule).filter(AdapterSchedule.adapter_name == name).first()
        if existing is None:
            db_session.add(
                AdapterSchedule(
                    adapter_name=name,
                    enabled=False,
                    schedule_expression="cron(0 2 1 * ? *)",
                    delay_sec=2.5,
                    per_run_limit=None,
                    skip_known_urls=False,
                    default_category_id=category_id,
                )
            )
    db_session.commit()

    monkeypatch.setattr(
        settings,
        "SCHEDULER_TARGET_EVENT_BUS_ARN",
        "arn:aws:events:us-east-1:123:event-bus/default",
    )
    monkeypatch.setattr(settings, "SCHEDULER_TARGET_ROLE_ARN", "arn:aws:iam::123:role/x")
    monkeypatch.setattr(settings, "SCHEDULER_GROUP_NAME", "default")
    monkeypatch.setattr(settings, "SCHEDULER_CRAWLER_SCHEDULE_NAME", "test-crawler-run")

    scheduler_client = MagicMock()
    scheduler_client.get_schedule.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule"
    )
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: scheduler_client)
    return scheduler_client


def test_list_requires_admin(client: TestClient, db_session: Session) -> None:
    token = create_and_login_user(client, db_session, "adapter_sched_non_admin")
    response = client.get(
        f"{settings.API_STR}/admin/adapter-schedules/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_returns_all_rows(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "adapter_sched_list")
    response = client.get(
        f"{settings.API_STR}/admin/adapter-schedules/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    names = [row["adapter_name"] for row in body["items"]]
    assert "a90shop" in names
    assert "studiorsr" in names
    assert body["presets"]["monthly"].startswith("cron(")


def test_patch_unknown_adapter_404(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "adapter_sched_404")
    response = client.patch(
        f"{settings.API_STR}/admin/adapter-schedules/not-a-real-adapter",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},
    )
    assert response.status_code == 404


def test_patch_toggles_enabled_and_calls_reconcile(
    client: TestClient, db_session: Session, _seed_adapter_rows_and_stub_boto: MagicMock
) -> None:
    token = create_and_login_admin_user(client, db_session, "adapter_sched_patch")
    response = client.patch(
        f"{settings.API_STR}/admin/adapter-schedules/a90shop",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True, "preset": "weekly"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert body["schedule_expression"] == adapter_schedule_service.CRON_PRESETS["weekly"]
    assert body["last_reconciled_at"] is not None

    # Reconcile hit get_schedule once (ResourceNotFound) then create_schedule once.
    _seed_adapter_rows_and_stub_boto.create_schedule.assert_called_once()


def test_patch_aws_error_returns_502_but_persists(
    client: TestClient, db_session: Session, _seed_adapter_rows_and_stub_boto: MagicMock
) -> None:
    _seed_adapter_rows_and_stub_boto.get_schedule.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetSchedule"
    )
    token = create_and_login_admin_user(client, db_session, "adapter_sched_502")
    response = client.patch(
        f"{settings.API_STR}/admin/adapter-schedules/a90shop",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True, "delay_sec": 30},
    )
    assert response.status_code == 502, response.text

    row = db_session.query(AdapterSchedule).filter(AdapterSchedule.adapter_name == "a90shop").first()
    assert row is not None
    # DB change is persisted even though AWS failed.
    db_session.refresh(row)
    assert row.enabled is True
    assert row.delay_sec == 30
    assert row.last_reconcile_error is not None


def test_patch_clear_per_run_limit(client: TestClient, db_session: Session) -> None:
    row = db_session.query(AdapterSchedule).filter(AdapterSchedule.adapter_name == "a90shop").first()
    assert row is not None
    row.per_run_limit = 42
    db_session.commit()

    token = create_and_login_admin_user(client, db_session, "adapter_sched_clear")
    response = client.patch(
        f"{settings.API_STR}/admin/adapter-schedules/a90shop",
        headers={"Authorization": f"Bearer {token}"},
        json={"clear_per_run_limit": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["per_run_limit"] is None


def test_reconcile_all(client: TestClient, db_session: Session, _seed_adapter_rows_and_stub_boto: MagicMock) -> None:
    token = create_and_login_admin_user(client, db_session, "adapter_sched_reconcile_all")
    response = client.post(
        f"{settings.API_STR}/admin/adapter-schedules/reconcile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert len(results) >= 2
    assert all(r["ok"] for r in results)
