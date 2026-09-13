"""The product's rate limit configuration over the shared DynamoDB limiter.

Counting itself belongs to `webbpulse.ratelimit` and is pinned there. What this file
pins is what stays CarModPicker's: how a request is classified, the caps each class
carries, how a caller is identified, that each class keeps its own row under the key
the previous limiter wrote, and that a backend failure fails open.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Mapping, Optional

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from webbpulse.http import REQUEST_CONTEXT_HEADER
from webbpulse.logging import JsonFormatter
from webbpulse.ratelimit import RateLimiter, classify

from app.api.middleware.rate_limiter import (
    ADMIN_CLASS,
    AUTH_CLASS,
    DEFAULT_CLASS,
    GET_CLASS,
    WINDOW_SECONDS,
    client_identity,
    limit_classes,
)

LIMITER_LOGGER = "webbpulse.ratelimit"

COUNT_ATTRIBUTE = "requests"

TTL_ATTRIBUTE = "expires_at"


class FakeTable:
    """An in-memory table implementing the three calls the limiter makes.

    Matches DynamoDB's conditional write semantics.
    """

    def __init__(self, *, clock: Optional[list[int]] = None) -> None:
        """Start empty, with no configured failure and an optional shared clock."""
        self.items: dict[str, dict[str, Any]] = {}
        self.raises: Optional[BaseException] = None
        self.calls: list[str] = []
        self._clock = clock

    def _fail_if_configured(self) -> None:
        """Raise the configured exception, if a test set one."""
        if self.raises is not None:
            raise self.raises

    @staticmethod
    def _pk(key: Mapping[str, Any]) -> str:
        """Extract the partition key value from a key mapping."""
        return str(key["pk"])

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Return the stored item for a key, or an empty response."""
        self.calls.append("get_item")
        self._fail_if_configured()
        item = self.items.get(self._pk(kwargs["Key"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Store an item under its partition key."""
        self.calls.append("put_item")
        self._fail_if_configured()
        item = dict(kwargs["Item"])
        self.items[self._pk(item)] = item
        return {}

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Apply the limiter's conditional counter update, refusing when the condition fails."""
        self.calls.append("update_item")
        self._fail_if_configured()

        pk = self._pk(kwargs["Key"])
        values = kwargs["ExpressionAttributeValues"]
        existing = self.items.get(pk)

        if existing is not None and int(existing.get(TTL_ATTRIBUTE, 0)) <= int(values[":now"]):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "window lapsed"}},
                "UpdateItem",
            )

        if existing is None:
            existing = {"pk": pk, COUNT_ATTRIBUTE: 0, TTL_ATTRIBUTE: int(values[":ttl"])}

        existing[COUNT_ATTRIBUTE] = int(existing.get(COUNT_ATTRIBUTE, 0)) + int(values[":one"])
        existing.setdefault(TTL_ATTRIBUTE, int(values[":ttl"]))
        self.items[pk] = existing
        return {"Attributes": dict(existing)}


@pytest.fixture
def frozen_now() -> list[int]:
    """A clock the tests advance by hand, so window arithmetic is exact rather than racy."""
    return [1_000_000]


def make_limiter(
    table: FakeTable,
    *,
    limiter_class: str = DEFAULT_CLASS,
) -> RateLimiter:
    """Build a limiter over a fake table in one class's namespace."""
    limiter = RateLimiter(
        namespace=limiter_class,
        anchor="first_request",
        count_attribute=COUNT_ATTRIBUTE,
    )
    limiter._table = table
    return limiter


def row_key(identity: str, limiter_class: str = DEFAULT_CLASS) -> str:
    """The partition key the limiter writes for one caller in one class."""
    return f"{limiter_class}#{identity}"


def check(
    limiter: RateLimiter,
    identity: str,
    *,
    limit: int = 3,
    now: Optional[int] = None,
) -> Any:
    """Count one request at `limit`, against the shared window."""
    return limiter.check(identity, limit=limit, window_seconds=WINDOW_SECONDS, now=now)


