"""Covers CarModPicker's side of the identity email change flow: the `change_email`
hook the package calls once the link mailed to the new address is spent.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from webbpulse.identity.flows import IdentityFlows

from app.common.db.dynamo.users import UniqueAttributeTaken, UserRepository
from app.domains.identity.identity_hooks import CarModPickerIdentityHooks


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

    with pytest.raises(UniqueAttributeTaken):
        hooks.change_email(created["id"], "holder@example.com")

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
