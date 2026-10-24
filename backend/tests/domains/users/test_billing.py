"""Stripe billing routes against a faked Stripe gateway and signed webhook deliveries."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Generator
from uuid import uuid4

import pytest
import stripe
from fastapi.testclient import TestClient
from webbpulse.testing import FakeStripeGateway, sign_stripe_payload

from app.common.db.dynamo.users import User, UserRepository
from app.domains.users.services.billing_service import (
    PREMIUM_PRICE_LOOKUP_KEY,
    get_gateway_factory,
    subscription_state,
)
from app.main import app as fastapi_app
from tests.conftest import auth_headers_for

WEBHOOK_SECRET = "whsec_test_billing_secret"
API_KEY = "rk_test_billing_key"
PERIOD_END = 1_900_000_000
WEBHOOK_PATH = "/api/billing/stripe/webhook"


class FakeGateway(FakeStripeGateway):
    """The shared Stripe fake with an injectable failure and a record of retrieved subscriptions."""

    def __init__(self) -> None:
        """Start with one premium price and no customers or subscriptions."""
        super().__init__(prices={PREMIUM_PRICE_LOOKUP_KEY: "price_premium"})
        self.retrieved: list[str] = []
        self.fail_with: Exception | None = None
        self.price_barrier: threading.Barrier | None = None

    def _maybe_fail(self) -> None:
        """Raise the configured failure, if any."""
        if self.fail_with is not None:
            raise self.fail_with

    def find_price_id(self, lookup_key: str) -> str | None:
        """The seeded price, after every racer behind the barrier has arrived."""
        self._maybe_fail()
        if self.price_barrier is not None:
            self.price_barrier.wait()
        return super().find_price_id(lookup_key)

    def ensure_customer(self, **kwargs: Any) -> str:
        """The owner's one customer id, unless a failure is configured."""
        self._maybe_fail()
        return super().ensure_customer(**kwargs)

    def create_checkout_session(self, **kwargs: Any) -> str:
        """Record the session and answer a fake Checkout URL."""
        self._maybe_fail()
        return super().create_checkout_session(**kwargs)

    def create_portal_session(self, **kwargs: Any) -> str:
        """Record the session and answer a fake portal URL."""
        self._maybe_fail()
        return super().create_portal_session(**kwargs)

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Record and answer a seeded subscription."""
        self._maybe_fail()
        self.retrieved.append(subscription_id)
        return super().retrieve_subscription(subscription_id)


@pytest.fixture
def gateway() -> Generator[FakeGateway, None, None]:
    """A fake gateway wired into the app in place of Stripe."""
    fake = FakeGateway()
    fastapi_app.dependency_overrides[get_gateway_factory] = lambda: lambda _settings: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_gateway_factory, None)


@pytest.fixture
def stripe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure Stripe through the environment only."""
    monkeypatch.delenv("APP_SECRETS_ARN", raising=False)
    monkeypatch.setenv("STRIPE_API_KEY", API_KEY)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)


@pytest.fixture
def no_stripe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave Stripe entirely unconfigured."""
    monkeypatch.delenv("APP_SECRETS_ARN", raising=False)
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)


def _subscription(sub_id: str, customer: str, status: str, user_id: str | None = None) -> dict[str, Any]:
    """A subscription dict in the current API shape, period end on its items."""
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "metadata": {"user_id": user_id} if user_id else {},
        "items": {"data": [{"id": "si_1", "current_period_end": PERIOD_END}]},
    }


def _deliver(
    client: TestClient,
    event_type: str,
    obj: dict[str, Any],
    *,
    event_id: str | None = None,
    secret: str = WEBHOOK_SECRET,
) -> Any:
    """Sign and post one webhook event, as Stripe would."""
    payload = json.dumps(
        {
            "id": event_id or f"evt_{uuid4().hex}",
            "object": "event",
            "type": event_type,
            "data": {"object": obj},
        }
    ).encode()
    header = sign_stripe_payload(payload, secret)
    return client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )


def _reload(user: User) -> User:
    """The user as currently stored."""
    return UserRepository().get_or_raise(user.id)


def test_checkout_creates_customer_and_session(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A free user gets a customer, a persisted customer id and a checkout URL."""
    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 200, response.text
    assert response.json()["url"].startswith("https://checkout.stripe.test/")
    assert gateway.customer_creates == 1
    [customer] = gateway.customers.values()
    assert customer["email"] == test_user.email
    assert customer["metadata"] == {"user_id": str(test_user.id)}
    assert _reload(test_user).stripe_customer_id == customer["id"]
    session = gateway.checkout_sessions[0]
    assert session["price"] == "price_premium"
    assert session["customer"] == customer["id"]
    assert session["client_reference_id"] == str(test_user.id)
    assert session["metadata"] == {"user_id": str(test_user.id)}
    assert session["success_url"].endswith("/checkout?status=success&session_id={CHECKOUT_SESSION_ID}")
    assert session["cancel_url"].endswith("/checkout?status=cancelled")