def cap_for(name: str) -> int:
    """The configured cap for one class name."""
    return next(item.limit for item in limit_classes() if item.name == name)


def test_requests_under_the_limit_are_allowed(frozen_now: list[int]) -> None:
    """Every request up to and including the limit passes."""
    limiter = make_limiter(FakeTable())

    for _ in range(3):
        assert check(limiter, "1.2.3.4", now=frozen_now[0]).allowed is True


def test_separate_identities_do_not_share_a_counter(frozen_now: list[int]) -> None:
    """One caller spending its window must not limit a different caller."""
    limiter = make_limiter(FakeTable())

    for _ in range(3):
        check(limiter, "1.1.1.1", limit=2, now=frozen_now[0])

    assert check(limiter, "1.1.1.1", limit=2, now=frozen_now[0]).allowed is False
    assert check(limiter, "2.2.2.2", limit=2, now=frozen_now[0]).allowed is True


def test_request_past_the_limit_is_denied_with_a_retry_after(frozen_now: list[int]) -> None:
    """The request after the limit is rejected and reports when to retry."""
    limiter = make_limiter(FakeTable())

    assert check(limiter, "9.9.9.9", limit=2, now=frozen_now[0]).allowed is True
    assert check(limiter, "9.9.9.9", limit=2, now=frozen_now[0]).allowed is True

    decision = check(limiter, "9.9.9.9", limit=2, now=frozen_now[0])
    assert decision.allowed is False
    assert 1 <= decision.reset_after <= WINDOW_SECONDS


def test_counter_accumulates_across_limiter_instances(frozen_now: list[int]) -> None:
    """The count lives in the table, so two limiter instances share it."""
    table = FakeTable()
    first = make_limiter(table)
    second = make_limiter(table)

    check(first, "5.5.5.5", limit=2, now=frozen_now[0])
    check(second, "5.5.5.5", limit=2, now=frozen_now[0])

    assert check(first, "5.5.5.5", limit=2, now=frozen_now[0]).allowed is False


@pytest.mark.parametrize(
    "error",
    [
        ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}}, "UpdateItem"),
        ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}}, "UpdateItem"
        ),
        EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com"),
        RuntimeError("something entirely unexpected"),
    ],
    ids=["missing-table", "throttled", "unreachable", "unexpected"],
)
def test_backend_failure_allows_the_request(frozen_now: list[int], error: BaseException) -> None:
    """A limiter that cannot reach its table must allow traffic, never reject it."""
    table = FakeTable()
    table.raises = error
    limiter = make_limiter(table)

    decision = check(limiter, "1.2.3.4", now=frozen_now[0])
    assert decision.allowed is True
    assert decision.failed_open is True


