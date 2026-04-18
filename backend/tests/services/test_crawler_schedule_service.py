"""Tests for app.api.services.crawler_schedule_service — boto3 is mocked."""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.api.models.crawler_schedule import CrawlerSchedule, CrawlerScheduleAdapter
from app.api.services import crawler_schedule_service


@pytest.fixture(autouse=True)
def _configure_scheduler_env(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _make_schedule(db_session: Session, *, name: str = "retailers-daily", enabled: bool = True) -> CrawlerSchedule:
    row = CrawlerSchedule(
        name=name,
        description=None,
        enabled=enabled,
        schedule_expression="cron(0 2 1 * ? *)",
    )
    row.adapters.append(CrawlerScheduleAdapter(adapter_name="a90shop"))
    row.adapters.append(CrawlerScheduleAdapter(adapter_name="studiorsr"))
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_resolve_preset_or_expression_prefers_preset() -> None:
    assert (
        crawler_schedule_service.resolve_preset_or_expression(
            preset="daily", expression="cron(0 12 * * ? *)", current="cron(0 0 * * ? *)"
        )
        == crawler_schedule_service.CRON_PRESETS["daily"]
    )


def test_resolve_preset_or_expression_uses_expression_when_no_preset() -> None:
    assert (
        crawler_schedule_service.resolve_preset_or_expression(
            preset=None, expression="cron(0 12 * * ? *)", current="cron(0 0 * * ? *)"
        )
        == "cron(0 12 * * ? *)"
    )


def test_resolve_preset_or_expression_unknown_preset_raises() -> None:
    with pytest.raises(ValueError):
        crawler_schedule_service.resolve_preset_or_expression(preset="bogus", expression=None, current="cron(0)")


def test_preset_name_for_expression() -> None:
    assert (
        crawler_schedule_service.preset_name_for_expression(crawler_schedule_service.CRON_PRESETS["weekly"]) == "weekly"
    )
    assert crawler_schedule_service.preset_name_for_expression("cron(0 7 * * ? *)") == "custom"


def test_schedule_name_strips_crawler_run_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SCHEDULER_CRAWLER_SCHEDULE_NAME", "carmodpicker-prod-crawler-run")
    assert (
        crawler_schedule_service.schedule_name_for("retailers-daily")
        == "carmodpicker-prod-crawler-sched-retailers-daily"
    )


def test_reconcile_creates_schedule_with_schedule_id_payload(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _make_schedule(db_session)

    client = MagicMock()
    client.get_schedule.side_effect = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule")
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    crawler_schedule_service.reconcile_schedule(db_session, row)

    client.create_schedule.assert_called_once()
    kwargs = client.create_schedule.call_args.kwargs
    assert kwargs["State"] == "ENABLED"
    assert kwargs["Name"].endswith("-crawler-sched-retailers-daily")
    payload = json.loads(kwargs["Target"]["Input"])
    # Target.Input must be schedule_id only — adapter config is dereferenced at firing time.
    assert payload == {"schedule_id": str(row.id)}

    db_session.refresh(row)
    assert row.last_reconciled_at is not None
    assert row.last_reconcile_error is None


def test_reconcile_updates_existing_schedule(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _make_schedule(db_session, name="archive-monthly", enabled=False)

    client = MagicMock()
    client.get_schedule.return_value = {"Name": "dummy"}
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    crawler_schedule_service.reconcile_schedule(db_session, row)
    client.update_schedule.assert_called_once()
    client.create_schedule.assert_not_called()
    assert client.update_schedule.call_args.kwargs["State"] == "DISABLED"


def test_reconcile_records_error_and_reraises(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _make_schedule(db_session, name="err-sched")

    client = MagicMock()
    boom = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "nope"}}, "GetSchedule")
    client.get_schedule.side_effect = boom
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    with pytest.raises(ClientError):
        crawler_schedule_service.reconcile_schedule(db_session, row)

    db_session.refresh(row)
    assert row.last_reconcile_error is not None
    assert "AccessDeniedException" in row.last_reconcile_error
    assert row.last_reconciled_at is None


def test_reconcile_without_target_config_raises(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SCHEDULER_TARGET_EVENT_BUS_ARN", "")
    row = _make_schedule(db_session, name="no-config")

    client = MagicMock()
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    with pytest.raises(crawler_schedule_service.AwsSchedulerUnavailable):
        crawler_schedule_service.reconcile_schedule(db_session, row)

    db_session.refresh(row)
    assert row.last_reconcile_error is not None


def test_delete_schedule_ignores_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.delete_schedule.side_effect = ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DeleteSchedule")
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)
    crawler_schedule_service.delete_schedule("retailers-daily")  # does not raise


def test_reconcile_all_continues_past_failures(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row_ok = _make_schedule(db_session, name="ok-sched")
    row_fail = _make_schedule(db_session, name="fail-sched")

    client = MagicMock()

    def get_schedule_side_effect(**kwargs: str) -> dict:
        if row_fail.name in kwargs.get("Name", ""):
            raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "nope"}}, "GetSchedule")
        raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "GetSchedule")

    client.get_schedule.side_effect = get_schedule_side_effect
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    results = crawler_schedule_service.reconcile_all(db_session)
    outcome = {r["schedule_name"]: r for r in results}
    assert outcome[row_ok.name]["ok"] is True
    assert outcome[row_fail.name]["ok"] is False


def test_sweep_orphan_schedules_deletes_unknown_and_keeps_live(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    live = _make_schedule(db_session, name="live")
    live_full_name = crawler_schedule_service.schedule_name_for(live.name)

    client = MagicMock()
    client.list_schedules.return_value = {
        "Schedules": [
            {"Name": live_full_name},
            {"Name": "test-crawler-sched-ghost"},
            {"Name": "test-crawler-a90shop"},  # legacy per-adapter schedule
        ],
        "NextToken": None,
    }
    monkeypatch.setattr(crawler_schedule_service, "_get_scheduler_client", lambda: client)

    deleted = crawler_schedule_service.sweep_orphan_schedules(db_session)

    assert live_full_name not in deleted
    assert "test-crawler-sched-ghost" in deleted
    assert "test-crawler-a90shop" in deleted
