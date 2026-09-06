"""Vote and report repositories on DynamoDB (moto-backed)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from uuid6 import uuid7

from app.db.dynamo.moderation import (
    Report,
    ReportRepository,
    Vote,
    VoteRepository,
    moderation_delete_actions,
)
from app.db.dynamo.repository import transact_write


def _vote(entity_id: UUID, user_id: UUID, vote_type: str = "upvote", entity_type: str = "part") -> Vote:
    return Vote(user_id=user_id, entity_type=entity_type, entity_id=entity_id, vote_type=vote_type)


def _report(entity_id: UUID, user_id: UUID, **extra: Any) -> Report:
    return Report(user_id=user_id, entity_type="part", entity_id=entity_id, reason="spam", **extra)


def test_user_vote_lookup_uses_entity_key(dynamo_tables: Any) -> None:
    votes = VoteRepository()
    part_id, user_id, other = uuid7(), uuid7(), uuid7()
    votes.create(_vote(part_id, user_id, "downvote"))
    votes.create(_vote(part_id, other))
    votes.create(_vote(uuid7(), user_id, entity_type="build_list"))

    found = votes.get_user_vote("part", part_id, user_id)
    assert found is not None and found.vote_type == "downvote"
    assert votes.get_user_vote("build_list", part_id, user_id) is None
    assert votes.counts("part", part_id) == (1, 1)


def test_tallies_and_user_votes_across_entities(dynamo_tables: Any) -> None:
    votes = VoteRepository()
    a, b, quiet, user_id = uuid7(), uuid7(), uuid7(), uuid7()
    votes.create(_vote(a, user_id))
    votes.create(_vote(a, uuid7()))
    votes.create(_vote(b, user_id, "downvote"))

    upvotes, downvotes = votes.tallies("part", [a, b, quiet])
    assert upvotes == {a: 2}
    assert downvotes == {b: 1}
    assert votes.user_votes("part", [a, b, quiet], user_id) == {a: "upvote", b: "downvote"}


def test_delete_helpers_scope_by_type_and_user(dynamo_tables: Any) -> None:
    votes = VoteRepository()
    user_id = uuid7()
    car_vote = votes.create(_vote(uuid7(), user_id, entity_type="car_generation"))
    part_vote = votes.create(_vote(uuid7(), user_id))
    keep = votes.create(_vote(uuid7(), uuid7()))

    assert votes.delete_for_entity_type("car_generation") == 1
    assert votes.get(car_vote.id) is None
    assert votes.delete_for_user(user_id) == 1
    assert votes.get(part_vote.id) is None
    assert votes.get(keep.id) is not None
    assert votes.count_by_entity_type() == {"part": 1}


def test_pending_report_lookup_ignores_resolved(dynamo_tables: Any) -> None:
    reports = ReportRepository()
    part_id, user_id = uuid7(), uuid7()
    reports.create(_report(part_id, user_id, status="resolved"))
    assert reports.pending_by_user("part", part_id, user_id) is None
    pending = reports.create(_report(part_id, user_id))
    found = reports.pending_by_user("part", part_id, user_id)
    assert found is not None and found.id == pending.id


def test_list_filtered_orders_newest_first(dynamo_tables: Any) -> None:
    reports = ReportRepository()
    user_id = uuid7()
    now = datetime.now(UTC)
    old = reports.put(_report(uuid7(), user_id, created_at=now - timedelta(days=1)))
    new = reports.put(_report(uuid7(), user_id))
    build_list = reports.put(
        Report(user_id=user_id, entity_type="build_list", entity_id=uuid7(), reason="spam", status="reviewed")
    )

    assert [r.id for r in reports.list_filtered()] == [build_list.id, new.id, old.id]
    assert [r.id for r in reports.list_filtered(status="pending")] == [new.id, old.id]
    assert [r.id for r in reports.list_filtered(entity_type="build_list")] == [build_list.id]
    assert [r.id for r in reports.list_filtered(entity_type="part", status="reviewed")] == []
    assert [r.id for r in reports.list_by_user(user_id, status="reviewed")] == [build_list.id]


def test_update_clears_admin_notes_with_none(dynamo_tables: Any) -> None:
    reports = ReportRepository()
    report = reports.create(_report(uuid7(), uuid7(), admin_notes="first pass"))
    updated = reports.update(report.id, status="dismissed", admin_notes=None, reviewed_by=uuid7())
    assert updated.status == "dismissed"
    assert updated.admin_notes is None
    assert updated.reviewed_by is not None


def test_moderation_delete_actions_remove_entity_rows(dynamo_tables: Any) -> None:
    votes, reports = VoteRepository(), ReportRepository()
    part_id, other_part = uuid7(), uuid7()
    votes.create(_vote(part_id, uuid7()))
    reports.create(_report(part_id, uuid7()))
    keep_vote = votes.create(_vote(other_part, uuid7()))

    actions = moderation_delete_actions("part", part_id, votes=votes, reports=reports)
    assert len(actions) == 2
    transact_write(actions)
    assert votes.for_entity("part", part_id) == []
    assert reports.for_entity("part", part_id) == []
    assert reports.entities_with_reports("part", [part_id, other_part]) == set()
    assert votes.get(keep_vote.id) is not None