def test_fail_open_is_logged_at_warning(
    frozen_now: list[int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failing open logs a warning carrying the alarm attribute and the error type."""
    table = FakeTable()
    table.raises = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}},
        "UpdateItem",
    )
    limiter = make_limiter(table)

    with caplog.at_level(logging.WARNING, logger=LIMITER_LOGGER):
        check(limiter, "1.2.3.4", now=frozen_now[0])

    records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert records, "the fail-open path must log at WARNING"
    assert records[0].rate_limit_failed_open is True


def test_fail_open_emits_a_top_level_json_boolean(
    frozen_now: list[int],
) -> None:
    """The formatted log event carries a top level JSON boolean the metric filter can match."""
    table = FakeTable()
    table.raises = EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com/")
    limiter = make_limiter(table)

    handler = logging.StreamHandler(io.StringIO())
    handler.setFormatter(JsonFormatter(service="carmodpicker", environment="test"))
    limiter_logger = logging.getLogger(LIMITER_LOGGER)
    limiter_logger.addHandler(handler)
    previous_level = limiter_logger.level
    limiter_logger.setLevel(logging.WARNING)
    try:
        check(limiter, "1.2.3.4", now=frozen_now[0])
    finally:
        limiter_logger.removeHandler(handler)
        limiter_logger.setLevel(previous_level)

    lines = [line for line in handler.stream.getvalue().splitlines() if line.strip()]
    assert lines, "the fail-open path must emit a formatted record"
    payload = json.loads(lines[0])

    assert payload["rate_limit_failed_open"] is True
    assert payload["level"] == "WARNING"
    assert payload["rate_limit_namespace"] == DEFAULT_CLASS
    assert "1.2.3.4" not in json.dumps(payload)


def test_fail_open_never_raises_into_the_request_path(frozen_now: list[int]) -> None:
    """Nothing in the limiter may propagate an exception, which is what would 5xx."""
    table = FakeTable()
    table.raises = RuntimeError("boom")
    limiter = make_limiter(table)

    check(limiter, "1.2.3.4", now=frozen_now[0])


def test_written_items_carry_a_ttl_in_the_future(frozen_now: list[int]) -> None:
    """Every counter must expire on its own, or the table grows without bound."""
    table = FakeTable()
    limiter = make_limiter(table)

    check(limiter, "1.2.3.4", now=frozen_now[0])

    item = table.items[row_key("1.2.3.4")]
    assert item[TTL_ATTRIBUTE] == frozen_now[0] + WINDOW_SECONDS


def test_ttl_is_not_extended_by_later_requests_in_the_same_window(frozen_now: list[int]) -> None:
    """The window is anchored on its first request and later ones do not slide it."""
    table = FakeTable()
    limiter = make_limiter(table)

    check(limiter, "1.2.3.4", limit=10, now=frozen_now[0])
    first_expiry = table.items[row_key("1.2.3.4")][TTL_ATTRIBUTE]

    frozen_now[0] += 30
    check(limiter, "1.2.3.4", limit=10, now=frozen_now[0])

    assert table.items[row_key("1.2.3.4")][TTL_ATTRIBUTE] == first_expiry


def test_expired_window_starts_a_fresh_count(frozen_now: list[int]) -> None:
    """Once the window lapses the caller is allowed again with a new counter."""
    table = FakeTable()
    limiter = make_limiter(table)

    check(limiter, "1.2.3.4", limit=2, now=frozen_now[0])
    check(limiter, "1.2.3.4", limit=2, now=frozen_now[0])
    assert check(limiter, "1.2.3.4", limit=2, now=frozen_now[0]).allowed is False

    frozen_now[0] += WINDOW_SECONDS + 1

    assert check(limiter, "1.2.3.4", limit=2, now=frozen_now[0]).allowed is True
    assert table.items[row_key("1.2.3.4")][COUNT_ATTRIBUTE] == 1
    assert table.items[row_key("1.2.3.4")][TTL_ATTRIBUTE] == frozen_now[0] + WINDOW_SECONDS


class TestRequestClass:
    """The pure classification every limiter lookup goes through."""

    @staticmethod
    def _class_of(method: str, path: str) -> str:
        """The name of the class this request falls into."""
        return classify(method, path, limit_classes()).name

    def test_every_get_is_the_get_class(self) -> None:
        """A GET is a GET whatever it targets, including auth and admin paths."""
        for path in ("/api/parts", "/api/auth/login", "/api/admin/users", "/api/auth/refresh"):
            assert self._class_of("GET", path) == GET_CLASS, path

    def test_method_matching_is_case_insensitive(self) -> None:
        """A lowercase method classifies the same as an uppercase one."""
        assert self._class_of("get", "/api/parts") == GET_CLASS

    def test_auth_writes_are_the_auth_class(self) -> None:
        """Non-GET writes under /api/auth are credential guesses."""
        for path in ("/api/auth/login", "/api/auth/register", "/api/auth/forgot-password"):
            assert self._class_of("POST", path) == AUTH_CLASS, path

    def test_refresh_and_logout_are_the_default_class(self) -> None:
        """These run on ordinary page loads and must not spend the auth cap."""
        for path in ("/api/auth/refresh", "/api/auth/logout"):
            assert self._class_of("POST", path) == DEFAULT_CLASS, path

    def test_a_trailing_slash_does_not_escape_the_auth_exemption(self) -> None:
        """A trailing slash must not turn a refresh into an auth-class request."""
        assert self._class_of("POST", "/api/auth/refresh/") == DEFAULT_CLASS

    def test_admin_writes_are_the_admin_class(self) -> None:
        """Non-GET writes under /api/admin get their own cap."""
        for path in ("/api/admin/users", "/api/admin/moderation/flags"):
            assert self._class_of("DELETE", path) == ADMIN_CLASS, path

    def test_a_path_merely_prefixed_by_auth_is_not_the_auth_class(self) -> None:
        """Prefix matching respects path segments rather than raw string starts."""
        assert self._class_of("POST", "/api/authors") == DEFAULT_CLASS

    def test_everything_else_is_the_default_class(self) -> None:
        """Ordinary writes fall back to the default cap."""
        for path in ("/api/parts", "/api/build-lists/7", "/api/users/me"):
            assert self._class_of("POST", path) == DEFAULT_CLASS, path


class TestPerClassCounters:
    """Each class counts in its own row, at its own cap."""

    def test_classes_do_not_share_a_counter(self, frozen_now: list[int]) -> None:
        """Spending one class's window leaves the others untouched."""
        table = FakeTable()
        get_limiter = make_limiter(table, limiter_class=GET_CLASS)
        auth_limiter = make_limiter(table, limiter_class=AUTH_CLASS)

        for _ in range(3):
            check(get_limiter, "1.2.3.4", limit=2, now=frozen_now[0])

        assert check(get_limiter, "1.2.3.4", limit=2, now=frozen_now[0]).allowed is False
        assert check(auth_limiter, "1.2.3.4", limit=2, now=frozen_now[0]).allowed is True

    def test_each_class_writes_its_own_row(self, frozen_now: list[int]) -> None:
        """The partition key carries the class, so the rows are distinct."""
        table = FakeTable()
        check(make_limiter(table, limiter_class=GET_CLASS), "1.2.3.4", now=frozen_now[0])
        check(make_limiter(table, limiter_class=ADMIN_CLASS), "1.2.3.4", now=frozen_now[0])

        assert row_key("1.2.3.4", GET_CLASS) in table.items
        assert row_key("1.2.3.4", ADMIN_CLASS) in table.items
        assert table.items[row_key("1.2.3.4", GET_CLASS)][COUNT_ATTRIBUTE] == 1

    def test_the_same_class_still_shares_one_row_across_identities(self, frozen_now: list[int]) -> None:
        """Class namespacing must not accidentally merge two callers."""
        table = FakeTable()
        limiter = make_limiter(table, limiter_class=GET_CLASS)

        check(limiter, "1.1.1.1", limit=1, now=frozen_now[0])
        check(limiter, "2.2.2.2", limit=1, now=frozen_now[0])

        assert table.items[row_key("1.1.1.1", GET_CLASS)][COUNT_ATTRIBUTE] == 1
        assert table.items[row_key("2.2.2.2", GET_CLASS)][COUNT_ATTRIBUTE] == 1


class TestConfiguredClasses:
    """The configuration wires each class to its cap, over one shared window."""

    def test_every_class_has_a_configured_limit(self) -> None:
        """Classification can never look up a class the configuration lacks."""
        names = {item.name for item in limit_classes()}
        assert names == {GET_CLASS, AUTH_CLASS, ADMIN_CLASS, DEFAULT_CLASS}

    def test_the_caps_match_the_settings_defaults(self) -> None:
        """The GET cap is well above the default, which is what the incident needed."""
        assert cap_for(GET_CLASS) == 200
        assert cap_for(AUTH_CLASS) == 10
        assert cap_for(ADMIN_CLASS) == 30
        assert cap_for(DEFAULT_CLASS) == 60

    def test_every_class_shares_the_one_minute_window(self) -> None:
        """The caps are all per minute, so one window serves them all."""
        assert {item.window_seconds for item in limit_classes()} == {60}

    def test_a_burst_of_sixty_one_gets_is_allowed(self, frozen_now: list[int]) -> None:
        """Sixty one GETs in a window is a page fanout, not abuse."""
        limiter = make_limiter(FakeTable(), limiter_class=GET_CLASS)
        cap = cap_for(GET_CLASS)

        assert all(check(limiter, "1.2.3.4", limit=cap, now=frozen_now[0]).allowed for _ in range(61))

    def test_the_get_cap_still_bites_eventually(self, frozen_now: list[int]) -> None:
        """A generous cap is still a cap."""
        limiter = make_limiter(FakeTable(), limiter_class=GET_CLASS)
        cap = cap_for(GET_CLASS)

        for _ in range(cap):
            assert check(limiter, "1.2.3.4", limit=cap, now=frozen_now[0]).allowed is True

        assert check(limiter, "1.2.3.4", limit=cap, now=frozen_now[0]).allowed is False

    def test_the_auth_cap_bites_at_eleven(self, frozen_now: list[int]) -> None:
        """Credential guesses get the tightest allowance."""
        limiter = make_limiter(FakeTable(), limiter_class=AUTH_CLASS)
        cap = cap_for(AUTH_CLASS)

        for _ in range(cap):
            assert check(limiter, "1.2.3.4", limit=cap, now=frozen_now[0]).allowed is True

        assert check(limiter, "1.2.3.4", limit=cap, now=frozen_now[0]).allowed is False


class FakeRequest:
    """Minimal stand-in carrying only what `client_identity` reads."""

    def __init__(self, headers: Optional[dict[str, str]] = None, scope: Optional[dict[str, Any]] = None) -> None:
        """Hold the headers and scope this stand-in exposes."""
        self.headers = headers or {}
        self.scope = scope or {}
        self.client = None


def test_identity_uses_the_web_adapter_request_context() -> None:
    """Payload format 2.0, which is what every HTTP API sends."""
    request = FakeRequest(headers={REQUEST_CONTEXT_HEADER: json.dumps({"http": {"sourceIp": "203.0.113.7"}})})
    assert client_identity(request) == "203.0.113.7"  # type: ignore[arg-type]


def test_identity_falls_back_to_the_aws_event_scope() -> None:
    """The zip runtime is still serving traffic during the migration."""
    request = FakeRequest(scope={"aws.event": {"requestContext": {"http": {"sourceIp": "198.51.100.9"}}}})
    assert client_identity(request) == "198.51.100.9"  # type: ignore[arg-type]


def test_identity_reads_a_nested_request_context() -> None:
    """A context nested under `requestContext` resolves the same as a flat one."""
    request = FakeRequest(
        headers={REQUEST_CONTEXT_HEADER: json.dumps({"requestContext": {"identity": {"sourceIp": "192.0.2.5"}}})}
    )
    assert client_identity(request) == "192.0.2.5"  # type: ignore[arg-type]


def test_identity_never_trusts_x_forwarded_for() -> None:
    """The caller identity comes from the request context, never a forwarded header."""
    request = FakeRequest(
        headers={
            "X-Forwarded-For": "1.2.3.4",
            REQUEST_CONTEXT_HEADER: json.dumps({"http": {"sourceIp": "203.0.113.7"}}),
        }
    )
    assert client_identity(request) == "203.0.113.7"  # type: ignore[arg-type]

    spoofed = FakeRequest(headers={"X-Forwarded-For": "1.2.3.4"})
    assert client_identity(spoofed) != "1.2.3.4"  # type: ignore[arg-type]


def test_identity_degrades_on_a_malformed_request_context() -> None:
    """A header that is not JSON must not raise out of the middleware."""
    request = FakeRequest(headers={REQUEST_CONTEXT_HEADER: "{not json"})
    assert client_identity(request) == "unknown"  # type: ignore[arg-type]
