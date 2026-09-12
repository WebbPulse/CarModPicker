"""Tests for the package's passkey and OAuth switches on the identity function.

Pins which environment variables gate which routes and where the client secrets come from.
"""

from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

import pytest

from app.composition.identity_hooks import CarModPickerIdentityHooks
from app.db.dynamo.users import User

from .entrypoints.test_route_split import _pairs
from .test_identity_row5 import ISSUER, FakeKms
from .test_identity_row5 import identity_env as _identity_env
from .test_identity_row5 import private_key as _private_key

identity_env = _identity_env
private_key = _private_key

OAUTH_FLOW_PATHS = (
    ("GET", "/api/auth/oauth/{provider}/start"),
    ("GET", "/api/auth/oauth/callback"),
    ("POST", "/api/auth/oauth/{provider}/link"),
    ("GET", "/api/auth/oauth/links"),
    ("DELETE", "/api/auth/oauth/{provider}/link"),
)

PASSKEY_MANAGEMENT_PATHS = (
    ("POST", "/api/auth/passkeys/register/options"),
    ("POST", "/api/auth/passkeys/register/verify"),
    ("GET", "/api/auth/passkeys"),
    ("PATCH", "/api/auth/passkeys/{credential_id}"),
    ("DELETE", "/api/auth/passkeys/{credential_id}"),
)

PASSKEY_LOGIN_PATHS = (
    ("POST", "/api/auth/login/passkey/options"),
    ("POST", "/api/auth/login/passkey/verify"),
)

GOOGLE_CLIENT_ID = "111111111111-carmodpicker.apps.googleusercontent.com"
GITHUB_CLIENT_ID = "Iv1.carmodpicker00000"
GOOGLE_CLIENT_SECRET = "google-client-secret-not-a-real-one"
GITHUB_CLIENT_SECRET = "github-client-secret-not-a-real-one"

FRONTEND_ORIGIN = "https://staging.carmodpicker.com"


