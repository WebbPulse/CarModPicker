"""Covers the votes stream consumer that recomputes net_votes: grouping, recompute
and failure reporting over fakes, then the same handler against real repositories.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

import pytest

from app.consumers.votes import (
    group_records_by_part,
    handle,
    part_id_from_record,
    process_records,
    recompute_net_votes,
)
from app.db.dynamo.catalog import Category, CategoryRepository, Part, PartRepository
from app.db.dynamo.moderation import Vote, VoteRepository
from app.db.dynamo.repository import ItemNotFound


def stream_record(
    entity_type: str = "part",
    entity_id: str | None = None,
    sequence_number: str = "1",
    event_name: str = "INSERT",
    image_key: str = "NewImage",
) -> Dict[str, Any]:
    """One votes stream record in the low level wire shape an event source mapping delivers."""
    image = {
        "id": {"S": str(uuid4())},
        "entity_type": {"S": entity_type},
        "entity_id": {"S": entity_id or str(uuid4())},
        "vote_type": {"S": "upvote"},
    }
    return {
        "eventID": sequence_number,
        "eventName": event_name,
        "eventSource": "aws:dynamodb",
        "sequenceNumber": sequence_number,
        "dynamodb": {
            "Keys": {"id": image["id"]},
            image_key: image,
            "SequenceNumber": sequence_number,
            "StreamViewType": "NEW_AND_OLD_IMAGES",
        },
    }


class FakeParts:
    """A parts repository recording its reads and writes."""

    def __init__(self, parts: Dict[str, Any]) -> None:
        """Start from a mapping of part id to part."""
        self.parts = parts
        self.updates: List[Tuple[str, int]] = []
        self.gets: List[str] = []
        self.raise_on_update: Exception | None = None

    def get(self, part_id: str) -> Any:
        """Return the part for an id, recording the lookup."""
        self.gets.append(part_id)
        return self.parts.get(part_id)

    def update(self, part_id: str, **changes: Any) -> Any:
        """Apply and record a net_votes write, or raise on demand."""
        if self.raise_on_update is not None:
            raise self.raise_on_update
        self.updates.append((part_id, changes["net_votes"]))
        part = self.parts[part_id]
        part.net_votes = changes["net_votes"]
        return part


class FakeVotes:
    """A votes repository returning a fixed upvote and downvote count per entity."""

    def __init__(self, counts: Dict[str, Tuple[int, int]]) -> None:
        """Start from a mapping of entity id to counts."""
        self.counts_by_entity = counts
        self.calls: List[Tuple[str, UUID]] = []

    def counts(self, entity_type: str, entity_id: UUID) -> Tuple[int, int]:
        """Return the counts for an entity, recording the call."""
        self.calls.append((entity_type, entity_id))
        return self.counts_by_entity.get(str(entity_id), (0, 0))


class FakeRepos:
    """A repository bundle carrying just the parts and votes fakes."""

    def __init__(self, parts: FakeParts, votes: FakeVotes) -> None:
        """Wire the two fakes into one bundle."""
        self.parts = parts
        self.votes = votes


class FakePart:
    """Only the two attributes the consumer reads."""

    def __init__(self, net_votes: int = 0, deleted: bool = False) -> None:
        """Hold the vote total and the tombstone flag."""
        self.net_votes = net_votes
        self.deleted = deleted


class TestRecordParsing:
    """Which votes stream records name a part that needs recounting."""

    def test_part_vote_yields_its_entity_id(self) -> None:
        """A part vote yields the part id to recount."""
        part_id = uuid4()
        assert part_id_from_record(stream_record(entity_id=str(part_id))) == part_id

    @pytest.mark.parametrize("entity_type", ["build_list", "car_generation"])
    def test_other_entity_types_are_dropped(self, entity_type: str) -> None:
        """A build list vote must cost no DynamoDB call at all."""
        assert part_id_from_record(stream_record(entity_type=entity_type)) is None

    def test_remove_reads_the_old_image(self) -> None:
        """A REMOVE carries only `OldImage`, and the part still needs recounting."""
        part_id = uuid4()
        record = stream_record(entity_id=str(part_id), event_name="REMOVE", image_key="OldImage")
        assert part_id_from_record(record) == part_id

    def test_record_with_no_image_is_dropped(self) -> None:
        """A record carrying no image is dropped."""
        assert part_id_from_record({"sequenceNumber": "1", "dynamodb": {}}) is None

    def test_record_with_no_dynamodb_key_is_dropped(self) -> None:
        """A record with no dynamodb key is dropped."""
        assert part_id_from_record({"sequenceNumber": "1"}) is None

    def test_malformed_entity_id_is_dropped_not_failed(self) -> None:
        """Not retryable, so it must not reach the dead letter queue."""
        record = stream_record(entity_id="not-a-uuid")
        assert part_id_from_record(record) is None

    def test_grouping_collapses_records_per_part_and_keeps_every_sequence(self) -> None:
        """Grouping collapses records per part while keeping every sequence number."""
        part_a, part_b = str(uuid4()), str(uuid4())
        records = [
            stream_record(entity_id=part_a, sequence_number="1"),
            stream_record(entity_id=part_b, sequence_number="2"),
            stream_record(entity_id=part_a, sequence_number="3"),
            stream_record(entity_type="build_list", sequence_number="4"),
        ]
        grouped = group_records_by_part(records)

        assert set(grouped) == {UUID(part_a), UUID(part_b)}
        assert grouped[UUID(part_a)] == ["1", "3"]
        assert grouped[UUID(part_b)] == ["2"]


class TestRecompute:
    """What recompute writes, and when it declines to write at all."""

    def test_writes_the_difference_of_the_counts(self) -> None:
        """The written total is upvotes minus downvotes."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (7, 2)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) == 5
        assert parts.updates == [(str(part_id), 5)]

    def test_missing_part_writes_nothing(self) -> None:
        """A vote can outlive its part; that is not an error."""
        part_id = uuid4()
        parts = FakeParts({})
        votes = FakeVotes({})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None
        assert parts.updates == []
        assert votes.calls == []

    def test_tombstoned_part_is_skipped(self) -> None:
        """Row 23: a part being purged must not have an attribute written back."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0, deleted=True)})
        votes = FakeVotes({str(part_id): (4, 1)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None
        assert parts.updates == []
        assert votes.calls == []

    def test_unchanged_aggregate_skips_the_write(self) -> None:
        """An unchanged total skips the write entirely."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=3)})
        votes = FakeVotes({str(part_id): (3, 0)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) == 3
        assert parts.updates == []

    def test_part_deleted_between_the_read_and_the_write(self) -> None:
        """A part deleted between the read and the write is not an error."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        parts.raise_on_update = ItemNotFound("carmodpicker-parts", {"id": str(part_id)})
        votes = FakeVotes({str(part_id): (2, 0)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None


class TestIdempotency:
    """The stream is at least once, so replays must converge rather than accumulate."""

    def test_replaying_the_same_record_converges(self) -> None:
        """At-least-once delivery: the same batch twice must not double the count."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (5, 1)})
        repos = FakeRepos(parts, votes)
        event = {"Records": [stream_record(entity_id=str(part_id))]}

        assert handle(event, repos) == {"batchItemFailures": []}
        assert handle(event, repos) == {"batchItemFailures": []}
        assert handle(event, repos) == {"batchItemFailures": []}

        assert parts.parts[str(part_id)].net_votes == 4
        assert parts.updates == [(str(part_id), 4)]

    def test_many_records_on_one_part_are_one_recompute(self) -> None:
        """Fifty records on one part are one query and one write."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (50, 0)})
        records = [stream_record(entity_id=str(part_id), sequence_number=str(i)) for i in range(50)]

        handle({"Records": records}, FakeRepos(parts, votes))

        assert len(votes.calls) == 1
        assert parts.updates == [(str(part_id), 50)]


class TestBatchHandling:
    """What comes back from a batch, clean and partially failed."""

    def test_mixed_batch_recomputes_only_the_parts(self) -> None:
        """A batch mixing entity types recomputes only the parts."""
        part_a, part_b = str(uuid4()), str(uuid4())
        parts = FakeParts({part_a: FakePart(), part_b: FakePart()})
        votes = FakeVotes({part_a: (3, 1), part_b: (0, 2)})
        records = [
            stream_record(entity_id=part_a, sequence_number="1"),
            stream_record(entity_type="build_list", sequence_number="2"),
            stream_record(entity_id=part_b, sequence_number="3", event_name="REMOVE", image_key="OldImage"),
            stream_record(entity_type="car_generation", sequence_number="4"),
            stream_record(entity_id=part_a, sequence_number="5", event_name="MODIFY"),
        ]

        result = handle({"Records": records}, FakeRepos(parts, votes))

        assert result == {"batchItemFailures": []}
        assert sorted(parts.updates) == sorted([(part_a, 2), (part_b, -2)])

    def test_empty_event_returns_an_empty_failure_list(self) -> None:
        """Explicitly `{"batchItemFailures": []}`, not an empty response."""
        assert handle({}, FakeRepos(FakeParts({}), FakeVotes({}))) == {"batchItemFailures": []}

    def test_one_failing_part_reports_only_its_own_records(self) -> None:
        """A failing part reports only its own sequence numbers."""
        part_ok, part_bad = str(uuid4()), str(uuid4())

        class ExplodingVotes(FakeVotes):
            """A votes repository that raises for one part id."""

            def counts(self, entity_type: str, entity_id: UUID) -> Tuple[int, int]:
                """Raise for the failing part and delegate for the rest."""
                if str(entity_id) == part_bad:
                    raise RuntimeError("ProvisionedThroughputExceededException")
                return super().counts(entity_type, entity_id)

        parts = FakeParts({part_ok: FakePart(), part_bad: FakePart()})
        votes = ExplodingVotes({part_ok: (2, 0)})
        records = [
            stream_record(entity_id=part_ok, sequence_number="1"),
            stream_record(entity_id=part_bad, sequence_number="2"),
            stream_record(entity_id=part_bad, sequence_number="3"),
        ]

        result = handle({"Records": records}, FakeRepos(parts, votes))

        assert result == {"batchItemFailures": [{"itemIdentifier": "2"}, {"itemIdentifier": "3"}]}
        assert parts.updates == [(part_ok, 2)]

    def test_process_records_returns_sequence_numbers(self) -> None:
        """process_records returns the failing sequence numbers without the envelope."""
        part_id = str(uuid4())
        parts = FakeParts({part_id: FakePart()})
        parts.raise_on_update = RuntimeError("throttled")
        votes = FakeVotes({part_id: (1, 0)})

        failures = process_records(
            FakeRepos(parts, votes),
            [stream_record(entity_id=part_id, sequence_number="99")],
        )

        assert failures == ["99"]


class TestAgainstRealRepositories:
    """The same handler, moto, and the repositories the Lambda actually builds."""

    def test_recompute_writes_the_real_part(self, dynamo_tables: Any) -> None:
        """The handler writes the real part through the real repositories, and a replay
        leaves the total unchanged.
        """
        category = next(iter(CategoryRepository().list_all()), None)
        if category is None:
            category = CategoryRepository().create(
                Category(
                    name="consumer_test_category",
                    display_name="Consumer Test Category",
                    description="For the votes stream consumer test",
                    is_active=True,
                    sort_order=1,
                )
            )
        user_id = uuid4()
        part = PartRepository().create(
            Part(name=f"consumer-part-{uuid4()}", description="x", user_id=user_id, category_id=category.id)
        )

        votes = VoteRepository()
        for _ in range(3):
            votes.create(Vote(user_id=uuid4(), entity_type="part", entity_id=part.id, vote_type="upvote"))
        votes.create(Vote(user_id=uuid4(), entity_type="part", entity_id=part.id, vote_type="downvote"))

        class RealRepos:
            """A bundle over the real parts and votes repositories."""

            parts = PartRepository()
            votes = VoteRepository()

        result = handle({"Records": [stream_record(entity_id=str(part.id))]}, RealRepos())

        assert result == {"batchItemFailures": []}
        assert PartRepository().get(part.id).net_votes == 2

        handle({"Records": [stream_record(entity_id=str(part.id))]}, RealRepos())
        assert PartRepository().get(part.id).net_votes == 2


class TestEntrypoint:
    """The Lambda entrypoint, whose contract is HTTP because the Web Adapter POSTs the
    raw event and uses /health as the readiness check.
    """

    @staticmethod
    def client(
        monkeypatch: pytest.MonkeyPatch,
        parts: "FakeParts",
        votes: "FakeVotes",
    ) -> Any:
        """A test client over the entrypoint with its repositories stubbed."""
        from fastapi.testclient import TestClient

        from app.entrypoints import catalog_votes_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "repositories", lambda: FakeRepos(parts, votes))
        return TestClient(entrypoint.app, raise_server_exceptions=False)

    def test_health_answers_the_readiness_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The path the Dockerfile polls before the adapter forwards anything."""
        client = self.client(monkeypatch, FakeParts({}), FakeVotes({}))

        response = client.get("/health")

        assert response.status_code == 200

    def test_events_recomputes_and_reports_no_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A vote posted to /events recomputes and reports no failures."""
        part_id = str(uuid4())
        parts = FakeParts({part_id: FakePart()})
        votes = FakeVotes({part_id: (2, 0)})
        client = self.client(monkeypatch, parts, votes)

        response = client.post("/events", json={"Records": [stream_record(entity_id=part_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert parts.updates == [(part_id, 2)]

    def test_events_collapses_a_mixed_batch_into_one_recompute_per_part(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fifty records over two parts is two queries, not fifty."""
        first, second = str(uuid4()), str(uuid4())
        parts = FakeParts({first: FakePart(), second: FakePart()})
        votes = FakeVotes({first: (5, 2), second: (1, 4)})
        client = self.client(monkeypatch, parts, votes)

        records = [
            stream_record(entity_id=first if index % 2 == 0 else second, sequence_number=str(index))
            for index in range(50)
        ]

        response = client.post("/events", json={"Records": records})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert sorted(parts.updates) == sorted([(first, 3), (second, -3)])
        assert sorted(parts.gets) == sorted([first, second])

    def test_events_skips_tombstoned_parts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A tombstoned part is skipped rather than written back."""
        part_id = str(uuid4())
        parts = FakeParts({part_id: FakePart(deleted=True)})
        votes = FakeVotes({part_id: (7, 0)})
        client = self.client(monkeypatch, parts, votes)

        response = client.post("/events", json={"Records": [stream_record(entity_id=part_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert parts.updates == []

    def test_events_returns_batch_item_failures_for_the_failed_part_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A partial failure is a 200 carrying only the failing sequence numbers, so the
        records that succeeded are not re-driven.
        """
        good, bad = str(uuid4()), str(uuid4())

        class ExplodingVotes(FakeVotes):
            """A votes repository that raises for one part id."""

            def counts(self, entity_type: str, entity_id: UUID) -> Tuple[int, int]:
                """Raise for the failing part and delegate for the rest."""
                if str(entity_id) == bad:
                    raise RuntimeError("ProvisionedThroughputExceededException")
                return super().counts(entity_type, entity_id)

        parts = FakeParts({good: FakePart(), bad: FakePart()})
        client = self.client(monkeypatch, parts, ExplodingVotes({good: (1, 0)}))

        records = [
            stream_record(entity_id=good, sequence_number="10"),
            stream_record(entity_id=bad, sequence_number="20"),
            stream_record(entity_id=bad, sequence_number="21"),
        ]

        response = client.post("/events", json={"Records": records})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": [{"itemIdentifier": "20"}, {"itemIdentifier": "21"}]}
        assert parts.updates == [(good, 1)]

    def test_an_unexpected_exception_becomes_a_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unexpected exception is a 5xx, because acking the batch would drop it
        instead of letting the mapping bisect and retry.
        """
        from app.entrypoints import catalog_votes_consumer as entrypoint

        client = self.client(monkeypatch, FakeParts({}), FakeVotes({}))
        monkeypatch.setattr(
            entrypoint,
            "repositories",
            lambda: (_ for _ in ()).throw(RuntimeError("bundle is unreachable")),
        )

        response = client.post("/events", json={"Records": [stream_record()]})

        assert response.status_code >= 500

    def test_a_malformed_body_becomes_a_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Not JSON means the adapter contract broke; fail loudly, do not ack."""
        client = self.client(monkeypatch, FakeParts({}), FakeVotes({}))

        response = client.post(
            "/events",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )

        assert response.status_code >= 500

    def test_service_name_is_distinct_from_the_http_catalog_function(self) -> None:
        """The consumer's service name is distinct from the domain's."""
        from app.entrypoints import catalog_votes_consumer as entrypoint

        assert entrypoint.SERVICE_NAME == f"{entrypoint.DOMAIN.service_name}-votes-consumer"
        assert entrypoint.SERVICE_NAME != entrypoint.DOMAIN.service_name

    def test_the_events_path_matches_the_adapter_default(self) -> None:
        """The events path matches the adapter pass through path, since a drift would ack
        every record on a 404.
        """
        from app.entrypoints import catalog_votes_consumer as entrypoint

        assert entrypoint.EVENTS_PATH == "/events"
        assert entrypoint.EVENTS_PATH in {route.path for route in entrypoint.app.routes}

    def test_the_bundle_is_memoised_across_invokes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One bundle per execution environment, not one per invoke."""
        from app.entrypoints import catalog_votes_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "_repos", None)
        built: List[int] = []

        def fake_bundle_for(domains: Any) -> Any:
            """Count bundle builds and return a placeholder bundle."""
            built.append(1)
            return FakeRepos(FakeParts({}), FakeVotes({}))

        monkeypatch.setattr("app.composition.wiring.bundle_for", fake_bundle_for)

        first = entrypoint.repositories()
        second = entrypoint.repositories()

        assert first is second
        assert len(built) == 1

    def test_neither_cors_nor_the_rate_limiter_is_mounted(self) -> None:
        """Neither CORS nor the rate limiter is mounted, since the limiter has no grant
        here and would fail open on every invoke.
        """
        from app.entrypoints import catalog_votes_consumer as entrypoint

        mounted = {middleware.cls.__name__ for middleware in entrypoint.app.user_middleware}

        assert "CORSMiddleware" not in mounted
        assert not any("RateLimit" in name for name in mounted)
