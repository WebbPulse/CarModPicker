"""Covers the user delete cascade: the users stream producer, the queue drainer,
idempotency under retry and bisect, and the same cascade against real repositories.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from app.consumers.user_delete import (
    MESSAGE_KIND,
    MESSAGE_VERSION,
    cascade_user_delete,
    group_records_by_user,
    handle_queue,
    handle_stream,
    is_queue_event,
    message_body,
    process_queue_records,
    process_stream_records,
    purge_identity,
    purge_owned_build_lists,
    purge_owned_moderation,
    purge_owned_parts,
    user_id_from_message,
    user_id_from_record,
)

QUEUE_URL = "https://sqs.us-west-2.amazonaws.com/123456789012/carmodpicker-test-user-delete"


def stream_record(
    user_id: str | None = None,
    sequence_number: str = "1",
    event_name: str = "MODIFY",
    deleted: bool = True,
    previously_deleted: bool = False,
    include_new_image: bool = True,
) -> Dict[str, Any]:
    """One users stream record in the low level wire shape an event source mapping delivers."""
    user_id = user_id or str(uuid4())
    new_image = {
        "id": {"S": user_id},
        "username": {"S": "someone"},
        "deleted": {"BOOL": deleted},
        "deleted_at": {"S": "2026-09-09T00:00:00Z"} if deleted else {"NULL": True},
    }
    old_image = {
        "id": {"S": user_id},
        "username": {"S": "someone"},
        "deleted": {"BOOL": previously_deleted},
    }

    dynamodb: Dict[str, Any] = {
        "Keys": {"id": {"S": user_id}},
        "OldImage": old_image,
        "SequenceNumber": sequence_number,
        "StreamViewType": "NEW_AND_OLD_IMAGES",
    }
    if include_new_image:
        dynamodb["NewImage"] = new_image

    return {
        "eventID": sequence_number,
        "eventName": event_name,
        "eventSource": "aws:dynamodb",
        "sequenceNumber": sequence_number,
        "dynamodb": dynamodb,
    }


def queue_record(user_id: str | None = None, message_id: str = "m1") -> Dict[str, Any]:
    """One SQS record in the shape an SQS event source mapping delivers."""
    return {
        "messageId": message_id,
        "receiptHandle": f"receipt-{message_id}",
        "body": message_body(UUID(user_id or str(uuid4()))),
        "eventSource": "aws:sqs",
        "awsRegion": "us-west-2",
    }


class FakeSqs:
    """Records what was sent, and can be told to fail for one user."""

    def __init__(self) -> None:
        """Start with nothing sent and no user configured to fail."""
        self.sent: List[Dict[str, str]] = []
        self.fail_for: set[str] = set()

    def send_message(self, QueueUrl: str, MessageBody: str) -> Dict[str, str]:  # noqa: N803
        """Record the send, or raise for a user marked as failing."""
        payload = json.loads(MessageBody)
        if payload["user_id"] in self.fail_for:
            raise RuntimeError("SQS is unavailable")
        self.sent.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})
        return {"MessageId": "sent"}

    @property
    def sent_user_ids(self) -> List[str]:
        """The user ids carried by every message sent so far."""
        return [json.loads(entry["MessageBody"])["user_id"] for entry in self.sent]


class FakeRow:
    """Anything the cascade only needs an id and an owner from."""

    def __init__(self, row_id: str, user_id: Optional[UUID] = None) -> None:
        """Hold an id and the owner the cascade keys on."""
        self.id = row_id
        self.user_id = user_id
        self.added_by = user_id


class FakeDeleteForUser:
    """A votes, reports or part_price_alerts repository: a second delete_for_user finds nothing."""

    def __init__(self, rows: Dict[str, int]) -> None:
        """Start from a per user row count with no user configured to fail."""
        self.rows = dict(rows)
        self.calls: List[UUID] = []
        self.fail_for: set[str] = set()

    def delete_for_user(self, user_id: UUID) -> int:
        """Remove and count the user's rows, or raise for a user marked as failing."""
        self.calls.append(user_id)
        if str(user_id) in self.fail_for:
            raise RuntimeError("DynamoDB throttled")
        return self.rows.pop(str(user_id), 0)


class FakeParts:
    """Owns part listing and bookkeeping; PartService.purge is stubbed separately."""

    def __init__(self, rows: Dict[str, List[str]]) -> None:
        """Start from a per user list of part ids."""
        self.rows = {key: list(value) for key, value in rows.items()}
        self.fail_for: set[str] = set()

    def list_by_user(self, user_id: UUID) -> List[FakeRow]:
        """The user's remaining parts, or raise for a user marked as failing."""
        if str(user_id) in self.fail_for:
            raise RuntimeError("DynamoDB throttled")
        return [FakeRow(part_id, user_id) for part_id in self.rows.get(str(user_id), [])]

    def forget(self, part_id: str) -> None:
        """Drop a part id from whichever user holds it."""
        for user_id, part_ids in self.rows.items():
            self.rows[user_id] = [existing for existing in part_ids if existing != part_id]


