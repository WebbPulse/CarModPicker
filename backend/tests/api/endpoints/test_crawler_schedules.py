"""Tests for the /admin/crawler-schedules router."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.crawler_adapter_config import CrawlerAdapterConfig
from app.api.models.crawler_schedule import CrawlerSchedule, CrawlerScheduleAdapter
from app.api.services import crawler_schedule_service
from app.core.config import settings
from tests.api.endpoints.test_admin import create_and_login_admin_user, create_and_login_user
from tests.conftest import get_default_category_id


@pytest.fixture(autouse=True)
def _seed_configs_and_stub_boto(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
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

    monkeypatch.setattr(
        settings,
        "SCHEDULER_TARGET_EVENT_BUS_ARN",
        "arn:aws:events:us-east-1:123:event-bus/default",
    )
    monkeypatch.setattr(settings, "SCHEDULER_TARGET_ROLE_ARN", "arn:aws:iam::123:role/x")
    monkeypatch.setattr(settings, "SCHEDULER_GROUP_NAME", "default")
    monkeypatch.setattr(settings, "SCHEDULER_CRAWLER_SCHEDULE_NAME", "test-crawler-run")

    client = MagicMock()
    client.get_schedule.side_effect = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule")
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)
    return client


def _url(path: str = "") -> str:
    return f"{settings.API_STR}/admin/crawler-schedules{path}"


def test_list_requires_admin(client: TestClient, db_session: Session) -> None:
    token = create_and_login_user(client, db_session, "sched_non_admin")
    response = client.get(_url("/"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_create_schedule_reconciles_and_persists_members(
    client: TestClient, db_session: Session, _seed_configs_and_stub_boto: MagicMock
) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_create")
    response = client.post(
        _url("/"),
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "retailers-daily",
            "enabled": True,
            "preset": "daily",
            "adapters": ["a90shop", "studiorsr"],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "retailers-daily"
    assert body["enabled"] is True
    assert body["schedule_expression"] == crawler_schedule_service.CRON_PRESETS["daily"]
    assert {a["adapter_name"] for a in body["adapters"]} == {"a90shop", "studiorsr"}
    _seed_configs_and_stub_boto.create_schedule.assert_called_once()


def test_create_rejects_invalid_name(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_bad_name")
    response = client.post(
        _url("/"),
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Has Spaces", "preset": "daily", "adapters": ["a90shop"]},
    )
    assert response.status_code == 422


def test_create_rejects_unknown_adapter(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_bad_adapter")
    response = client.post(
        _url("/"),
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "bad-one", "preset": "daily", "adapters": ["nope"]},
    )
    assert response.status_code == 400


def test_create_conflict_on_duplicate_name(client: TestClient, db_session: Session) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_dup")
    payload = {"name": "weekly-one", "preset": "weekly", "adapters": ["a90shop"]}
    r1 = client.post(_url("/"), headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r1.status_code == 201, r1.text
    r2 = client.post(_url("/"), headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r2.status_code == 409


def test_patch_membership_change_does_not_call_boto(
    client: TestClient, db_session: Session, _seed_configs_and_stub_boto: MagicMock
) -> None:
    """Pure-membership edit must not issue any boto scheduler calls."""
    token = create_and_login_admin_user(client, db_session, "sched_membership")

    # Seed a schedule directly so we can assert no calls happen on the membership PATCH.
    schedule = CrawlerSchedule(
        name="members-test",
        enabled=False,
        schedule_expression="cron(0 2 1 * ? *)",
    )
    schedule.adapters.append(CrawlerScheduleAdapter(adapter_name="a90shop"))
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)

    _seed_configs_and_stub_boto.reset_mock()

    response = client.patch(
        _url(f"/{schedule.id}"),
        headers={"Authorization": f"Bearer {token}"},
        json={"adapters": ["a90shop", "studiorsr"]},
    )
    assert response.status_code == 200, response.text
    assert {a["adapter_name"] for a in response.json()["adapters"]} == {"a90shop", "studiorsr"}

    _seed_configs_and_stub_boto.get_schedule.assert_not_called()
    _seed_configs_and_stub_boto.update_schedule.assert_not_called()
    _seed_configs_and_stub_boto.create_schedule.assert_not_called()


def test_patch_enabled_toggle_calls_reconcile(
    client: TestClient, db_session: Session, _seed_configs_and_stub_boto: MagicMock
) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_toggle")
    schedule = CrawlerSchedule(
        name="toggle-test",
        enabled=False,
        schedule_expression="cron(0 2 1 * ? *)",
    )
    schedule.adapters.append(CrawlerScheduleAdapter(adapter_name="a90shop"))
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)

    _seed_configs_and_stub_boto.reset_mock()
    _seed_configs_and_stub_boto.get_schedule.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule"
    )

    response = client.patch(
        _url(f"/{schedule.id}"),
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},
    )
    assert response.status_code == 200, response.text
    _seed_configs_and_stub_boto.create_schedule.assert_called_once()


def test_delete_schedule_calls_delete_then_removes_row(
    client: TestClient, db_session: Session, _seed_configs_and_stub_boto: MagicMock
) -> None:
    token = create_and_login_admin_user(client, db_session, "sched_delete")
    schedule = CrawlerSchedule(
        name="delete-me",
        enabled=False,
        schedule_expression="cron(0 2 1 * ? *)",
    )
    schedule.adapters.append(CrawlerScheduleAdapter(adapter_name="a90shop"))
    db_session.add(schedule)
    db_session.commit()
    schedule_id = schedule.id

    response = client.delete(_url(f"/{schedule_id}"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204

    _seed_configs_and_stub_boto.delete_schedule.assert_called_once()
    assert db_session.query(CrawlerSchedule).filter(CrawlerSchedule.id == schedule_id).first() is None


def test_reconcile_all(client: TestClient, db_session: Session, _seed_configs_and_stub_boto: MagicMock) -> None:
    schedule = CrawlerSchedule(
        name="recon",
        enabled=True,
        schedule_expression="cron(0 2 1 * ? *)",
    )
    schedule.adapters.append(CrawlerScheduleAdapter(adapter_name="a90shop"))
    db_session.add(schedule)
    db_session.commit()

    token = create_and_login_admin_user(client, db_session, "sched_reconcile_all")
    response = client.post(_url("/reconcile"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert any(r["schedule_name"] == "recon" and r["ok"] is True for r in results)
