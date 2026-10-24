"""CarModPicker's `IdentityHooks`: how the package reads and writes `users`.

Looks a user up, decides whether they may sign in, supplies this product's
claims, and creates the row a package registration needs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from webbpulse.dynamodb import ItemNotFound
from webbpulse.identity import AuthenticationRefused, LoginRejected
from webbpulse.identity.oauth import OAuthLinkStore
from webbpulse.identity.storage import PasskeyStore

from app.common.db.dynamo.users import (
    OAuthAccountRepository,
    UniqueAttributeTaken,
    User,
    UserRepository,
    WebAuthnCredentialRepository,
)

REFUSAL_MESSAGE = "This account may not sign in."

SUPERUSER_ROLE = "superuser"
ADMIN_ROLE = "admin"

REGISTRATION_ATTRIBUTES = frozenset({"username", "email_verified"})

EMAIL_TAKEN_CODE = "EMAIL_TAKEN"
EMAIL_TAKEN_MESSAGE = "Another account already uses that email address."


class CarModPickerIdentityHooks:
    """CarModPicker's `IdentityHooks`, satisfying the protocol structurally.

    Stateless apart from three repositories, so one instance is shared per
    process. Constructing it makes no AWS call and caches no boto3 object.
    """

    def __init__(
        self,
        users: UserRepository | None = None,
        *,
        oauth_accounts: OAuthAccountRepository | None = None,
        webauthn_credentials: WebAuthnCredentialRepository | None = None,
        package_passkeys: PasskeyStore | None = None,
        package_oauth_links: OAuthLinkStore | None = None,
    ) -> None:
        """The three repositories and the two package stores, all injectable.

        The repositories default because they are this product's tables; the package
        stores never do, so their table names are spelled in exactly one place.
        """
        self._users = users if users is not None else UserRepository()
        self._oauth_accounts = oauth_accounts if oauth_accounts is not None else OAuthAccountRepository()
        self._webauthn_credentials = (
            webauthn_credentials if webauthn_credentials is not None else WebAuthnCredentialRepository()
        )
        self._package_passkeys = package_passkeys
        self._package_oauth_links = package_oauth_links

    def load_user_by_id(self, user_id: str) -> Mapping[str, Any] | None:
        """The user whose id is this `sub`, or `None`.

        A `sub` that is not a UUID gets the same `None` a missing row does, since it
        is not a token this service minted.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            return None
        user = self._users.get(parsed)
        return _as_mapping(user) if user is not None else None

    def load_user_by_email(self, email: str) -> Mapping[str, Any] | None:
        """The user with this address or username, or `None`.

        The login form accepts either. A value containing `@` is tried on the
        `email_lower-index` first and then on the `username_lower-index`, because
        some accounts have a username that is itself an address; anything else is
        a username only. Both repository methods lowercase, so casing never
        matters.
        """
        identifier = email.strip()
        user = self._users.get_by_email(identifier) if "@" in identifier else None
        if user is None:
            user = self._users.get_by_username(identifier)
        return _as_mapping(user) if user is not None else None

    def may_authenticate(self, user: Mapping[str, Any]) -> None:
        """Permit an enabled, verified, human account and refuse everything else.

        Returns `None` to permit and raises to refuse, which is the protocol's
        shape and the one where forgetting to return lands on the refusing side.
        """
        if user.get("disabled"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="ACCOUNT_DISABLED")
        if user.get("is_service_account"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="SERVICE_ACCOUNT")
        if not user.get("email_verified"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="EMAIL_NOT_VERIFIED")

    def claims_for(self, user: Mapping[str, Any]) -> Mapping[str, Any]:
        """This product's claims: the roles list and the display username.

        `roles` is always a list so a consumer's check is one shape, ordered most
        privileged first. Consumers must test membership and never index.
        """
        roles: list[str] = []
        if user.get("is_superuser"):
            roles.append(SUPERUSER_ROLE)
        if user.get("is_admin"):
            roles.append(ADMIN_ROLE)
        return {"roles": roles, "username": user["username"]}

    def has_other_sign_in_method(self, user_id: str) -> bool:
        """Whether this user holds a sign-in method that `unlink` does not count.

        A legacy or package passkey, or a legacy or package OAuth link; not the
        password, which since row 13 lives only in the package's `credentials`
        table and is one of the things `unlink` counts for itself. Not second
        factors. An unparseable id answers `False`, the refusing side.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            return False

        if self._webauthn_credentials.list_by_user(parsed):
            return True
        if self._oauth_accounts.list_by_user(parsed):
            return True

        subject = str(parsed)
        if self._package_passkeys is not None and self._package_passkeys.list_for_user(subject):
            return True
        return bool(self._package_oauth_links is not None and self._package_oauth_links.list_for_user(subject))

    def create_user(self, *, email: str, attributes: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create a CarModPicker user row for a package registration and return it.

        The username is derived from the address when none is supplied. Only
        `REGISTRATION_ATTRIBUTES` are kept, because the public register route passes
        caller supplied attributes through; role flags such as `is_superuser` are
        set out of band, never at registration.
        """
        record = {key: value for key, value in attributes.items() if key in REGISTRATION_ATTRIBUTES}
        record["email"] = email
        record["username"] = str(record.get("username") or _username_from(email))
        user = User(**record)
        return _as_mapping(self._users.create_user(user))

    def mark_email_verified(self, user_id: str) -> None:
        """Record that this user's address is confirmed, on the `users` row.

        Raises `ValueError` for a missing row rather than passing silently: the link
        is already spent, so a failure has to be visible.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            raise ValueError(f"mark_email_verified was given {user_id!r}, which is not one of this product's user ids.")
        try:
            self._users.update(parsed, email_verified=True)
        except ItemNotFound as exc:
            raise ValueError(
                f"mark_email_verified found no user with id {parsed}. The link was consumed, "
                "so the address is not verified and the user needs a new one."
            ) from exc

    def change_email(self, user_id: str, email: str) -> None:
        """Move this user's sign-in address and mark it verified, on the `users` row.

        Called by the package only after the link mailed to `email` is spent. Goes
        through `update_user` so the email reservation moves in the same transaction.
        Raises `LoginRejected` with 409 `EMAIL_TAKEN` when another account claimed the
        address after the package's check, and `ValueError` for a missing row.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            raise ValueError(f"change_email was given {user_id!r}, which is not one of this product's user ids.")
        try:
            self._users.update_user(parsed, email=email, email_verified=True)
        except UniqueAttributeTaken as exc:
            raise LoginRejected(EMAIL_TAKEN_MESSAGE, error_code=EMAIL_TAKEN_CODE, status_code=409) from exc
        except ItemNotFound as exc:
            raise ValueError(f"change_email found no user with id {parsed}. The link was consumed.") from exc

    def delete_user(self, user_id: str) -> bool:
        """Hard-delete this product's users row, returning whether one was there.

        Only the users row and its username and email reservations. The identity
        rows are the users-table stream purge's to remove, so an ephemeral e2e
        user's teardown exercises the same deletion path a real account does. An
        unparseable id answers `False`, as a missing row does.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            return False
        user = self._users.get(parsed)
        if user is None:
            return False
        self._users.delete_user(user)
        return True

    def on_user_created(self, user: Mapping[str, Any], via: str) -> None:
        """No side effects to run.

        The verification email is sent by the package's own register flow, and a new
        CarModPicker account owns no default rows.
        """
        del user, via

    def user_repository(self) -> object:
        """CarModPicker's users repository. Typed `object`, as the protocol has it."""
        return self._users


def _as_uuid(value: str) -> UUID | None:
    """`value` as a UUID, or `None` when it is not one."""
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _as_mapping(user: User) -> Mapping[str, Any]:
    """A user row as the plain mapping the hooks protocol returns.

    `mode="json"` so the id reaches the package as the string it becomes in the
    `sub` claim rather than as a `UUID`.
    """
    return user.model_dump(mode="json")


def _username_from(email: str) -> str:
    """A username derived from the address's local part, with no collision suffix.

    Uniqueness is a sentinel row in the same transaction as the user row, so a
    collision fails the registration atomically and the caller picks another.
    """
    return email.partition("@")[0].strip() or "user"