@pytest.fixture
def passkeys_on(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both passkey flags on, as a fully enabled workspace sets them."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "true")
    monkeypatch.setenv("IDENTITY_WEBAUTHN_ORIGINS", json.dumps([FRONTEND_ORIGIN]))


@pytest.fixture
def oauth_on(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both providers' client ids as environment, and their secrets alongside."""
    monkeypatch.setenv("IDENTITY_GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_GITHUB_CLIENT_ID", GITHUB_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_OAUTH_REDIRECT_URIS", json.dumps([f"{ISSUER}/oauth/callback"]))
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", GITHUB_CLIENT_SECRET)


def _build_identity_app(private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Build the identity application with boto3 clients faked, reaching no network."""
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        """Return a fake KMS or SES client and refuse any other service."""
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"the identity router asked for an unexpected client: {service}")

    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


@pytest.fixture
def passkey_app(passkeys_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with both passkey flags on and no OAuth."""
    yield from _build_identity_app(private_key, monkeypatch)


@pytest.fixture
def oauth_app(oauth_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with both providers configured and no passkeys."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    yield from _build_identity_app(private_key, monkeypatch)


@pytest.fixture
def everything_app(
    passkeys_on: None, oauth_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """Both switches on, which is what the staging workspace applies."""
    yield from _build_identity_app(private_key, monkeypatch)


def test_the_passkey_routes_mount_with_both_flags_on(passkey_app: Any) -> None:
    """All seven passkey routes mount under the issuer path when both flags are on."""
    pairs = _pairs(passkey_app)

    for method, path in PASSKEY_MANAGEMENT_PATHS + PASSKEY_LOGIN_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"


def test_the_passkey_routes_are_absent_with_the_flag_off(oauth_app: Any) -> None:
    """The flag off removes all seven routes rather than leaving the package default on."""
    pairs = _pairs(oauth_app)

    for method, path in PASSKEY_MANAGEMENT_PATHS + PASSKEY_LOGIN_PATHS:
        assert (method, path) not in pairs, f"{method} {path} mounted with the flag off"

    assert ("GET", "/api/auth/passkeys/availability") in pairs


def test_passwordless_off_keeps_the_five_management_routes(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passwordless off still declares all seven routes; the two login routes refuse instead."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    monkeypatch.setenv("IDENTITY_WEBAUTHN_ORIGINS", json.dumps([FRONTEND_ORIGIN]))

    app = next(_build_identity_app(private_key, monkeypatch))
    pairs = _pairs(app)

    for method, path in PASSKEY_MANAGEMENT_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"
    for method, path in PASSKEY_LOGIN_PATHS:
        assert (method, path) in pairs, (
            f"{method} {path} is declared by passkeys_enabled and refused by passwordless, not removed by it"
        )


def test_the_webauthn_origin_is_the_frontend_and_not_the_api(passkeys_on: None) -> None:
    """The WebAuthn origin is the SPA origin, which is what makes a passkey phishing resistant."""
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.webauthn_origins == [FRONTEND_ORIGIN]
    assert identity_settings.rp_id == "staging.carmodpicker.com"
    assert identity_settings.rp_name == "CarModPicker"


def test_the_oauth_routes_mount_when_a_provider_has_a_client_id(
    oauth_app: Any,
) -> None:
    """All five flow routes, with both providers configured."""
    pairs = _pairs(oauth_app)

    for method, path in OAUTH_FLOW_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"


def test_the_oauth_flow_routes_are_absent_with_no_client_id(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client id is the switch for the flow routes; the stores are not."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    app = next(_build_identity_app(private_key, monkeypatch))
    pairs = _pairs(app)

    for method, path in OAUTH_FLOW_PATHS:
        assert (method, path) not in pairs, f"{method} {path} mounted with no client id"


def test_the_providers_route_mounts_with_no_oauth_configured(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The providers route is unconditional and answers an empty list when nothing is configured."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    app = next(_build_identity_app(private_key, monkeypatch))

    assert ("GET", "/api/auth/oauth/providers") in _pairs(app)


def test_the_providers_route_lists_both_configured_providers(
    everything_app: Any,
) -> None:
    """A provider is advertised only when both its id and its secret arrived."""
    from fastapi.testclient import TestClient

    with TestClient(everything_app) as client:
        response = client.get("/api/auth/oauth/providers")

    assert response.status_code == 200
    listed = {entry["id"] for entry in response.json()["providers"]}
    assert listed == {"google", "github"}


def test_a_provider_with_no_secret_is_not_advertised(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An id with no secret leaves the provider unadvertised and the deployment still starts."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    monkeypatch.setenv("IDENTITY_GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_GITHUB_CLIENT_ID", GITHUB_CLIENT_ID)
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)

    from fastapi.testclient import TestClient

    app = next(_build_identity_app(private_key, monkeypatch))
    with TestClient(app) as client:
        response = client.get("/api/auth/oauth/providers")

    assert response.status_code == 200
    listed = {entry["id"] for entry in response.json()["providers"]}
    assert listed == {"google"}


def test_the_secret_keys_are_the_ones_terraform_writes() -> None:
    """The provider to secret key map matches the keys Terraform writes into the app secret."""
    from app.composition.identity import OAUTH_SECRET_KEYS

    assert OAUTH_SECRET_KEYS == {
        "google": "OAUTH_GOOGLE_CLIENT_SECRET",
        "github": "OAUTH_GITHUB_CLIENT_SECRET",
    }


def test_the_client_secrets_are_read_from_the_app_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both client secrets resolve from the app secret blob when the environment is unset."""
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:1:secret:app")
    monkeypatch.setattr(
        "app.core.secrets.fetch_app_secrets",
        lambda *args, **kwargs: {
            "SECRET_KEY": "unused-here",
            "OAUTH_GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
            "OAUTH_GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
        },
    )

    assert build_oauth_client_secrets(app_settings) == {
        "google": GOOGLE_CLIENT_SECRET,
        "github": GITHUB_CLIENT_SECRET,
    }


def test_a_missing_key_is_omitted_rather_than_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing key is omitted, since an empty string would advertise a provider that cannot exchange."""
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:1:secret:app")
    monkeypatch.setattr(
        "app.core.secrets.fetch_app_secrets",
        lambda *args, **kwargs: {
            "OAUTH_GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
            "OAUTH_GITHUB_CLIENT_SECRET": "",
        },
    )

    assert build_oauth_client_secrets(app_settings) == {"google": GOOGLE_CLIENT_SECRET}


def test_no_app_secret_is_an_empty_mapping_and_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No app secret yields an empty mapping rather than a cold start failure."""
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("APP_SECRETS_ARN", raising=False)
    monkeypatch.setattr(app_settings, "APP_SECRETS_ARN", "")

    assert build_oauth_client_secrets(app_settings) == {}


def test_the_client_secrets_are_not_settings_fields(oauth_on: None) -> None:
    """Neither client secret is a settings field, so neither appears in a repr or a validation error."""
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert not hasattr(identity_settings, "google_client_secret")
    assert not hasattr(identity_settings, "github_client_secret")
    assert GOOGLE_CLIENT_SECRET not in repr(identity_settings)
    assert GITHUB_CLIENT_SECRET not in repr(identity_settings)

    assert identity_settings.google_client_id == GOOGLE_CLIENT_ID
    assert identity_settings.github_client_id == GITHUB_CLIENT_ID


def test_the_redirect_uri_is_the_issuer_callback(oauth_on: None) -> None:
    """The single allowed redirect URI is the issuer callback, compared by exact equality."""
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.oauth_redirect_uris == ["https://api.staging.carmodpicker.com/api/auth/oauth/callback"]


def test_the_refresh_window_is_thirty_days_rolling(identity_env: None) -> None:
    """The refresh window is thirty days rolling with a ninety day absolute cap."""
    from datetime import timedelta

    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.refresh_token_ttl == timedelta(days=30)
    assert identity_settings.refresh_absolute_ttl == timedelta(days=90)
    assert identity_settings.refresh_absolute_ttl >= identity_settings.refresh_token_ttl


def _user(**overrides: Any) -> User:
    """A user with no sign-in method at all, so each test adds exactly one."""
    base: dict[str, Any] = {
        "username": f"user{uuid4().hex[:8]}",
        "email": f"{uuid4().hex[:8]}@example.com",
        "email_verified": True,
        "disabled": False,
        "is_superuser": False,
        "is_admin": False,
        "is_service_account": False,
    }
    base.update(overrides)
    return User(**base)


@pytest.fixture
def package_stores() -> tuple[Any, Any]:
    """The package's in-memory passkey and OAuth link stores, which implement the same ABCs."""
    from webbpulse.identity.oauth import InMemoryOAuthLinkStore
    from webbpulse.identity.storage import InMemoryPasskeyStore

    return InMemoryPasskeyStore(), InMemoryOAuthLinkStore()


@pytest.fixture
def hooks_with_package_stores(dynamo_tables: Any, package_stores: tuple[Any, Any]) -> CarModPickerIdentityHooks:
    """Hooks over the real legacy repositories plus the two package stores."""
    passkeys, links = package_stores
    return CarModPickerIdentityHooks(
        package_passkeys=passkeys,
        package_oauth_links=links,
    )


def test_a_package_passkey_counts(
    hooks_with_package_stores: CarModPickerIdentityHooks,
    package_stores: tuple[Any, Any],
    dynamo_tables: Any,
) -> None:
    """A package passkey counts as another way in, which the package's own unlink cannot see."""
    from webbpulse.identity.storage import PasskeyRecord

    passkeys, _ = package_stores
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is False

    passkeys.put(
        PasskeyRecord(
            user_id=str(created.id),
            credential_id="Y3JlZGVudGlhbA",
            public_key="cHVibGlja2V5",
            name="Phone",
        )
    )

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is True


def test_a_package_oauth_link_counts(
    hooks_with_package_stores: CarModPickerIdentityHooks,
    package_stores: tuple[Any, Any],
    dynamo_tables: Any,
) -> None:
    """A package OAuth link counts, a deliberate double count that errs toward refusing an unlink."""
    from webbpulse.identity.oauth import OAuthLinkRecord

    _, links = package_stores
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    links.put(
        OAuthLinkRecord(
            provider_subject="google:12345",
            provider="google",
            subject="12345",
            user_id=str(created.id),
            linked_at="2026-09-10T00:00:00Z",
        )
    )

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is True


def test_a_package_totp_factor_still_does_not_count(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """A second factor is never counted, since it cannot sign a user in on its own."""
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is False
    assert not hasattr(hooks_with_package_stores, "_package_totp_factors")


def test_absent_package_stores_read_as_no_rows(dynamo_tables: Any) -> None:
    """Hooks built without the package stores still answer, treating absent stores as no rows."""
    hooks = CarModPickerIdentityHooks()
    user = _user()
    created = hooks._users.create_user(user)

    assert hooks.has_other_sign_in_method(str(created.id)) is False


def test_a_legacy_password_no_longer_counts_with_the_package_stores_present(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """Row 9's two additions are unchanged by row 13 removing the password source.

    This asserted the opposite through row 12: `users.hashed_password` was one of
    row 5's three legacy sources, and the cheapest of the three, so it was the
    one checked here to say the legacy half of a short-circuiting chain still
    answered after row 9 added to the end of it.

    Row 13 removed the password check from `has_other_sign_in_method`. Every
    password that could be migrated moved into the package's `credentials` table
    in row 7, and `OAuthService.unlink` counts that row itself, so counting a
    stale attribute here would double count the credential and refuse
    legitimate unlinks. The assertion is inverted rather than deleted, because
    what it now protects is that removing the source did not also disturb the two
    stores row 9 added: the passkey and link tests either side of this one are
    the other half of that statement.
    """
    created = hooks_with_package_stores._users.create_user(_user())

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is False


def test_an_unparseable_subject_still_answers_false(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """An unresolvable subject answers False without querying either package store."""
    assert hooks_with_package_stores.has_other_sign_in_method("not-a-uuid") is False


def test_the_hooks_receive_the_same_store_objects_the_package_does(
    everything_app: Any,
) -> None:
    """The hooks and the package share one construction of each store, by identity."""
    from app.composition.identity import build_router
    from app.core.config import settings as app_settings

    captured: dict[str, Any] = {}

    import webbpulse.identity as package

    original = package.build_identity_router

    def capture(settings: Any, hooks: Any, stores: Any, **kwargs: Any) -> Any:
        """Record the hooks and stores passed to the router, then build it as usual."""
        captured["hooks"] = hooks
        captured["stores"] = stores
        return original(settings, hooks, stores, **kwargs)

    package.build_identity_router = capture  # type: ignore[assignment]
    try:
        build_router(app_settings)
    finally:
        package.build_identity_router = original  # type: ignore[assignment]

    hooks = captured["hooks"]
    stores = captured["stores"]

    assert hooks._package_passkeys is stores.passkeys
    assert hooks._package_oauth_links is stores.oauth_links


def test_the_four_new_stores_are_supplied_unconditionally(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All four package stores are supplied even with every switch off."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    from app.composition.identity import build_router
    from app.core.config import settings as app_settings

    captured: dict[str, Any] = {}

    import boto3

    monkeypatch.setattr(
        boto3,
        "client",
        lambda service, *a, **k: FakeKms(private_key) if service == "kms" else object(),
    )

    import webbpulse.identity as package

    original = package.build_identity_router

    def capture(settings: Any, hooks: Any, stores: Any, **kwargs: Any) -> Any:
        """Record the stores passed to the router, then build it as usual."""
        captured["stores"] = stores
        return original(settings, hooks, stores, **kwargs)

    package.build_identity_router = capture  # type: ignore[assignment]
    try:
        build_router(app_settings)
    finally:
        package.build_identity_router = original  # type: ignore[assignment]

    stores = captured["stores"]
    assert stores.passkeys is not None
    assert stores.webauthn_challenges is not None
    assert stores.oauth_states is not None
    assert stores.oauth_links is not None
