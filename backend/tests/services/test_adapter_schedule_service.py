"""Tests for app.api.services.adapter_schedule_service — boto3 is mocked."""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.api.models.adapter_schedule import AdapterSchedule
from app.api.services import adapter_schedule_service
from tests.conftest import get_default_category_id


@pytest.fixture(autouse=True)
def _configure_scheduler_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply fake ARNs so _require_target_config() doesn't raise."""
    from app.core.config import settings as app_settings

    monkeypatch.setattr(
        app_settings,
        "SCHEDULER_TARGET_EVENT_BUS_ARN",
        "arn:aws:events:us-east-1:123:event-bus/default",
    )
    monkeypatch.setattr(
        app_settings,
        "SCHEDULER_TARGET_ROLE_ARN",
        "arn:aws:iam::123:role/fake-scheduler",
    )
    monkeypatch.setattr(app_settings, "SCHEDULER_GROUP_NAME", "default")
    monkeypatch.setattr(app_settings, "SCHEDULER_CRAWLER_SCHEDULE_NAME", "test-crawler-run")


def _make_row(db_session: Session, *, adapter_name: str = "a90shop", enabled: bool = True) -> AdapterSchedule:
    row = AdapterSchedule(
        adapter_name=adapter_name,
        enabled=enabled,
        schedule_expression="cron(0 2 1 * ? *)",
        delay_sec=5.0,
        per_run_limit=10,
        skip_known_urls=False,
        default_category_id=get_default_category_id(db_session),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_resolve_preset_or_expression_prefers_preset() -> None:
    assert (
        adapter_schedule_service.resolve_preset_or_expression(
            preset="daily", expression="cron(0 12 * * ? *)", current="cron(0 0 * * ? *)"
        )
        == adapter_schedule_service.CRON_PRESETS["daily"]
    )


def test_resolve_preset_or_expression_uses_expression_when_no_preset() -> None:
    assert (
        adapter_schedule_service.resolve_preset_or_expression(
            preset=None, expression="cron(0 12 * * ? *)", current="cron(0 0 * * ? *)"
        )
        == "cron(0 12 * * ? *)"
    )


def test_resolve_preset_or_expression_falls_back_to_current() -> None:
    assert (
        adapter_schedule_service.resolve_preset_or_expression(preset=None, expression=None, current="cron(X)")
        == "cron(X)"
    )


def test_resolve_preset_or_expression_unknown_preset_raises() -> None:
    with pytest.raises(ValueError):
        adapter_schedule_service.resolve_preset_or_expression(preset="bogus", expression=None, current="cron(0)")


def test_preset_name_for_expression() -> None:
    assert (
        adapter_schedule_service.preset_name_for_expression(adapter_schedule_service.CRON_PRESETS["weekly"]) == "weekly"
    )
    assert adapter_schedule_service.preset_name_for_expression("cron(0 7 * * ? *)") == "custom"


def test_schedule_name_strips_crawler_run_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SCHEDULER_CRAWLER_SCHEDULE_NAME", "carmodpicker-prod-crawler-run")
    assert adapter_schedule_service._schedule_name_for("a90shop") == "carmodpicker-prod-crawler-a90shop"


def test_reconcile_creates_schedule_when_missing(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _make_row(db_session)

    client = MagicMock()
    not_found = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule")
    client.get_schedule.side_effect = not_found

    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    adapter_schedule_service.reconcile_adapter_schedule(db_session, row)

    client.create_schedule.assert_called_once()
    client.update_schedule.assert_not_called()
    kwargs = client.create_schedule.call_args.kwargs
    assert kwargs["State"] == "ENABLED"
    assert kwargs["ScheduleExpression"] == row.schedule_expression
    assert kwargs["Name"].endswith(f"-crawler-{row.adapter_name}")
    payload = json.loads(kwargs["Target"]["Input"])
    assert payload["adapters"] == [row.adapter_name]
    assert payload["delay_sec"] == row.delay_sec
    assert payload["global_limit"] == row.per_run_limit

    db_session.refresh(row)
    assert row.last_reconciled_at is not None
    assert row.last_reconcile_error is None


def test_reconcile_updates_existing_schedule(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _make_row(db_session, adapter_name="studiorsr", enabled=False)

    client = MagicMock()
    client.get_schedule.return_value = {"Name": "dummy"}
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    adapter_schedule_service.reconcile_adapter_schedule(db_session, row)

    client.update_schedule.assert_called_once()
    client.create_schedule.assert_not_called()
    kwargs = client.update_schedule.call_args.kwargs
    assert kwargs["State"] == "DISABLED"


def test_reconcile_records_error_and_reraises(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _make_row(db_session)

    client = MagicMock()
    boom = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "nope"}}, "GetSchedule")
    client.get_schedule.side_effect = boom
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    with pytest.raises(ClientError):
        adapter_schedule_service.reconcile_adapter_schedule(db_session, row)

    db_session.refresh(row)
    assert row.last_reconcile_error is not None
    assert "AccessDeniedException" in row.last_reconcile_error
    assert row.last_reconciled_at is None


def test_reconcile_without_target_config_raises(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SCHEDULER_TARGET_EVENT_BUS_ARN", "")
    row = _make_row(db_session, adapter_name="generic")

    client = MagicMock()
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    with pytest.raises(adapter_schedule_service.AwsSchedulerUnavailable):
        adapter_schedule_service.reconcile_adapter_schedule(db_session, row)

    db_session.refresh(row)
    assert row.last_reconcile_error is not None


def test_delete_adapter_schedule_ignores_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.delete_schedule.side_effect = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DeleteSchedule")
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    adapter_schedule_service.delete_adapter_schedule("a90shop")  # does not raise


def test_reconcile_all_continues_past_failures(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row_ok = _make_row(db_session, adapter_name="a90shop")
    row_fail = _make_row(db_session, adapter_name="studiorsr")

    client = MagicMock()

    def get_schedule_side_effect(**kwargs: str) -> dict:
        if row_fail.adapter_name in kwargs.get("Name", ""):
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "nope"}},
                "GetSchedule",
            )
        raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule")

    client.get_schedule.side_effect = get_schedule_side_effect
    monkeypatch.setattr(adapter_schedule_service, "_get_scheduler_client", lambda: client)

    results = adapter_schedule_service.reconcile_all(db_session)
    outcome = {r["adapter_name"]: r for r in results}
    assert outcome[row_ok.adapter_name]["ok"] is True
    assert outcome[row_fail.adapter_name]["ok"] is False
    assert outcome[row_fail.adapter_name]["error"] is not None
