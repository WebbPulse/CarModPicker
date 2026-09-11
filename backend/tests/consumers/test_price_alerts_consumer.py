"""Covers the part_listings stream consumer that mails price alerts: drop detection
and grouping over fakes, idempotency against redelivery, and the real send path
with only the SES transport faked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import pytest

from app.consumers.price_alerts import (
    PriceDrop,
    group_records_by_listing,
    handle,
    price_drop_from_record,
    process_records,
)

OBSERVED_AT = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)


def listing_image(
    listing_id: str,
    part_id: str,
    retailer_id: str,
    price_cents: Optional[int],
    observed_at: datetime = OBSERVED_AT,
) -> Dict[str, Any]:
    """One part_listings item in the low level wire format the stream actually holds."""
    image: Dict[str, Any] = {
        "id": {"S": listing_id},
        "part_id": {"S": part_id},
        "retailer_id": {"S": retailer_id},
        "product_url": {"S": "https://example.com/p/1"},
    }
    if price_cents is None:
        image["last_known_price_cents"] = {"NULL": True}
    else:
        image["last_known_price_cents"] = {"N": str(price_cents)}
        image["last_price_updated_at"] = {"S": observed_at.isoformat()}
    return image


def stream_record(
    listing_id: Optional[str] = None,
    part_id: Optional[str] = None,
    retailer_id: Optional[str] = None,
    price_cents: Optional[int] = 9_000,
    previous_cents: Optional[int] = None,
    sequence_number: str = "1",
    event_name: str = "MODIFY",
    observed_at: datetime = OBSERVED_AT,
) -> Dict[str, Any]:
    """One stream record as an event source mapping delivers it; previous_cents of None
    on a MODIFY means the old image carried no price, which reads as a drop.
    """
    listing_id = listing_id or str(uuid4())
    part_id = part_id or str(uuid4())
    retailer_id = retailer_id or str(uuid4())

    dynamodb: Dict[str, Any] = {
        "Keys": {"id": {"S": listing_id}},
        "SequenceNumber": sequence_number,
        "StreamViewType": "NEW_AND_OLD_IMAGES",
    }
    if event_name != "REMOVE":
        dynamodb["NewImage"] = listing_image(listing_id, part_id, retailer_id, price_cents, observed_at)
    if event_name != "INSERT":
        dynamodb["OldImage"] = listing_image(listing_id, part_id, retailer_id, previous_cents, observed_at)

    return {
        "eventID": sequence_number,
        "eventName": event_name,
        "eventSource": "aws:dynamodb",
        "sequenceNumber": sequence_number,
        "dynamodb": dynamodb,
    }


class FakeAlert:
    """Only the attributes the evaluator reads and writes."""

    def __init__(
        self,
        user_id: UUID,
        threshold_cents: int,
        last_fired_at: Optional[datetime] = None,
    ) -> None:
        """Hold the threshold and cooldown marker the evaluator reads and writes."""
        self.id = uuid4()
        self.user_id = user_id
        self.threshold_cents = threshold_cents
        self.last_fired_at = last_fired_at
        self.active = True


class FakeAlerts:
    """A part_price_alerts repository, recording its queries and updates."""

    def __init__(self, alerts: Dict[str, List[FakeAlert]]) -> None:
        """Start from a per part list of alerts."""
        self.alerts_by_part = alerts
        self.queries: List[Tuple[UUID, int]] = []
        self.updates: List[Tuple[UUID, Optional[datetime]]] = []
        self.raise_on_query: Optional[Exception] = None

    def active_at_or_below(self, part_id: UUID, price_cents: int) -> List[FakeAlert]:
        """The active alerts for a part whose threshold the price meets, or raise on demand."""
        if self.raise_on_query is not None:
            raise self.raise_on_query
        self.queries.append((part_id, price_cents))
        return [
            alert
            for alert in self.alerts_by_part.get(str(part_id), [])
            if alert.active and price_cents <= alert.threshold_cents
        ]

    def update(self, alert_id: UUID, **changes: Any) -> Any:
        """Apply and record a change to one alert."""
        self.updates.append((alert_id, changes.get("last_fired_at")))
        for alerts in self.alerts_by_part.values():
            for alert in alerts:
                if alert.id == alert_id:
                    for key, value in changes.items():
                        setattr(alert, key, value)
                    return alert
        raise KeyError(alert_id)


class FakeEntity:
    """A part or retailer the email template only needs an id and a name from."""

    def __init__(self, name: str) -> None:
        """Hold a generated id and the display name."""
        self.id = uuid4()
        self.name = name


class FakeRepo:
    """A repository the consumer only reads single items from by id."""

    def __init__(self, items: Dict[str, Any]) -> None:
        """Start from a mapping of id to item."""
        self.items = items
        self.gets: List[str] = []

    def get(self, key: Any) -> Any:
        """Return the item for a key, recording the lookup."""
        self.gets.append(str(key))
        return self.items.get(str(key))


class FakeUser:
    """A user the email path only needs an id and an address from."""

    def __init__(self, email: str) -> None:
        """Hold a generated id and the address."""
        self.id = uuid4()
        self.email = email


class FakeRepos:
    """A repository bundle covering the four tables the evaluation reads."""

    def __init__(
        self,
        part_price_alerts: FakeAlerts,
        parts: FakeRepo,
        retailers: FakeRepo,
        users: FakeRepo,
    ) -> None:
        """Wire the four per table fakes into one bundle."""
        self.part_price_alerts = part_price_alerts
        self.parts = parts
        self.retailers = retailers
        self.users = users


def build_world(
    threshold_cents: int = 12_000,
    last_fired_at: Optional[datetime] = None,
) -> Tuple[FakeRepos, str, str, FakeAlert]:
    """A part with one subscribed user, plus the ids to build records with."""
    part = FakeEntity("Brake Disc")
    retailer = FakeEntity("Example Retailer")
    user = FakeUser("subscriber@example.com")
    alert = FakeAlert(user_id=user.id, threshold_cents=threshold_cents, last_fired_at=last_fired_at)

    repos = FakeRepos(
        part_price_alerts=FakeAlerts({str(part.id): [alert]}),
        parts=FakeRepo({str(part.id): part}),
        retailers=FakeRepo({str(retailer.id): retailer}),
        users=FakeRepo({str(user.id): user}),
    )
    return repos, str(part.id), str(retailer.id), alert


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, Any, Any, int, Any]]:
    """Capture send_price_drop_alert_email calls without building a message."""
    calls: List[Tuple[str, Any, Any, int, Any]] = []

    def fake_send(to_email: str, part: Any, retailer: Any, price_cents: int, alert: Any) -> bool:
        """Record the call and report success."""
        calls.append((to_email, part, retailer, price_cents, alert))
        return True

    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", fake_send)
    return calls


class TestDropDetection:
    """Which stream records read as a price drop worth evaluating."""

    def test_a_lower_price_is_a_drop(self) -> None:
        """A lower price than the old image is a drop carrying the new price and timestamp."""
        drop = price_drop_from_record(stream_record(price_cents=9_000, previous_cents=11_000))

        assert drop is not None
        assert drop.price_cents == 9_000
        assert drop.observed_at == OBSERVED_AT

    def test_an_insert_with_a_price_is_a_drop(self) -> None:
        """A first listing is a drop, because there was no previous price to be below."""
        drop = price_drop_from_record(stream_record(price_cents=9_000, event_name="INSERT"))

        assert drop is not None
        assert drop.price_cents == 9_000

    @pytest.mark.parametrize("previous", [9_000, 8_000])
    def test_an_unchanged_or_raised_price_is_not_a_drop(self, previous: int) -> None:
        """A re-stamped or raised price is not a drop, which is the common case on a
        crawler revisiting a stable listing.
        """
        assert price_drop_from_record(stream_record(price_cents=9_000, previous_cents=previous)) is None

    def test_a_remove_is_never_a_drop(self) -> None:
        """A REMOVE is never a drop."""
        assert price_drop_from_record(stream_record(event_name="REMOVE")) is None

    def test_a_listing_with_no_price_is_not_a_drop(self) -> None:
        """A listing with no price is not a drop."""
        assert price_drop_from_record(stream_record(price_cents=None)) is None

    def test_an_unreadable_part_id_is_skipped_rather_than_failed(self) -> None:
        """An unreadable part id is skipped rather than failed, because no redelivery
        could ever fix it.
        """
        record = stream_record(price_cents=9_000, previous_cents=11_000)
        record["dynamodb"]["NewImage"]["part_id"] = {"S": "not-a-uuid"}

        assert price_drop_from_record(record) is None

    def test_a_naive_timestamp_is_read_as_utc(self) -> None:
        """The crawler path has historically sent both aware and naive values."""
        naive = datetime(2026, 9, 9, 12, 0, 0)
        record = stream_record(price_cents=9_000, previous_cents=11_000)
        record["dynamodb"]["NewImage"]["last_price_updated_at"] = {"S": naive.isoformat()}

        drop = price_drop_from_record(record)

        assert drop is not None
        assert drop.observed_at == OBSERVED_AT


class TestGrouping:
    """How several writes to one listing collapse into one evaluation."""

    def test_several_writes_to_one_listing_collapse_to_one_evaluation(self) -> None:
        """Several writes to one listing collapse to one evaluation at the lowest price,
        and every sequence number is retained for failure reporting.
        """
        listing_id, part_id, retailer_id = str(uuid4()), str(uuid4()), str(uuid4())
        records = [
            stream_record(listing_id, part_id, retailer_id, 11_000, 12_000, sequence_number="1"),
            stream_record(listing_id, part_id, retailer_id, 9_000, 11_000, sequence_number="2"),
            stream_record(listing_id, part_id, retailer_id, 9_500, 10_000, sequence_number="3"),
        ]

        grouped = group_records_by_listing(records)

        assert len(grouped) == 1
        drop, sequence_numbers = grouped[UUID(listing_id)]
        assert drop.price_cents == 9_000
        assert sequence_numbers == ["1", "2", "3"]

    def test_a_rise_inside_a_batch_contributes_nothing(self) -> None:
        """A rise alongside a drop is not grouped, so its sequence number is never retried."""
        listing_id, part_id, retailer_id = str(uuid4()), str(uuid4()), str(uuid4())
        records = [
            stream_record(listing_id, part_id, retailer_id, 9_000, 12_000, sequence_number="1"),
            stream_record(listing_id, part_id, retailer_id, 10_000, 9_000, sequence_number="2"),
        ]

        _, sequence_numbers = group_records_by_listing(records)[UUID(listing_id)]

        assert sequence_numbers == ["1"]

    def test_records_that_are_not_drops_are_absent_entirely(self) -> None:
        """A batch with no drops groups to nothing."""
        records = [
            stream_record(price_cents=9_000, previous_cents=9_000),
            stream_record(event_name="REMOVE"),
        ]

        assert group_records_by_listing(records) == {}


class TestBatchHandling:
    """What comes back from a batch, clean and partially failed."""

    def test_a_clean_batch_reports_no_failures(self, sent: List[Any]) -> None:
        """A clean batch sends and reports no failures."""
        repos, part_id, retailer_id, _ = build_world()

        result = handle(
            {"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]}, repos
        )

        assert result == {"batchItemFailures": []}
        assert len(sent) == 1

    def test_an_empty_batch_is_valid_and_reports_nothing(self, sent: List[Any]) -> None:
        """The shape the manual smoke invoke in deploy-backend.yml sends."""
        repos, _, _, _ = build_world()

        assert handle({"Records": []}, repos) == {"batchItemFailures": []}
        assert sent == []

    def test_only_the_failed_listing_is_reported(self, sent: List[Any]) -> None:
        """A partial failure reports only the failing listing's sequence numbers, so the
        records that succeeded are not re-driven.
        """
        repos, part_id, retailer_id, _ = build_world()
        bad_part_id = str(uuid4())

        original = repos.part_price_alerts.active_at_or_below

        def flaky(query_part_id: UUID, price_cents: int) -> List[FakeAlert]:
            """Raise for one part id and delegate for the rest."""
            if str(query_part_id) == bad_part_id:
                raise RuntimeError("ProvisionedThroughputExceededException")
            return original(query_part_id, price_cents)

        repos.part_price_alerts.active_at_or_below = flaky  # type: ignore[method-assign]

        records = [
            stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000, sequence_number="10"),
            stream_record(part_id=bad_part_id, retailer_id=retailer_id, previous_cents=15_000, sequence_number="20"),
            stream_record(part_id=bad_part_id, retailer_id=retailer_id, previous_cents=15_000, sequence_number="21"),
        ]

        result = handle({"Records": records}, repos)

        assert result == {"batchItemFailures": [{"itemIdentifier": "20"}, {"itemIdentifier": "21"}]}
        assert len(sent) == 1

    def test_a_listing_whose_alerts_all_fail_still_lets_the_others_run(self, sent: List[Any]) -> None:
        """Per-alert isolation lives in the evaluator and must survive the move."""
        repos, part_id, retailer_id, alert = build_world()
        exploding = FakeAlert(user_id=uuid4(), threshold_cents=99_000)
        repos.part_price_alerts.alerts_by_part[part_id].insert(0, exploding)

        result = handle(
            {"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]}, repos
        )

        assert result == {"batchItemFailures": []}
        assert len(sent) == 1
        assert sent[0][4] is alert


class TestIdempotency:
    """The stream is at least once, so a redelivered record must not mail twice."""

    def test_a_redelivered_record_does_not_send_a_second_email(self, sent: List[Any]) -> None:
        """A redelivered record sends nothing, because the cooldown marker written by the
        first send suppresses it.
        """
        repos, part_id, retailer_id, alert = build_world()
        record = stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)

        assert handle({"Records": [record]}, repos) == {"batchItemFailures": []}
        assert len(sent) == 1
        assert alert.last_fired_at == OBSERVED_AT

        assert handle({"Records": [record]}, repos) == {"batchItemFailures": []}
        assert len(sent) == 1

    def test_a_replay_of_a_whole_batch_sends_nothing_new(self, sent: List[Any]) -> None:
        """What a retry after a partial batch failure actually looks like."""
        repos, part_id, retailer_id, _ = build_world()
        records = [
            stream_record(
                part_id=part_id, retailer_id=retailer_id, price_cents=11_000, previous_cents=15_000, sequence_number="1"
            ),
            stream_record(
                part_id=part_id, retailer_id=retailer_id, price_cents=9_000, previous_cents=11_000, sequence_number="2"
            ),
        ]

        handle({"Records": records}, repos)
        assert len(sent) == 1

        handle({"Records": records}, repos)
        assert len(sent) == 1

    def test_a_failed_send_leaves_the_marker_alone_so_the_retry_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A rejected send leaves the cooldown marker unset, so a transient error does not
        become a permanently missed alert.
        """
        repos, part_id, retailer_id, alert = build_world()
        outcomes = [False, True]
        calls: List[str] = []

        def flaky_send(to_email: str, part: Any, retailer: Any, price_cents: int, sent_alert: Any) -> bool:
            """Fail the first send and succeed on the second."""
            calls.append(to_email)
            return outcomes[len(calls) - 1]

        monkeypatch.setattr("app.core.email.send_price_drop_alert_email", flaky_send)
        record = stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)

        handle({"Records": [record]}, repos)
        assert len(calls) == 1
        assert alert.last_fired_at is None
        assert repos.part_price_alerts.updates == []

        handle({"Records": [record]}, repos)
        assert len(calls) == 2
        assert alert.last_fired_at == OBSERVED_AT

    def test_a_later_drop_outside_the_cooldown_does_fire_again(self, sent: List[Any]) -> None:
        """The marker suppresses duplicates, not the next genuine drop."""
        repos, part_id, retailer_id, _ = build_world()

        handle(
            {"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]},
            repos,
        )
        assert len(sent) == 1

        later = OBSERVED_AT + timedelta(hours=25)
        handle(
            {
                "Records": [
                    stream_record(
                        part_id=part_id,
                        retailer_id=retailer_id,
                        price_cents=8_000,
                        previous_cents=9_000,
                        observed_at=later,
                    )
                ]
            },
            repos,
        )
        assert len(sent) == 2


class FakeSesClient:
    """Stands in for the sesv2 client and sends nothing, recording the whole request
    so a wrong configuration set cannot pass.
    """

    def __init__(self) -> None:
        """Start with no requests recorded."""
        self.requests: List[Dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> Dict[str, str]:
        """Record the request and return a fake message id."""
        self.requests.append(kwargs)
        return {"MessageId": f"fake-{len(self.requests)}"}


class TestAgainstTheRealSendPath:
    """The whole chain with only the SES transport faked, so the template, the signed
    unsubscribe token and the send request shape are all exercised.
    """

    @staticmethod
    def enable_ses(monkeypatch: pytest.MonkeyPatch) -> FakeSesClient:
        """Point the email module at a fake SES client and enable sending."""
        from app.core import email as email_module
        from app.core.config import settings

        client = FakeSesClient()
        monkeypatch.setattr(email_module.boto3, "client", lambda *args, **kwargs: client)
        monkeypatch.setattr(settings, "EMAIL_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "EMAIL_FROM", "alerts@example.com", raising=False)
        monkeypatch.setattr(settings, "SECRET_KEY_SETTING", "test-signing-key-not-a-real-one")
        return client

    def test_a_drop_reaches_ses_with_the_expected_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A drop reaches SES with the expected destination, sender and configuration set."""
        ses = self.enable_ses(monkeypatch)
        repos, part_id, retailer_id, alert = build_world()

        result = handle(
            {"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]},
            repos,
        )

        assert result == {"batchItemFailures": []}
        assert len(ses.requests) == 1
        request = ses.requests[0]
        assert request["Destination"]["ToAddresses"] == ["subscriber@example.com"]
        assert request["FromEmailAddress"] == "alerts@example.com"
        assert request["ConfigurationSetName"] == "carmodpicker-transactional"
        assert alert.last_fired_at == OBSERVED_AT

    def test_the_body_carries_a_working_unsubscribe_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The unsubscribe link carries a token signed with the app secret, which is the
        secret dependency this consumer would otherwise break on silently.
        """
        ses = self.enable_ses(monkeypatch)
        repos, part_id, retailer_id, alert = build_world()

        handle(
            {"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]},
            repos,
        )

        html = ses.requests[0]["Content"]["Simple"]["Body"]["Html"]["Data"]
        assert "unsubscribe?token=" in html

        token = html.split("unsubscribe?token=")[1].split('"')[0].split("&")[0]
        from app.api.dependencies.auth import decode_access_token

        claims = decode_access_token(token)
        assert claims is not None
        assert claims.get("purpose") == "price_alert_unsubscribe"
        assert claims.get("sub") == str(alert.id)

    def test_a_redelivery_sends_nothing_to_ses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The idempotency claim, restated where the side effect is real."""
        ses = self.enable_ses(monkeypatch)
        repos, part_id, retailer_id, _ = build_world()
        record = stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)

        handle({"Records": [record]}, repos)
        handle({"Records": [record]}, repos)

        assert len(ses.requests) == 1

    def test_an_unchanged_price_never_reaches_ses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The crawler revisit case, proven at the transport rather than in a unit."""
        ses = self.enable_ses(monkeypatch)
        repos, part_id, retailer_id, _ = build_world()

        result = handle(
            {
                "Records": [
                    stream_record(part_id=part_id, retailer_id=retailer_id, price_cents=9_000, previous_cents=9_000)
                ]
            },
            repos,
        )

        assert result == {"batchItemFailures": []}
        assert ses.requests == []
        assert repos.part_price_alerts.queries == []


class TestEntrypoint:
    """The Lambda entrypoint, whose contract is HTTP because the Web Adapter POSTs the
    raw event and uses /health as the readiness check.
    """

    @staticmethod
    def client(monkeypatch: pytest.MonkeyPatch, repos: FakeRepos) -> Any:
        """A test client over the entrypoint with its repositories stubbed."""
        from fastapi.testclient import TestClient

        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "repositories", lambda: repos)
        return TestClient(entrypoint.app, raise_server_exceptions=False)

    def test_health_answers_the_readiness_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The readiness route answers."""
        repos, _, _, _ = build_world()

        assert self.client(monkeypatch, repos).get("/health").status_code == 200

    def test_events_sends_and_reports_no_failures(self, monkeypatch: pytest.MonkeyPatch, sent: List[Any]) -> None:
        """A drop posted to /events sends and reports no failures."""
        repos, part_id, retailer_id, _ = build_world()
        client = self.client(monkeypatch, repos)

        response = client.post(
            "/events",
            json={"Records": [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]},
        )

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert len(sent) == 1

    def test_events_returns_batch_item_failures_for_the_failed_listing_only(
        self, monkeypatch: pytest.MonkeyPatch, sent: List[Any]
    ) -> None:
        """A failing listing comes back as a batchItemFailures entry with a 200."""
        repos, part_id, retailer_id, _ = build_world()
        repos.part_price_alerts.raise_on_query = RuntimeError("ProvisionedThroughputExceededException")
        client = self.client(monkeypatch, repos)

        response = client.post(
            "/events",
            json={
                "Records": [
                    stream_record(
                        part_id=part_id,
                        retailer_id=retailer_id,
                        previous_cents=15_000,
                        sequence_number="42",
                    )
                ]
            },
        )

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": [{"itemIdentifier": "42"}]}
        assert sent == []

    def test_an_unexpected_exception_becomes_a_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unexpected exception is a 5xx, because acking the batch would drop it with
        the subscribers on it never hearing about the drop.
        """
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        repos, _, _, _ = build_world()
        client = self.client(monkeypatch, repos)
        monkeypatch.setattr(
            entrypoint,
            "repositories",
            lambda: (_ for _ in ()).throw(RuntimeError("bundle is unreachable")),
        )

        assert client.post("/events", json={"Records": [stream_record()]}).status_code >= 500

    def test_a_malformed_body_becomes_a_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Not JSON means the adapter contract broke; fail loudly, do not ack."""
        repos, _, _, _ = build_world()
        client = self.client(monkeypatch, repos)

        response = client.post(
            "/events",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )

        assert response.status_code >= 500

    def test_service_name_is_distinct_from_the_http_admin_function(self) -> None:
        """The consumer's service name is distinct from the domain's."""
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        assert entrypoint.SERVICE_NAME == f"{entrypoint.DOMAIN.service_name}-price-alerts-consumer"
        assert entrypoint.SERVICE_NAME != entrypoint.DOMAIN.service_name

    def test_the_events_path_matches_the_adapter_default(self) -> None:
        """The events path matches the adapter pass through path, since a drift would ack
        every record on a 404.
        """
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        assert entrypoint.EVENTS_PATH == "/events"
        assert entrypoint.EVENTS_PATH in {route.path for route in entrypoint.app.routes}

    def test_the_bundle_is_memoised_across_invokes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One bundle per execution environment, not one per invoke."""
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "_repos", None)
        built: List[int] = []

        def fake_bundle_for(domains: Any) -> Any:
            """Count bundle builds and return a prebuilt world."""
            built.append(1)
            return build_world()[0]

        monkeypatch.setattr("app.composition.wiring.bundle_for", fake_bundle_for)

        first = entrypoint.repositories()
        second = entrypoint.repositories()

        assert first is second
        assert len(built) == 1

    def test_it_runs_on_the_admin_domain_and_needs_no_bundle_widening(self) -> None:
        """Every repository the evaluation reaches is already in the admin domain's set,
        so this consumer widens nothing.
        """
        from app.composition.domains import DOMAINS
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        assert entrypoint.DOMAIN is DOMAINS["admin"]
        assert {"part_price_alerts", "parts", "retailers", "users"} <= set(DOMAINS["admin"].repositories)

    def test_the_admin_http_function_is_unchanged_by_this_row(self) -> None:
        """The admin domain descriptor gains no SES grant; that lives on the consumer."""
        from app.composition.domains import DOMAINS

        assert DOMAINS["admin"].requires_secrets == ("SECRET_KEY",)

    def test_neither_cors_nor_the_rate_limiter_is_mounted(self) -> None:
        """Neither CORS nor the rate limiter is mounted, since the limiter has no grant
        here and would fail open on every invoke.
        """
        from app.entrypoints import admin_price_alerts_consumer as entrypoint

        mounted = {middleware.cls.__name__ for middleware in entrypoint.app.user_middleware}

        assert "CORSMiddleware" not in mounted
        assert not any("RateLimit" in name for name in mounted)


def test_process_records_is_the_handler_without_the_envelope(sent: List[Any]) -> None:
    """process_records is the handler without the batchItemFailures envelope, so the
    envelope cannot quietly change what is evaluated.
    """
    repos, part_id, retailer_id, _ = build_world()
    records = [stream_record(part_id=part_id, retailer_id=retailer_id, previous_cents=15_000)]

    assert process_records(repos, records) == []
    assert len(sent) == 1


def test_price_drop_equality_is_by_value() -> None:
    """`PriceDrop` is compared in the grouping tests, so this has to hold."""
    part_id, retailer_id = uuid4(), uuid4()

    assert PriceDrop(part_id, retailer_id, 9_000, OBSERVED_AT) == PriceDrop(part_id, retailer_id, 9_000, OBSERVED_AT)
    assert PriceDrop(part_id, retailer_id, 9_000, OBSERVED_AT) != PriceDrop(part_id, retailer_id, 8_000, OBSERVED_AT)
    assert PriceDrop(part_id, retailer_id, 9_000, OBSERVED_AT) != "not a drop"
