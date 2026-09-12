"""The shared, DynamoDB backed rate limiter: the only limiter this API runs.

Counting in the table rather than in a process is what makes the limit real on
Lambda, where every execution environment would otherwise hold its own count.
Every backend failure fails open, so an outage costs availability nothing.

Requests are split into classes so a page's read fanout cannot spend the
allowance that guards credential endpoints. Each class counts in its own row.
"""

import hashlib
import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Mapping, Optional, Protocol

from botocore.exceptions import ClientError
from fastapi import Request

from ...core.config import settings

logger = logging.getLogger(__name__)

REQUEST_CONTEXT_HEADER = "x-amzn-request-context"

TTL_ATTRIBUTE = "expires_at"

COUNT_ATTRIBUTE = "requests"

CLIENT_KEY_DIGEST_CHARS = 16

GET_CLASS = "get"

AUTH_CLASS = "auth"

ADMIN_CLASS = "admin"

DEFAULT_CLASS = "default"

AUTH_PATH_PREFIX = "/api/auth"

ADMIN_PATH_PREFIX = "/api/admin"

AUTH_CLASS_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        f"{AUTH_PATH_PREFIX}/refresh",
        f"{AUTH_PATH_PREFIX}/logout",
    }
)

current_route_var: ContextVar[Optional[str]] = ContextVar("rate_limit_route", default=None)


@contextmanager
def request_route(route: Optional[str]) -> Iterator[None]:
    """Scope `route` to the current request for the duration of the limiter call."""
    token = current_route_var.set(route)
    try:
        yield
    finally:
        current_route_var.reset(token)