class FakeBuildLists:
    """A build_lists repository queried through the user index."""

    def __init__(self, rows: Dict[str, List[str]]) -> None:
        """Start from a per user list of build list ids."""
        self.rows = {key: list(value) for key, value in rows.items()}
        self.cascaded: List[str] = []
        self.fail_for: set[str] = set()

    def query_all(self, index: str, key_value: Any) -> List[FakeRow]:
        """The user's build lists off the user index, or raise for a user marked as failing."""
        assert index == "user_id-created_at-index"
        if str(key_value) in self.fail_for:
            raise RuntimeError("DynamoDB throttled")
        return [FakeRow(list_id, key_value) for list_id in self.rows.get(str(key_value), [])]

    def forget(self, list_id: str) -> None:
        """Drop a build list id from whichever user holds it."""
        for user_id, list_ids in self.rows.items():
            self.rows[user_id] = [existing for existing in list_ids if existing != list_id]


class FakeBuildListParts:
    """The second pass: rows this user added to somebody else's list."""

    def __init__(self, rows: Dict[str, UUID]) -> None:
        """Start from a mapping of usage row id to the user who added it."""
        self.rows = dict(rows)
        self.deleted: List[List[str]] = []

    def scan_all(self) -> List[FakeRow]:
        """Every build list part usage row still present."""
        return [FakeRow(usage_id, user_id) for usage_id, user_id in self.rows.items()]

    def batch_delete(self, keys: List[str]) -> None:
        """Record and apply one batch delete of usage rows."""
        self.deleted.append(list(keys))
        for key in keys:
            self.rows.pop(key, None)


class FakeIdentityRows:
    """An oauth_accounts or webauthn_credentials repository, which lists then deletes."""

    def __init__(self, rows: Dict[str, int]) -> None:
        """Start from a per user row count."""
        self.rows = dict(rows)
        self.fail_for: set[str] = set()

    def list_by_user(self, user_id: UUID) -> List[FakeRow]:
        """The user's identity rows, or raise for a user marked as failing."""
        if str(user_id) in self.fail_for:
            raise RuntimeError("DynamoDB throttled")
        return [FakeRow(f"row-{n}", user_id) for n in range(self.rows.get(str(user_id), 0))]

    def delete_all_for_user(self, user_id: UUID) -> None:
        """Remove every identity row for the user."""
        self.rows.pop(str(user_id), None)


class FakeBuildLogs:
    """Enough of build_logs and build_log_posts for the real delete action helper to run."""

    def __init__(self) -> None:
        """Start with no logs attached to any build list."""
        self.rows: Dict[str, List[str]] = {}

    def all_for_build_list(self, build_list_id: Any) -> List[FakeRow]:
        """The log ids attached to a build list."""
        return [FakeRow(log_id) for log_id in self.rows.get(str(build_list_id), [])]

    def all_for_build_log(self, build_log_id: Any) -> List[FakeRow]:
        """No posts, which is enough for the helper under test."""
        return []

    def delete_action(self, key: str) -> Dict[str, Any]:
        """A transaction delete action for one key."""
        return {"Delete": {"Key": {"id": key}}}


class FakeRepos:
    """A repository bundle covering every group the cascade touches."""

    def __init__(
        self,
        parts: FakeParts,
        part_price_alerts: FakeDeleteForUser,
        build_lists: FakeBuildLists,
        build_list_parts: FakeBuildListParts,
        votes: FakeDeleteForUser,
        reports: FakeDeleteForUser,
        oauth_accounts: FakeIdentityRows,
        webauthn_credentials: FakeIdentityRows,
    ) -> None:
        """Wire the per group fakes into one bundle."""
        self.parts = parts
        self.part_price_alerts = part_price_alerts
        self.build_lists = build_lists
        self.build_list_parts = build_list_parts
        self.votes = votes
        self.reports = reports
        self.oauth_accounts = oauth_accounts
        self.webauthn_credentials = webauthn_credentials
        self.build_list_phases = object()
        self.build_list_labor_estimates = object()
        self.build_logs = FakeBuildLogs()
        self.build_log_posts = FakeBuildLogs()

    def is_empty_for(self, user_id: str) -> bool:
        """Whether the cascade has removed everything belonging to this user."""
        return (
            not self.parts.rows.get(user_id)
            and user_id not in self.part_price_alerts.rows
            and not self.build_lists.rows.get(user_id)
            and not any(str(row.added_by) == user_id for row in self.build_list_parts.scan_all())
            and user_id not in self.votes.rows
            and user_id not in self.reports.rows
            and user_id not in self.oauth_accounts.rows
            and user_id not in self.webauthn_credentials.rows
        )


