"""Covers CarModPicker's side of the identity email change flow: the `change_email`
hook the package calls once the link mailed to the new address is spent.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from webbpulse.identity import (
    EMAIL_CHANGE_CONFIRM_PATH,
    IdentitySettings,
    IdentityStores,
    InMemoryCredentialStore,
    InMemoryIdentityTokenStore,
    InMemoryLoginAttemptStore,
    InMemoryRefreshTokenStore,
    LoginRejected,
    RecordingEmailSender,
    TokenService,
    build_identity_router,
    identity_prefix,
)
from webbpulse.identity.flows import IdentityFlows
from webbpulse.testing import FakeKms

from app.common.db.dynamo.users import UserRepository
from app.domains.identity.identity_hooks import EMAIL_TAKEN_CODE, CarModPickerIdentityHooks

KEY_ARN = "arn:aws:kms:us-west-2:748861776298:key/11111111-2222-3333-4444-555555555555"


@pytest.fixture
def hooks(dynamo_tables: Any) -> CarModPickerIdentityHooks:
    """Hooks over the real repositories against moto."""
    return CarModPickerIdentityHooks()


def test_the_package_finds_the_change_email_hook(hooks: CarModPickerIdentityHooks) -> None:
    """The flow answers 501 EMAIL_CHANGE_UNSUPPORTED without the hook, so the mount
    only works end to end when the package's own check accepts these hooks.
    """
    found = IdentityFlows._require_email_change_hook(SimpleNamespace(_hooks=hooks))  # type: ignore[arg-type]

    assert found == hooks.change_email


def test_change_email_moves_the_address_and_marks_it_verified(hooks: CarModPickerIdentityHooks) -> None:
    """A spent link proves the new mailbox, so the new address lands verified."""
    created = hooks.create_user(email="before@example.com", attributes={"username": "mover"})
    assert created["email_verified"] is False

    hooks.change_email(created["id"], "after@example.com")

    reloaded = hooks.load_user_by_id(created["id"])
    assert reloaded is not None
    assert reloaded["email"] == "after@example.com"
    assert reloaded["email_verified"] is True
    assert hooks.load_user_by_email("after@example.com") is not None
    assert hooks.load_user_by_email("before@example.com") is None


def test_change_email_releases_the_old_address_for_another_account(hooks: CarModPickerIdentityHooks) -> None:
    """The old address's reservation moves in the same transaction, so it is free again."""
    created = hooks.create_user(email="released@example.com", attributes={"username": "releaser"})
    hooks.change_email(created["id"], "released-new@example.com")

    other = hooks.create_user(email="released@example.com", attributes={"username": "claimer"})

    assert other["email"] == "released@example.com"


def test_change_email_refuses_an_address_another_account_holds(hooks: CarModPickerIdentityHooks) -> None:
    """A race where another account claimed the address since the request fails the
    write rather than giving two accounts one address.
    """
    hooks.create_user(email="holder@example.com", attributes={"username": "holder"})
    created = hooks.create_user(email="racer@example.com", attributes={"username": "racer"})

    with pytest.raises(LoginRejected) as refused:
        hooks.change_email(created["id"], "holder@example.com")

    assert refused.value.status_code == 409
    assert refused.value.error_code == EMAIL_TAKEN_CODE

    stored = UserRepository().get_by_email("racer@example.com")
    assert stored is not None


def test_change_email_raises_for_an_unknown_user(hooks: CarModPickerIdentityHooks) -> None:
    """A spent link naming no user raises rather than reporting success."""
    with pytest.raises(ValueError):
        hooks.change_email(str(uuid4()), "nobody@example.com")


def test_change_email_raises_for_a_value_that_is_not_an_id(hooks: CarModPickerIdentityHooks) -> None:
    """An unparseable target is a caller bug, so it raises."""
    with pytest.raises(ValueError):
        hooks.change_email("not-a-uuid", "nobody@example.com")


class _RivalClaimsFirst(CarModPickerIdentityHooks):
    """Hooks where another account claims the new address just before the write.

    That is the window between the package's uniqueness re-check on confirm and the
    product's own transaction, which only the write's reservation can catch.
    """

    def change_email(self, user_id: str, email: str) -> None:
        """Register a rival on `email`, then move the address as the product does."""
        self.create_user(email=email, attributes={"username": "rival"})
        super().change_email(user_id, email)


def _settings() -> IdentitySettings:
    """Identity settings with links on, enough to issue and spend an email change link."""
    return IdentitySettings(
        environment="test",
        issuer="https://api.staging.carmodpicker.com/api/auth",
        audience="carmodpicker-test-api",
        signing_key_arns=[KEY_ARN],
        email_verification_required=False,
        frontend_base_url="https://staging.carmodpicker.com",
        email_from="no-reply@staging.carmodpicker.com",
        product_name="CarModPicker",
        support_email="support@carmodpicker.com",
    )


@pytest.fixture
def race(dynamo_tables: Any) -> Iterator[tuple[TestClient, RecordingEmailSender, IdentityFlows, _RivalClaimsFirst]]:
    """The package router over the racing hooks, plus flows sharing its link store."""
    kms = FakeKms(rsa.generate_private_key(public_exponent=65537, key_size=2048))
    settings = _settings()
    hooks = _RivalClaimsFirst()
    stores = IdentityStores(
        credentials=InMemoryCredentialStore(),
        refresh_tokens=InMemoryRefreshTokenStore(),
        identity_tokens=InMemoryIdentityTokenStore(),
    )
    sender = RecordingEmailSender()
    flows = IdentityFlows(
        settings,
        hooks,
        stores,
        TokenService(settings, kms),
        attempts=InMemoryLoginAttemptStore(),
        email_sender=sender,
    )
    app = FastAPI()
    app.include_router(
        build_identity_router(
            settings,
            hooks,
            stores,
            kms_client=kms,
            attempts=InMemoryLoginAttemptStore(),
            email_sender=sender,
            limiter_enabled=False,
        )
    )
    with TestClient(app, base_url="https://api.staging.carmodpicker.com") as client:
        yield client, sender, flows, hooks


def _token_mailed_to(sender: RecordingEmailSender, address: str) -> str:
    """The token in the most recent link mailed to `address`."""
    message = sender.last_for(address)
    assert message is not None
    for line in message.text.splitlines():
        if line.startswith("http"):
            return parse_qs(urlsplit(line).query)["token"][0]
    raise AssertionError("the message carried no link")


def test_confirm_answers_409_when_another_account_wins_the_address_race(
    race: tuple[TestClient, RecordingEmailSender, IdentityFlows, _RivalClaimsFirst],
) -> None:
    """An address claimed between the request and the write answers 409 EMAIL_TAKEN,
    not 500, and the requester keeps their old address.
    """
    client, sender, flows, hooks = race
    created = hooks.create_user(email="requester@example.com", attributes={"username": "requester"})
    flows.request_email_change(user_id=created["id"], new_email="contested@example.com")

    response = client.post(
        f"{identity_prefix(_settings())}{EMAIL_CHANGE_CONFIRM_PATH}",
        json={"token": _token_mailed_to(sender, "contested@example.com")},
    )

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == EMAIL_TAKEN_CODE
    reloaded = hooks.load_user_by_id(created["id"])
    assert reloaded is not None
    assert reloaded["email"] == "requester@example.com"