class TableClient(Protocol):
    """The slice of a boto3 DynamoDB Table this module uses.

    Declared as a Protocol so tests can pass a fake in place of a real table without
    moto or network access, which is what keeps the fail-open paths cheap to pin.
    """

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Read one item from the table."""
        ...

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Apply an update expression to one item."""
        ...

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Write one item to the table."""
        ...


def _error_code(error: ClientError) -> str:
    """The AWS error code, read defensively so a malformed response yields ""."""
    return str(error.response.get("Error", {}).get("Code", ""))


def _under_prefix(path: str, prefix: str) -> bool:
    """True when `path` is `prefix` itself or sits beneath it."""
    return path == prefix or path.startswith(f"{prefix}/")


def request_class(method: str, path: str) -> str:
    """The rate limit class one request belongs to.

    GETs are their own class because a single page view fans out into many of
    them. Non-GET writes under `/api/auth` are credential guesses and get the
    tightest cap, except `refresh` and `logout`, which run on ordinary page
    loads. Non-GET writes under `/api/admin` get their own cap, and everything
    else falls back to the default.
    """
    if method.upper() == "GET":
        return GET_CLASS

    normalised = path.rstrip("/") or path

    if _under_prefix(normalised, AUTH_PATH_PREFIX) and normalised not in AUTH_CLASS_EXEMPT_PATHS:
        return AUTH_CLASS

    if _under_prefix(normalised, ADMIN_PATH_PREFIX):
        return ADMIN_CLASS

    return DEFAULT_CLASS


def now() -> int:
    """Return the current Unix time in whole seconds."""
    return int(time.time())


def _source_ip_from_context(context: Any) -> str:
    """Pull the source IP out of one API Gateway request context mapping."""
    if not isinstance(context, dict):
        return ""

    http_section = context.get("http")
    if isinstance(http_section, dict):
        source_ip = http_section.get("sourceIp")
        if isinstance(source_ip, str) and source_ip:
            return source_ip

    identity = context.get("identity")
    if isinstance(identity, dict):
        source_ip = identity.get("sourceIp")
        if isinstance(source_ip, str) and source_ip:
            return source_ip

    return ""


def client_identity(request: Request) -> str:
    """The caller's IP as API Gateway observed it.

    Three sources are tried in order: the `x-amzn-request-context` header the Web
    Adapter forwards, the `aws.event` scope key an event-driven adapter populates,
    and finally the connection's own peer address.
    """
    raw = request.headers.get(REQUEST_CONTEXT_HEADER)
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Could not parse %s as JSON; ignoring it.", REQUEST_CONTEXT_HEADER)
            parsed = None

        source_ip = _source_ip_from_context(parsed)
        if not source_ip and isinstance(parsed, dict):
            source_ip = _source_ip_from_context(parsed.get("requestContext"))
        if source_ip:
            return source_ip

    event = request.scope.get("aws.event")
    if isinstance(event, dict):
        source_ip = _source_ip_from_context(event.get("requestContext"))
        if source_ip:
            return source_ip

    return request.client.host if request.client else "unknown"


class SharedRateLimiter:
    """Fixed window request counter over the rate limits table.

    The window is anchored on the caller's first request rather than on the clock.
    Each limiter owns one class, and its rows are namespaced by that class so two
    classes never share a counter.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        request_class: str = DEFAULT_CLASS,
        table_client: Optional[TableClient] = None,
    ) -> None:
        """Configure the window size, request cap, class and optional table client."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_class = request_class
        self._table_client = table_client

    @property
    def table(self) -> TableClient:
        """The DynamoDB table backing the counter, resolved on first use."""
        if self._table_client is not None:
            return self._table_client

        from app.db.dynamo import client as dynamo_client
        from app.db.dynamo.tables import RATE_LIMITS

        if settings.RATE_LIMITS_TABLE:
            return dynamo_client.get_resource().Table(settings.RATE_LIMITS_TABLE)
        return dynamo_client.get_table(RATE_LIMITS)

    def key(self, identity: str) -> dict[str, str]:
        """Build the primary key for this class's counter row for a caller."""
        return {"pk": f"RATE#{self.request_class}#{identity}"}

    @staticmethod
    def client_key(identity: str) -> str:
        """A stable, non-reversible handle for one caller, safe to log."""
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:CLIENT_KEY_DIGEST_CHARS]

    def _failed_open(
        self,
        operation: str,
        error: BaseException,
        identity: Optional[str] = None,
    ) -> None:
        """Record a limiter failure that let a request through."""
        logger.warning(
            "Shared rate limit check failed; allowing the request. operation=%s error_type=%s error_message=%s",
            operation,
            type(error).__name__,
            error,
            extra={
                "rate_limit_failed_open": True,
                "rate_limit_operation": operation,
                "exception_type": type(error).__name__,
                "exception_message": str(error),
                "client_key": self.client_key(identity) if identity is not None else None,
                "rate_limit_class": self.request_class,
                "route": current_route_var.get(),
            },
        )

    def _current(self, identity: str) -> Optional[Mapping[str, Any]]:
        """Return the caller's counter row, or None when absent or expired."""
        item = self.table.get_item(Key=self.key(identity)).get("Item")
        if not item or int(item.get(TTL_ATTRIBUTE, 0)) <= now():
            return None
        return item

    def is_limited(self, identity: str) -> bool:
        """True when `identity` has already spent its window. Never raises."""
        try:
            item = self._current(identity)
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("is_limited", error, identity)
            return False
        if item is None:
            return False
        return int(item.get(COUNT_ATTRIBUTE, 0)) >= self.max_requests

    def retry_after(self, identity: str) -> Optional[int]:
        """Seconds until `identity` may retry, or None when it is not limited."""
        try:
            item = self._current(identity)
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("retry_after", error, identity)
            return None
        if item is None or int(item.get(COUNT_ATTRIBUTE, 0)) < self.max_requests:
            return None
        return max(1, int(item[TTL_ATTRIBUTE]) - now())

    def record_request(self, identity: str) -> int:
        """Count one request and return the running total for the window.

        Returns 0 when the counter could not be written, which is below every threshold
        and so allows the request. That is the fail-open path.
        """
        current = now()
        try:
            response = self.table.update_item(
                Key=self.key(identity),
                UpdateExpression=f"ADD {COUNT_ATTRIBUTE} :one SET #ttl = if_not_exists(#ttl, :ttl)",
                ConditionExpression="attribute_not_exists(#ttl) OR #ttl > :now",
                ExpressionAttributeNames={"#ttl": TTL_ATTRIBUTE},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":ttl": current + self.window_seconds,
                    ":now": current,
                },
                ReturnValues="ALL_NEW",
            )
            return int(response["Attributes"][COUNT_ATTRIBUTE])
        except ClientError as error:
            if _error_code(error) != "ConditionalCheckFailedException":
                self._failed_open("record_request", error, identity)
                return 0
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("record_request", error, identity)
            return 0

        try:
            self.table.put_item(
                Item={
                    **self.key(identity),
                    COUNT_ATTRIBUTE: 1,
                    TTL_ATTRIBUTE: current + self.window_seconds,
                }
            )
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("record_request", error, identity)
            return 0
        return 1

    def check(self, identity: str) -> tuple[bool, Optional[int]]:
        """Count this request and report whether it should be rejected.

        Returns `(is_limited, retry_after_seconds)`. The count happens first so a
        caller who is already over the limit keeps extending nothing: the window is
        """
        count = self.record_request(identity)
        if count == 0 or count <= self.max_requests:
            return False, None
        return True, self.retry_after(identity)


WINDOW_SECONDS = 60


def build_limiters(*, table_client: Optional[TableClient] = None) -> dict[str, SharedRateLimiter]:
    """One limiter per class, each carrying that class's configured cap."""
    caps = {
        GET_CLASS: settings.RATE_LIMIT_GET_REQUESTS_PER_MINUTE,
        AUTH_CLASS: settings.RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE,
        ADMIN_CLASS: settings.RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE,
        DEFAULT_CLASS: settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    }
    return {
        name: SharedRateLimiter(cap, WINDOW_SECONDS, request_class=name, table_client=table_client)
        for name, cap in caps.items()
    }


shared_rate_limiters: dict[str, SharedRateLimiter] = build_limiters()


def limiter_for(method: str, path: str) -> SharedRateLimiter:
    """The limiter guarding the class this request belongs to."""
    return shared_rate_limiters[request_class(method, path)]