def build_world(user_id: str) -> FakeRepos:
    """A user with rows in every group the cascade touches."""
    return FakeRepos(
        parts=FakeParts({user_id: ["part-a", "part-b"]}),
        part_price_alerts=FakeDeleteForUser({user_id: 4}),
        build_lists=FakeBuildLists({user_id: ["list-a"]}),
        build_list_parts=FakeBuildListParts({"usage-elsewhere": UUID(user_id)}),
        votes=FakeDeleteForUser({user_id: 7}),
        reports=FakeDeleteForUser({user_id: 2}),
        oauth_accounts=FakeIdentityRows({user_id: 1}),
        webauthn_credentials=FakeIdentityRows({user_id: 3}),
    )


@pytest.fixture(autouse=True)
def stub_the_two_borrowed_helpers(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Stand in for PartService.purge and delete_build_list_cascade so layer one
    tests the cascade control flow rather than the helpers it reuses.
    """
    from app.db.dynamo.errors import ItemNotFound

    state: Dict[str, Any] = {"purge_failures": set(), "cascade_failures": set()}

    if "dynamo_tables" in request.fixturenames:
        return state

    def fake_purge(self: Any, part: Any) -> None:
        """Forget the part, raise ItemNotFound when it is already gone, or fail on demand."""
        if part.id in state["purge_failures"]:
            raise RuntimeError("DynamoDB throttled")
        if part.id not in self.repos.parts.rows.get(str(part.user_id), []):
            raise ItemNotFound("parts", part.id)
        self.repos.parts.forget(part.id)

    def fake_cascade(build_list_id: Any, *, build_lists: Any, **kwargs: Any) -> None:
        """Forget the build list, or fail on demand."""
        if build_list_id in state["cascade_failures"]:
            raise RuntimeError("DynamoDB throttled")
        build_lists.forget(build_list_id)

    monkeypatch.setattr("app.api.services.part_service.PartService.purge", fake_purge, raising=True)
    monkeypatch.setattr("app.db.dynamo.build_lists.delete_build_list_cascade", fake_cascade, raising=True)
    return state


class TestRecordParsing:
    """Which users stream records name a user whose cascade should run."""

    def test_a_tombstone_yields_its_user_id(self) -> None:
        """A fresh tombstone yields the user id to cascade."""
        user_id = str(uuid4())
        assert user_id_from_record(stream_record(user_id=user_id)) == UUID(user_id)

    def test_an_ordinary_profile_write_is_ignored(self) -> None:
        """An ordinary profile write is not a deletion, and this stream carries mostly those."""
        assert user_id_from_record(stream_record(deleted=False)) is None

    def test_an_already_tombstoned_row_is_ignored(self) -> None:
        """The cascade for it is already in flight or already done."""
        record = stream_record(deleted=True, previously_deleted=True)
        assert user_id_from_record(record) is None

    def test_a_remove_is_ignored(self) -> None:
        """The hard delete following the tombstone must not enqueue a second cascade."""
        record = stream_record(event_name="REMOVE", include_new_image=False)
        assert user_id_from_record(record) is None

    def test_a_malformed_id_is_ignored_rather_than_raising(self) -> None:
        """An unparseable id is ignored rather than raising."""
        record = stream_record()
        record["dynamodb"]["NewImage"]["id"] = {"S": "not-a-uuid"}
        assert user_id_from_record(record) is None

    def test_a_missing_id_is_ignored(self) -> None:
        """A record with no id is ignored."""
        record = stream_record()
        del record["dynamodb"]["NewImage"]["id"]
        assert user_id_from_record(record) is None


class TestGrouping:
    """How stream records collapse into one unit of work per user."""

    def test_many_records_on_one_user_collapse_to_one_unit(self) -> None:
        """Many records on one user collapse to one unit carrying every sequence number."""
        user_id = str(uuid4())
        records = [stream_record(user_id=user_id, sequence_number=str(n)) for n in range(5)]
        grouped = group_records_by_user(records)
        assert list(grouped) == [UUID(user_id)]
        assert grouped[UUID(user_id)] == ["0", "1", "2", "3", "4"]

    def test_records_for_different_users_stay_separate(self) -> None:
        """Records for different users stay in separate units."""
        first, second = str(uuid4()), str(uuid4())
        grouped = group_records_by_user(
            [
                stream_record(user_id=first, sequence_number="1"),
                stream_record(user_id=second, sequence_number="2"),
            ]
        )
        assert set(grouped) == {UUID(first), UUID(second)}

    def test_the_sequence_number_falls_back_to_the_nested_one(self) -> None:
        """The nested sequence number is used when the top level one is absent."""
        record = stream_record(sequence_number="42")
        del record["sequenceNumber"]
        grouped = group_records_by_user([record])
        assert list(grouped.values()) == [["42"]]


class TestStreamHalf:
    """The producer half: tombstones become one queue message per user."""

    def test_a_tombstone_is_enqueued_once(self) -> None:
        """A tombstone is enqueued once, on the configured queue."""
        user_id = str(uuid4())
        client = FakeSqs()
        failures = process_stream_records(client, QUEUE_URL, [stream_record(user_id=user_id)])
        assert failures == []
        assert client.sent_user_ids == [user_id]
        assert client.sent[0]["QueueUrl"] == QUEUE_URL

    def test_the_message_body_carries_only_the_user_id(self) -> None:
        """A snapshot of the owned rows would let a retry act on stale state."""
        user_id = uuid4()
        payload = json.loads(message_body(user_id))
        assert payload == {"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "user_id": str(user_id)}

    def test_fifty_records_on_one_user_send_one_message(self) -> None:
        """Fifty records on one user still send one message."""
        user_id = str(uuid4())
        client = FakeSqs()
        records = [stream_record(user_id=user_id, sequence_number=str(n)) for n in range(50)]
        process_stream_records(client, QUEUE_URL, records)
        assert len(client.sent) == 1

    def test_a_failed_send_reports_every_record_that_asked_for_it(self) -> None:
        """A failed send reports every record that asked for it."""
        user_id = str(uuid4())
        client = FakeSqs()
        client.fail_for.add(user_id)
        records = [stream_record(user_id=user_id, sequence_number=str(n)) for n in range(3)]
        failures = process_stream_records(client, QUEUE_URL, records)
        assert failures == ["0", "1", "2"]

    def test_one_failing_user_does_not_stop_the_others(self) -> None:
        """One failing user does not stop the others from being enqueued."""
        bad, good = str(uuid4()), str(uuid4())
        client = FakeSqs()
        client.fail_for.add(bad)
        failures = process_stream_records(
            client,
            QUEUE_URL,
            [
                stream_record(user_id=bad, sequence_number="1"),
                stream_record(user_id=good, sequence_number="2"),
            ],
        )
        assert failures == ["1"]
        assert client.sent_user_ids == [good]

    def test_handle_stream_returns_the_mapping_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """handle_stream returns the batchItemFailures shape the mapping expects."""
        monkeypatch.setenv("USER_DELETE_QUEUE_URL", QUEUE_URL)
        client = FakeSqs()
        result = handle_stream({"Records": [stream_record()]}, client)
        assert result == {"batchItemFailures": []}

    def test_a_missing_queue_url_raises_rather_than_acking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing queue url raises, because acking with nothing enqueued loses the cascade."""
        monkeypatch.delenv("USER_DELETE_QUEUE_URL", raising=False)
        with pytest.raises(RuntimeError, match="USER_DELETE_QUEUE_URL"):
            handle_stream({"Records": [stream_record()]}, FakeSqs())


class TestQueueHalf:
    """The drainer half: one message removes every row the user owns."""

    def test_a_message_drains_every_group(self) -> None:
        """One message drains every group the user owns."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        failures = process_queue_records(repos, [queue_record(user_id=user_id)])
        assert failures == []
        assert repos.is_empty_for(user_id)

    def test_the_counts_are_reported(self) -> None:
        """The cascade reports a per table count of what it removed."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        removed = cascade_user_delete(repos, UUID(user_id))
        assert removed == {
            "parts": 2,
            "parts_already_purged": 0,
            "part_price_alerts": 4,
            "build_lists": 1,
            "build_list_parts_added_elsewhere": 1,
            "votes": 7,
            "reports": 2,
            "oauth_accounts": 1,
            "webauthn_credentials": 3,
        }

    def test_each_group_reports_its_own_tables(self) -> None:
        """The four groups are separable, which is what makes the counts readable."""
        user_id = UUID(str(uuid4()))
        repos = build_world(str(user_id))
        assert set(purge_owned_parts(repos, user_id)) == {"parts", "parts_already_purged", "part_price_alerts"}
        assert set(purge_owned_build_lists(repos, user_id)) == {
            "build_lists",
            "build_list_parts_added_elsewhere",
        }
        assert purge_owned_moderation(repos, user_id) == {"votes": 7, "reports": 2}
        assert purge_identity(repos, user_id) == {"oauth_accounts": 1, "webauthn_credentials": 3}

    def test_a_build_list_row_added_to_someone_elses_list_is_removed(self) -> None:
        """The second pass, which is the one an owner-only query would miss."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        other = FakeRow("usage-theirs", uuid4())
        repos.build_list_parts.rows[other.id] = other.user_id  # type: ignore[assignment]

        purge_owned_build_lists(repos, UUID(user_id))

        assert repos.build_list_parts.deleted == [["usage-elsewhere"]]
        assert "usage-theirs" in repos.build_list_parts.rows, "somebody else's row is untouched"

    def test_a_failing_cascade_reports_its_message(self) -> None:
        """A failing cascade reports its own message id."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        repos.votes.fail_for.add(user_id)
        failures = process_queue_records(repos, [queue_record(user_id=user_id, message_id="m9")])
        assert failures == ["m9"]

    def test_one_failing_message_does_not_stop_the_others(self) -> None:
        """One failing message does not stop the others in the batch."""
        bad, good = str(uuid4()), str(uuid4())
        repos = FakeRepos(
            parts=FakeParts({bad: ["p1"], good: ["p2"]}),
            part_price_alerts=FakeDeleteForUser({bad: 1, good: 1}),
            build_lists=FakeBuildLists({bad: ["l1"], good: ["l2"]}),
            build_list_parts=FakeBuildListParts({"u1": UUID(bad), "u2": UUID(good)}),
            votes=FakeDeleteForUser({bad: 1, good: 1}),
            reports=FakeDeleteForUser({bad: 1, good: 1}),
            oauth_accounts=FakeIdentityRows({bad: 1, good: 1}),
            webauthn_credentials=FakeIdentityRows({bad: 1, good: 1}),
        )
        repos.votes.fail_for.add(bad)
        failures = process_queue_records(
            repos,
            [queue_record(user_id=bad, message_id="m1"), queue_record(user_id=good, message_id="m2")],
        )
        assert failures == ["m1"]
        assert repos.is_empty_for(good)

    def test_an_unreadable_body_is_dropped_rather_than_retried(self) -> None:
        """Five receives on a message no retry can fix would only spend the DLQ."""
        record = queue_record()
        record["body"] = "not json at all"
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_a_body_without_a_user_id_is_dropped(self) -> None:
        """A body carrying no user id is dropped rather than retried."""
        record = queue_record()
        record["body"] = json.dumps({"version": 1, "kind": MESSAGE_KIND})
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_a_malformed_user_id_is_dropped(self) -> None:
        """A body carrying an unparseable user id is dropped rather than retried."""
        record = queue_record()
        record["body"] = json.dumps({"version": 1, "kind": MESSAGE_KIND, "user_id": "nope"})
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_user_id_from_message_round_trips(self) -> None:
        """A message body round trips back to its user id."""
        user_id = uuid4()
        assert user_id_from_message(message_body(user_id)) == user_id

    def test_handle_queue_returns_the_mapping_contract(self) -> None:
        """handle_queue returns the batchItemFailures shape the mapping expects."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        result = handle_queue({"Records": [queue_record(user_id=user_id)]}, repos)
        assert result == {"batchItemFailures": []}


class TestEventDiscrimination:
    """Telling an SQS event apart from a stream event on the shared entrypoint."""

    def test_an_sqs_event_is_recognised(self) -> None:
        """An SQS event is routed to the queue half."""
        assert is_queue_event({"Records": [queue_record()]}) is True

    def test_a_stream_event_is_recognised(self) -> None:
        """A stream event is routed to the producer half."""
        assert is_queue_event({"Records": [stream_record()]}) is False

    def test_an_empty_batch_is_treated_as_a_stream_event(self) -> None:
        """Arbitrary, and consequence free: both halves answer it with no work."""
        assert is_queue_event({"Records": []}) is False


class TestIdempotency:
    """The property the whole design rests on. Mandatory per the row's brief."""

    def test_replaying_one_message_converges(self) -> None:
        """Replaying one message converges rather than failing."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        record = queue_record(user_id=user_id)

        assert process_queue_records(repos, [record]) == []
        assert repos.is_empty_for(user_id)

        assert process_queue_records(repos, [record]) == []
        assert repos.is_empty_for(user_id)

    def test_a_replay_issues_no_second_delete(self) -> None:
        """Not merely harmless: the second run writes nothing at all."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        cascade_user_delete(repos, UUID(user_id))
        deletes_after_first = len(repos.build_list_parts.deleted)

        removed = cascade_user_delete(repos, UUID(user_id))

        assert removed == {
            "parts": 0,
            "parts_already_purged": 0,
            "part_price_alerts": 0,
            "build_lists": 0,
            "build_list_parts_added_elsewhere": 0,
            "votes": 0,
            "reports": 0,
            "oauth_accounts": 0,
            "webauthn_credentials": 0,
        }
        assert len(repos.build_list_parts.deleted) == deletes_after_first

    def test_a_part_that_is_already_purged_is_counted_rather_than_failing(self) -> None:
        """An already purged part is counted separately rather than failing the cascade,
        which is what lets a mid cascade retry get past the parts step.
        """
        user_id = str(uuid4())
        repos = build_world(user_id)
        repos.parts.rows[user_id] = ["part-a"]
        listed = repos.parts.list_by_user

        def list_with_a_ghost(user: UUID) -> List[FakeRow]:
            """List the user's parts plus one that purge will find already gone."""
            return list(listed(user)) + [FakeRow("ghost", user)]

        repos.parts.list_by_user = list_with_a_ghost  # type: ignore[method-assign]

        counts = purge_owned_parts(repos, UUID(user_id))

        assert counts["parts"] == 1
        assert counts["parts_already_purged"] == 1, "counted separately, so the log tells a replay apart"

    def test_a_cascade_that_failed_midway_completes_on_retry(self) -> None:
        """The half-done case, which is what a retry actually encounters."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        repos.votes.fail_for.add(user_id)

        assert process_queue_records(repos, [queue_record(user_id=user_id, message_id="m1")]) == ["m1"]
        assert not repos.parts.rows[user_id], "the steps before the failure did run"
        assert not repos.build_lists.rows[user_id]
        assert user_id in repos.votes.rows, "the failing step left its rows"
        assert user_id in repos.oauth_accounts.rows, "the steps after it never ran"

        repos.votes.fail_for.clear()
        assert process_queue_records(repos, [queue_record(user_id=user_id, message_id="m1")]) == []
        assert repos.is_empty_for(user_id)

    def test_a_bisected_batch_reruns_the_successful_half_safely(self) -> None:
        """A bisected batch re-delivers the records that already succeeded, and rerunning
        them must neither fail nor remove anything else.
        """
        good_a, good_b, bad = str(uuid4()), str(uuid4()), str(uuid4())
        repos = FakeRepos(
            parts=FakeParts({good_a: ["pa"], good_b: ["pb"], bad: ["pc"]}),
            part_price_alerts=FakeDeleteForUser({good_a: 1, good_b: 1, bad: 1}),
            build_lists=FakeBuildLists({good_a: ["la"], good_b: ["lb"], bad: ["lc"]}),
            build_list_parts=FakeBuildListParts({"ua": UUID(good_a), "ub": UUID(good_b), "uc": UUID(bad)}),
            votes=FakeDeleteForUser({good_a: 1, good_b: 1, bad: 1}),
            reports=FakeDeleteForUser({good_a: 1, good_b: 1, bad: 1}),
            oauth_accounts=FakeIdentityRows({good_a: 1, good_b: 1, bad: 1}),
            webauthn_credentials=FakeIdentityRows({good_a: 1, good_b: 1, bad: 1}),
        )
        repos.votes.fail_for.add(bad)

        batch = [
            queue_record(user_id=good_a, message_id="m1"),
            queue_record(user_id=good_b, message_id="m2"),
            queue_record(user_id=bad, message_id="m3"),
        ]
        assert process_queue_records(repos, batch) == ["m3"]
        assert repos.is_empty_for(good_a) and repos.is_empty_for(good_b)

        repos.votes.fail_for.clear()
        assert process_queue_records(repos, batch) == []
        assert repos.is_empty_for(good_a)
        assert repos.is_empty_for(good_b)
        assert repos.is_empty_for(bad)

    def test_enqueueing_twice_is_safe_because_draining_twice_is(self) -> None:
        """Which is what lets the producer send without deduplication."""
        user_id = str(uuid4())
        client = FakeSqs()
        record = stream_record(user_id=user_id)
        process_stream_records(client, QUEUE_URL, [record])
        process_stream_records(client, QUEUE_URL, [record])
        assert client.sent_user_ids == [user_id, user_id]

        repos = build_world(user_id)
        records = [queue_record(user_id=user_id, message_id="m1"), queue_record(user_id=user_id, message_id="m2")]
        assert process_queue_records(repos, records) == []
        assert repos.is_empty_for(user_id)


class TestAgainstRealRepositories:
    """The same cascade against moto, so the fakes are checked against reality."""

    @staticmethod
    def _bundle(names: List[str]) -> Any:
        """A real repository bundle over the named tables."""
        from app.api.dependencies.repositories import build_bundle

        return build_bundle(tuple(names), name="users-delete-consumer-test")

    def test_the_cascade_removes_every_owned_row(self, dynamo_tables: Any) -> None:
        """The unstubbed cascade, over the real bundle the entrypoint declares."""
        from app.db.dynamo.build_lists import BuildList, BuildListPart
        from app.db.dynamo.catalog import Category, Part
        from app.db.dynamo.moderation import Report, Vote
        from app.db.dynamo.part_price_alerts import PartPriceAlert
        from app.entrypoints.users_delete_consumer import REPOSITORIES

        repos = self._bundle(list(REPOSITORIES))
        user_id = uuid4()
        other_user = uuid4()

        category = repos.categories.put(Category(name="Intake"))
        part = repos.parts.put(Part(name="A part", user_id=user_id, category_id=category.id))
        repos.part_price_alerts.put(PartPriceAlert(part_id=part.id, user_id=user_id, threshold_cents=100))
        build_list = repos.build_lists.put(BuildList(name="A list", user_id=user_id))
        repos.build_list_parts.put(BuildListPart(build_list_id=build_list.id, part_id=part.id, added_by=user_id))
        theirs = repos.build_lists.put(BuildList(name="Their list", user_id=other_user))
        repos.build_list_parts.put(BuildListPart(build_list_id=theirs.id, part_id=part.id, added_by=user_id))
        repos.votes.put(Vote(entity_type="part", entity_id=part.id, user_id=user_id, vote_type="upvote"))
        repos.reports.put(
            Report(entity_type="part", entity_id=part.id, user_id=user_id, reason="spam", description="x")
        )

        counts = cascade_user_delete(repos, user_id)

        assert counts["parts"] == 1
        assert counts["parts_already_purged"] == 0
        assert counts["part_price_alerts"] == 1
        assert counts["build_lists"] == 1
        assert counts["votes"] == 1
        assert counts["reports"] == 1

        remaining = repos.parts.get(str(part.id))
        assert remaining is None or getattr(remaining, "deleted", False) is True

        assert repos.build_lists.get(str(build_list.id)) is None
        assert repos.build_lists.get(str(theirs.id)) is not None, "somebody else's list survives"
        assert repos.votes.for_entities("part", [part.id]).get(part.id, []) == []
        assert repos.part_price_alerts.list_by_user(user_id) == []
        assert [usage for usage in repos.build_list_parts.scan_all() if usage.added_by == user_id] == []

    def test_the_replay_against_real_repositories_writes_nothing(self, dynamo_tables: Any) -> None:
        """A replay against real DynamoDB semantics removes nothing the second time,
        including the parts the first run tombstoned.
        """
        from app.db.dynamo.moderation import Report, Vote
        from app.entrypoints.users_delete_consumer import REPOSITORIES

        repos = self._bundle(list(REPOSITORIES))
        user_id = uuid4()
        entity_id = uuid4()
        repos.votes.put(Vote(entity_type="part", entity_id=entity_id, user_id=user_id, vote_type="upvote"))
        repos.reports.put(
            Report(entity_type="part", entity_id=entity_id, user_id=user_id, reason="spam", description="x")
        )

        assert cascade_user_delete(repos, user_id)["votes"] == 1

        second = cascade_user_delete(repos, user_id)
        assert set(second.values()) == {0}


class TestTheSynchronousHalfStayedBehind:
    """The user row and its two unique reservations stay on the request thread,
    so this consumer must not be able to reach the users table.
    """

    def test_the_bundle_cannot_reach_the_users_table(self) -> None:
        """The consumer's bundle does not declare the users repository."""
        from app.entrypoints.users_delete_consumer import REPOSITORIES

        assert "users" not in REPOSITORIES, (
            "the user row and its two reservations are removed synchronously; "
            "declaring the repository here would make a second writer possible"
        )

    def test_reaching_for_it_anyway_raises_rather_than_writing(self, dynamo_tables: Any) -> None:
        """`RepositoryNotInBundle` is the mechanism that makes the absence load bearing."""
        from app.api.dependencies.repositories import (
            RepositoryNotInBundle,
            build_bundle,
        )
        from app.entrypoints.users_delete_consumer import REPOSITORIES

        repos = build_bundle(tuple(REPOSITORIES), name="users-delete-consumer-test")
        with pytest.raises(RepositoryNotInBundle):
            _ = repos.users

    def test_the_endpoint_still_deletes_the_user_row_itself(self) -> None:
        """The other half: the tombstone is written and the row is removed inline."""
        import inspect

        from app.api.endpoints.users import _delete_user_everywhere

        source = inspect.getsource(_delete_user_everywhere)
        assert "repos.users.update" in source, "the tombstone the consumer keys on"
        assert "repos.users.delete_user" in source, "the row and its two reservations, on this thread"

    def test_the_cascade_never_names_the_users_repository(self) -> None:
        """Cheap, and it is what would catch a well meaning re-addition."""
        import inspect

        from app.consumers import user_delete

        lines: List[str] = []
        for step in (
            user_delete.cascade_user_delete,
            user_delete.purge_owned_parts,
            user_delete.purge_owned_build_lists,
            user_delete.purge_owned_moderation,
            user_delete.purge_identity,
        ):
            body = inspect.getsource(step)
            head, _, tail = body.partition('"""')
            _, _, after = tail.partition('"""')
            lines.extend((head + after).splitlines())
        code = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
        assert "repos.users" not in code


class TestEntrypoint:
    """The shared Lambda entrypoint: routing, failure reporting, and bundle scope."""

    @staticmethod
    def client(monkeypatch: pytest.MonkeyPatch, repos: Any, sqs: Any) -> Any:
        """A test client over the entrypoint with its repositories and SQS stubbed."""
        from fastapi.testclient import TestClient

        from app.entrypoints import users_delete_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "repositories", lambda: repos)
        monkeypatch.setattr(entrypoint, "sqs_client", lambda: sqs)
        return TestClient(entrypoint.app, raise_server_exceptions=False)

    def test_health_is_served(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The health route answers."""
        client = self.client(monkeypatch, build_world(str(uuid4())), FakeSqs())
        assert client.get("/health").status_code == 200

    def test_a_stream_event_is_routed_to_the_producer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stream event posted to /events enqueues rather than cascading."""
        monkeypatch.setenv("USER_DELETE_QUEUE_URL", QUEUE_URL)
        user_id = str(uuid4())
        sqs = FakeSqs()
        client = self.client(monkeypatch, build_world(user_id), sqs)

        response = client.post("/events", json={"Records": [stream_record(user_id=user_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert sqs.sent_user_ids == [user_id]

    def test_a_queue_event_is_routed_to_the_drainer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A queue event posted to /events cascades and sends nothing."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        sqs = FakeSqs()
        client = self.client(monkeypatch, repos, sqs)

        response = client.post("/events", json={"Records": [queue_record(user_id=user_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert repos.is_empty_for(user_id)
        assert sqs.sent == [], "the queue half sends nothing"

    def test_a_partial_failure_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failing message comes back as a batchItemFailures entry with a 200."""
        user_id = str(uuid4())
        repos = build_world(user_id)
        repos.votes.fail_for.add(user_id)
        client = self.client(monkeypatch, repos, FakeSqs())

        response = client.post("/events", json={"Records": [queue_record(user_id=user_id, message_id="m7")]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": [{"itemIdentifier": "m7"}]}

    def test_an_unexpected_error_is_a_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`AWS_LWA_ERROR_STATUS_CODES=500-599` turns this into a function error."""
        from fastapi.testclient import TestClient

        from app.entrypoints import users_delete_consumer as entrypoint

        def explode() -> Any:
            """Fail while building the bundle."""
            raise RuntimeError("the bundle could not be built")

        monkeypatch.setattr(entrypoint, "repositories", explode)
        client = TestClient(entrypoint.app, raise_server_exceptions=False)
        response = client.post("/events", json={"Records": [queue_record()]})
        assert response.status_code >= 500

    def test_a_malformed_body_is_a_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A body that is not JSON is a 500 rather than an ack."""
        client = self.client(monkeypatch, build_world(str(uuid4())), FakeSqs())
        response = client.post("/events", content=b"not json at all", headers={"content-type": "application/json"})
        assert response.status_code >= 500

    def test_the_service_name_distinguishes_it(self) -> None:
        """The consumer's service name is distinct from the domain's."""
        from app.entrypoints import users_delete_consumer as entrypoint

        assert entrypoint.SERVICE_NAME == f"{entrypoint.DOMAIN.service_name}-delete-consumer"
        assert entrypoint.SERVICE_NAME != entrypoint.DOMAIN.service_name

    def test_the_events_path_matches_the_adapter_contract(self) -> None:
        """The events path is /events and is actually mounted."""
        from app.entrypoints import users_delete_consumer as entrypoint

        assert entrypoint.EVENTS_PATH == "/events"
        assert entrypoint.EVENTS_PATH in {route.path for route in entrypoint.app.routes}

    def test_neither_cors_nor_the_rate_limiter_is_mounted(self) -> None:
        """The limiter would write to a table this function has no grant for."""
        from app.entrypoints import users_delete_consumer as entrypoint

        mounted = {middleware.cls.__name__ for middleware in entrypoint.app.user_middleware}
        assert "CORSMiddleware" not in mounted
        assert not any("RateLimit" in name for name in mounted)

    def test_the_bundle_is_memoised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The repository bundle is built once and reused."""
        from app.entrypoints import users_delete_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "_repos", None)
        built: List[int] = []

        def fake_build_bundle(names: Any, *, name: str = "all") -> Any:
            """Count bundle builds and return a placeholder."""
            built.append(1)
            return object()

        monkeypatch.setattr("app.api.dependencies.repositories.build_bundle", fake_build_bundle)
        assert entrypoint.repositories() is entrypoint.repositories()
        assert len(built) == 1
        monkeypatch.setattr(entrypoint, "_repos", None)

    def test_the_bundle_carries_the_eighteen_cascade_tables_and_nothing_else(self) -> None:
        """The consumer declares exactly the eighteen cascade repositories, which is the
        narrowing this split was for.
        """
        from app.entrypoints.users_delete_consumer import REPOSITORIES

        assert set(REPOSITORIES) == {
            "oauth_accounts",
            "webauthn_credentials",
            "categories",
            "part_manufacturers",
            "retailers",
            "parts",
            "part_cars",
            "part_listings",
            "part_price_history",
            "part_price_alerts",
            "build_lists",
            "build_list_parts",
            "build_list_phases",
            "build_list_labor_estimates",
            "build_logs",
            "build_log_posts",
            "votes",
            "reports",
        }
        assert len(REPOSITORIES) == len(set(REPOSITORIES)), "no duplicates"

    def test_the_users_domain_gave_up_the_twenty_cascade_tables(self) -> None:
        """The users domain no longer declares the cascade tables, asserted from its own side."""
        from app.composition.domains import DOMAINS

        assert DOMAINS["users"].repositories == ("users", "app_settings", "oauth_accounts")
        for table in ("parts", "build_lists", "build_list_parts", "votes", "reports", "webauthn_credentials"):
            assert table not in DOMAINS["users"].repositories

        assert "oauth_accounts" in DOMAINS["users"].repositories
