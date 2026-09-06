"""Bug report and app settings repositories on DynamoDB (moto-backed)."""

from typing import Any

from uuid6 import uuid7

from app.db.dynamo.app_settings import SETTINGS_ID, AppSettingsRepository
from app.db.dynamo.bug_reports import BugReport, BugReportRepository


def _bug_report(**extra: Any) -> BugReport:
    return BugReport(title="Broken", description="It broke", **extra)


def test_list_filtered_by_status_and_priority_newest_first(dynamo_tables: Any) -> None:
    repo = BugReportRepository()
    first = repo.create(_bug_report(priority="high"))
    second = repo.create(_bug_report(priority="low"))
    third = repo.create(_bug_report(status="resolved", priority="high"))

    assert [report.id for report in repo.list_filtered()] == [third.id, second.id, first.id]
    assert [report.id for report in repo.list_filtered(status="pending")] == [second.id, first.id]
    assert [report.id for report in repo.list_filtered(priority="high")] == [third.id, first.id]
    assert [report.id for report in repo.list_filtered(status="pending", priority="high")] == [first.id]
    assert repo.count() == 3


def test_anonymous_reports_have_no_user_and_purge_by_user(dynamo_tables: Any) -> None:
    repo = BugReportRepository()
    user_id = uuid7()
    anonymous = repo.create(_bug_report())
    owned = repo.create(_bug_report(user_id=user_id))

    fetched = repo.get_or_raise(anonymous.id)
    assert fetched.user_id is None and fetched.status == "pending" and fetched.priority == "medium"
    assert [report.id for report in repo.list_by_user(user_id)] == [owned.id]

    assert repo.delete_for_user(user_id) == 1
    assert repo.get(owned.id) is None
    assert repo.get(anonymous.id) is not None


def test_app_settings_singleton_round_trip(dynamo_tables: Any) -> None:
    repo = AppSettingsRepository()
    assert repo.premium_disabled() is False

    created = repo.get_or_create()
    assert created.id == SETTINGS_ID and created.premium_disabled is False
    assert repo.get_or_create().updated_at == created.updated_at

    updated = repo.update_settings(premium_disabled=True)
    assert updated.id == SETTINGS_ID and updated.premium_disabled is True
    assert updated.updated_at >= created.updated_at
    assert repo.premium_disabled() is True
    assert repo.get(SETTINGS_ID) is not None and repo.get(SETTINGS_ID).premium_disabled is True  # type: ignore[union-attr]

    assert repo.update_settings().premium_disabled is True
    assert repo.update_settings(premium_disabled=False).premium_disabled is False