def test_concurrent_checkouts_share_one_customer(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """Two checkouts racing for a user with no stored customer end with one customer."""
    gateway.price_barrier = threading.Barrier(2, timeout=10)
    headers = auth_headers_for(test_user.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post("/api/billing/checkout-session", headers=headers), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert gateway.customer_creates == 1
    [customer_id] = gateway.customers
    assert {session["customer"] for session in gateway.checkout_sessions} == {customer_id}
    assert len(gateway.checkout_sessions) == 2
    assert _reload(test_user).stripe_customer_id == customer_id


def test_checkout_reuses_existing_customer(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A user who already has a customer id is not given a second customer."""
    UserRepository().update_user(test_user.id, stripe_customer_id="cus_existing")

    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 200
    assert gateway.customers == {}
    assert gateway.checkout_sessions[0]["customer"] == "cus_existing"


def test_checkout_refuses_premium_user(
    client: TestClient, premium_test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """An active premium user cannot start a second subscription."""
    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(premium_test_user.id))

    assert response.status_code == 409
    assert response.json()["error_code"] == "ALREADY_PREMIUM"
    assert gateway.checkout_sessions == []


def test_checkout_without_stripe_is_503(
    client: TestClient, test_user: User, gateway: FakeGateway, no_stripe_env: None
) -> None:
    """An unconfigured stage answers a declared 503."""
    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 503
    assert response.json()["error_code"] == "STRIPE_NOT_CONFIGURED"


def test_checkout_without_price_is_503(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A missing premium price answers 503 and creates no customer."""
    gateway.prices = {}

    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 503
    assert response.json()["error_code"] == "STRIPE_PRICE_MISSING"
    assert gateway.customers == {}


def test_checkout_stripe_failure_is_502(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A Stripe error surfaces as a 502."""
    gateway.fail_with = stripe.APIConnectionError("down")

    response = client.post("/api/billing/checkout-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 502
    assert response.json()["error_code"] == "STRIPE_ERROR"


def test_checkout_requires_auth(client: TestClient, gateway: FakeGateway, stripe_env: None) -> None:
    """An anonymous caller is refused."""
    assert client.post("/api/billing/checkout-session").status_code == 401


def test_portal_without_customer_is_409(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A user with no Stripe customer has nothing to manage."""
    response = client.post("/api/billing/portal-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 409
    assert response.json()["error_code"] == "NO_BILLING_ACCOUNT"


def test_portal_returns_to_profile(client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None) -> None:
    """The portal session is opened for the user's customer and returns to the profile."""
    UserRepository().update_user(test_user.id, stripe_customer_id="cus_portal")

    response = client.post("/api/billing/portal-session", headers=auth_headers_for(test_user.id))

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://billing.stripe.test/")
    assert gateway.portal_sessions[0]["customer"] == "cus_portal"
    assert gateway.portal_sessions[0]["return_url"].endswith("/profile")


def test_webhook_without_secret_is_503(
    client: TestClient, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stage with an API key but no signing secret answers the declared 503."""
    monkeypatch.delenv("APP_SECRETS_ARN", raising=False)
    monkeypatch.setenv("STRIPE_API_KEY", API_KEY)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

    response = _deliver(client, "customer.subscription.updated", {"id": "sub_1"})

    assert response.status_code == 503
    assert response.json()["error_code"] == "STRIPE_NOT_CONFIGURED"


def test_webhook_unconfigured_is_503(client: TestClient, gateway: FakeGateway, no_stripe_env: None) -> None:
    """A stage with no Stripe keys at all answers the same 503 to an empty body."""
    response = client.post(WEBHOOK_PATH, json={})

    assert response.status_code == 503
    assert response.json()["error_code"] == "STRIPE_NOT_CONFIGURED"


def test_webhook_bad_signature_is_400(client: TestClient, gateway: FakeGateway, stripe_env: None) -> None:
    """A delivery signed with the wrong secret is refused."""
    response = _deliver(client, "customer.subscription.updated", {"id": "sub_1"}, secret="whsec_wrong")

    assert response.status_code == 400
    assert response.json()["error_code"] == "STRIPE_SIGNATURE_INVALID"
    assert gateway.retrieved == []


def test_webhook_missing_signature_is_400(client: TestClient, gateway: FakeGateway, stripe_env: None) -> None:
    """A delivery with no signature header is refused."""
    response = client.post(WEBHOOK_PATH, json={})

    assert response.status_code == 400


def test_checkout_completed_upgrades_user(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A completed checkout makes the referenced user premium and links the customer."""
    gateway.subscriptions["sub_1"] = _subscription("sub_1", "cus_new", "active")

    response = _deliver(
        client,
        "checkout.session.completed",
        {
            "id": "cs_1",
            "object": "checkout.session",
            "customer": "cus_new",
            "subscription": "sub_1",
            "client_reference_id": str(test_user.id),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["handled"] is True
    stored = _reload(test_user)
    assert stored.subscription_tier == "premium"
    assert stored.subscription_status == "active"
    assert stored.subscription_expires_at == datetime.fromtimestamp(PERIOD_END, UTC)
    assert stored.stripe_customer_id == "cus_new"


def test_subscription_deleted_downgrades_by_customer(
    client: TestClient, premium_test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A deleted subscription found through the customer id index downgrades the user."""
    UserRepository().update_user(premium_test_user.id, stripe_customer_id="cus_gone")
    gateway.subscriptions["sub_2"] = _subscription("sub_2", "cus_gone", "canceled")

    response = _deliver(
        client,
        "customer.subscription.deleted",
        {"id": "sub_2", "object": "subscription", "customer": "cus_gone"},
    )

    assert response.status_code == 200
    stored = _reload(premium_test_user)
    assert stored.subscription_tier == "free"
    assert stored.subscription_status == "cancelled"


def test_payment_failed_reads_subscription_from_invoice_parent(
    client: TestClient, premium_test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A failed invoice in the current API shape syncs the subscription it bills."""
    UserRepository().update_user(premium_test_user.id, stripe_customer_id="cus_unpaid")
    gateway.subscriptions["sub_3"] = _subscription("sub_3", "cus_unpaid", "unpaid")

    response = _deliver(
        client,
        "invoice.payment_failed",
        {
            "id": "in_1",
            "object": "invoice",
            "customer": "cus_unpaid",
            "parent": {"subscription_details": {"subscription": "sub_3"}},
        },
    )

    assert response.status_code == 200
    assert gateway.retrieved == ["sub_3"]
    stored = _reload(premium_test_user)
    assert stored.subscription_tier == "free"
    assert stored.subscription_status == "expired"


def test_failed_renewal_drops_premium_right_away(
    client: TestClient, premium_test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A failed renewal leaves the subscription past_due, which ends premium at once."""
    UserRepository().update_user(premium_test_user.id, stripe_customer_id="cus_past_due")
    gateway.subscriptions["sub_7"] = _subscription("sub_7", "cus_past_due", "past_due")

    response = _deliver(
        client,
        "invoice.payment_failed",
        {"id": "in_2", "object": "invoice", "customer": "cus_past_due", "subscription": "sub_7"},
    )

    assert response.status_code == 200
    assert gateway.retrieved == ["sub_7"]
    stored = _reload(premium_test_user)
    assert stored.subscription_tier == "free"
    assert stored.subscription_status == "expired"


def test_duplicate_delivery_is_applied_once(
    client: TestClient, test_user: User, gateway: FakeGateway, stripe_env: None
) -> None:
    """A redelivered event id is acknowledged without being applied again."""
    UserRepository().update_user(test_user.id, stripe_customer_id="cus_dup")
    gateway.subscriptions["sub_4"] = _subscription("sub_4", "cus_dup", "active")
    obj = {"id": "sub_4", "object": "subscription", "customer": "cus_dup"}

    first = _deliver(client, "customer.subscription.created", obj, event_id="evt_dup")
    second = _deliver(client, "customer.subscription.created", obj, event_id="evt_dup")

    assert first.json()["handled"] is True
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert gateway.retrieved == ["sub_4"]


def test_unhandled_event_type_is_acknowledged(client: TestClient, gateway: FakeGateway, stripe_env: None) -> None:
    """An event type billing does not act on still answers 200."""
    response = _deliver(client, "customer.created", {"id": "cus_x", "object": "customer"})

    assert response.status_code == 200
    assert response.json() == {"received": True, "handled": False, "duplicate": False}


def test_failed_processing_releases_the_claim(
    test_user: User, gateway: FakeGateway, stripe_env: None, dynamo_tables: Any
) -> None:
    """A delivery whose processing fails can be retried and then applied."""
    UserRepository().update_user(test_user.id, stripe_customer_id="cus_retry")
    gateway.subscriptions["sub_5"] = _subscription("sub_5", "cus_retry", "active")
    obj = {"id": "sub_5", "object": "subscription", "customer": "cus_retry"}
    client = TestClient(fastapi_app, raise_server_exceptions=False)

    gateway.fail_with = stripe.APIConnectionError("down")
    failed = _deliver(client, "customer.subscription.updated", obj, event_id="evt_retry")
    gateway.fail_with = None
    retried = _deliver(client, "customer.subscription.updated", obj, event_id="evt_retry")

    assert failed.status_code == 500
    assert retried.status_code == 200
    assert retried.json()["handled"] is True
    assert _reload(test_user).subscription_tier == "premium"


def test_unknown_customer_is_acknowledged(client: TestClient, gateway: FakeGateway, stripe_env: None) -> None:
    """A subscription that matches no user is acknowledged, not retried forever."""
    gateway.subscriptions["sub_6"] = _subscription("sub_6", "cus_nobody", "active")

    response = _deliver(
        client,
        "customer.subscription.updated",
        {"id": "sub_6", "object": "subscription", "customer": "cus_nobody"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("stripe_status", "tier", "status"),
    [
        ("active", "premium", "active"),
        ("trialing", "premium", "active"),
        ("past_due", "free", "expired"),
        ("canceled", "free", "cancelled"),
        ("unpaid", "free", "expired"),
        ("incomplete", "free", "expired"),
        ("incomplete_expired", "free", "expired"),
    ],
)
def test_subscription_state_mapping(stripe_status: str, tier: str, status: str) -> None:
    """Each Stripe status maps onto the user's tier and status."""
    state = subscription_state(_subscription("sub", "cus", stripe_status))

    assert state["subscription_tier"] == tier
    assert state["subscription_status"] == status
    assert state["subscription_expires_at"] == datetime.fromtimestamp(PERIOD_END, UTC)


def test_subscription_state_falls_back_to_legacy_period_end() -> None:
    """An older API shape with the period end on the subscription still yields an expiry."""
    state = subscription_state({"status": "active", "current_period_end": PERIOD_END})

    assert state["subscription_expires_at"] == datetime.fromtimestamp(PERIOD_END, UTC)
