"""Tests for the Chrome extension sign in handoff on the identity function.

Covers who may ask for a code, which extension may receive one, and what may be spent.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import pytest

from .entrypoints.test_route_split import _pairs
from .test_identity_row5 import AUDIENCE, ISSUER, KEY_ARN, FakeKms
from .test_identity_row5 import identity_env as _identity_env
from .test_identity_row5 import private_key as _private_key

identity_env = _identity_env
private_key = _private_key

STAGING_EXTENSION_ID = "dbglgmnnfandmnacdpibkfggkadjikkg"

OTHER_EXTENSION_ID = "aaaabbbbccccddddeeeeffffgggghhhh"

EXTENSION_PATHS = (
    ("POST", "/api/auth/extension/handoff"),
    ("POST", "/api/auth/extension/token"),
)


@pytest.fixture
def extension_env(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The identity environment plus the extension allowlist variable."""
    monkeypatch.setenv("CHROME_EXTENSION_IDS", STAGING_EXTENSION_ID)


@pytest.fixture
def extension_app(extension_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with the extension allowlist set and boto3 faked."""
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        """Return a local KMS signer or a stub SES client and refuse any other service."""
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"an unexpected client was requested: {service}")

    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


@pytest.fixture
def client(extension_app: Any) -> Iterator[Any]:
    """A test client over the extension enabled identity application."""
    from fastapi.testclient import TestClient

    with TestClient(extension_app) as test_client:
        yield test_client


def _sign(private_key: Any, claims: dict[str, Any]) -> str:
    """Sign claims through the router's own signer, so the token is indistinguishable from a minted one."""
    from webbpulse.identity import KmsSigner

    return KmsSigner(FakeKms(private_key), KEY_ARN).encode(claims)


def _access_token(private_key: Any, subject: str = "user-1") -> str:
    """A valid access token for `subject`, with this deployment's audience."""
    issued_at = int(time.time())
    return _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": subject,
            "aud": AUDIENCE,
            "iat": issued_at,
            "exp": issued_at + 600,
            "typ": "access",
        },
    )


def _redirect_uri(extension_id: str = STAGING_EXTENSION_ID) -> str:
    """Build a chrome-extension redirect URI for the given extension id."""
    return f"chrome-extension://{extension_id}/handoff.html"


def test_both_routes_mount_on_the_identity_function(extension_app: Any) -> None:
    """Both handoff routes mount on the identity function."""
    served = _pairs(extension_app)
    missing = [pair for pair in EXTENSION_PATHS if pair not in served]
    assert missing == []


def test_every_route_is_under_the_existing_proxy_route_key(extension_app: Any) -> None:
    """Both paths stay under the existing proxy route key, so no gateway change is needed."""
    served = {path for method, path in _pairs(extension_app) if (method, path) in EXTENSION_PATHS}
    assert served
    assert all(path.startswith("/api/auth/") for path in served)


def test_the_routes_are_absent_without_an_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an issuer configured neither route mounts."""
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", "")
    from app.entrypoints.identity import build_app

    served = {path for _, path in _pairs(build_app())}
    assert "/api/auth/extension/handoff" not in served
    assert "/api/auth/extension/token" not in served


def test_a_code_needs_a_signed_in_caller(client: Any) -> None:
    """Requesting a code without a session is refused."""
    response = client.post(
        "/api/auth/extension/handoff",
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "NOT_AUTHENTICATED"


def test_an_unverifiable_bearer_token_is_simply_not_signed_in(client: Any) -> None:
    """An unverifiable token gets the same 401 as none, with no hint why."""
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": "Bearer not-a-token"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "NOT_AUTHENTICATED"


def test_a_signed_in_caller_gets_a_code(client: Any, private_key: Any) -> None:
    """A signed in caller naming a trusted extension gets a handoff code."""
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("code"), str)
    assert body["code"]
    assert set(body) == {"code"}


@pytest.mark.parametrize(
    "redirect_uri",
    [
        pytest.param(f"https://{STAGING_EXTENSION_ID}/handoff.html", id="https-scheme"),
        pytest.param(f"chrome-extension://{OTHER_EXTENSION_ID}/x.html", id="unlisted-id"),
        pytest.param("chrome-extension:///handoff.html", id="no-host"),
        pytest.param("not a url at all", id="unparseable"),
        pytest.param(f"moz-extension://{STAGING_EXTENSION_ID}/x", id="other-extension-scheme"),
    ],
)
def test_a_redirect_target_we_do_not_trust_is_refused(client: Any, private_key: Any, redirect_uri: str) -> None:
    """Every untrusted redirect target, scheme or id, is refused."""
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": redirect_uri},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "EXTENSION_NOT_ALLOWED"


def test_an_unset_allowlist_still_serves_the_store_build(
    client: Any, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset allowlist means the published store id, matching what CORS allows."""
    monkeypatch.delenv("CHROME_EXTENSION_IDS", raising=False)
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 200


def test_an_explicitly_empty_allowlist_trusts_nothing(
    client: Any, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicitly empty allowlist trusts no extension, unlike an unset one."""
    monkeypatch.setenv("CHROME_EXTENSION_IDS", "")
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "EXTENSION_NOT_ALLOWED"


def test_the_allowlist_parses_the_comma_separated_form_terraform_renders() -> None:
    """Several ids, whitespace and empty entries, the way a variable arrives."""
    from app.composition.identity_extension import allowed_extension_ids

    parsed = allowed_extension_ids({"CHROME_EXTENSION_IDS": f" {STAGING_EXTENSION_ID} ,,{OTHER_EXTENSION_ID}"})
    assert parsed == [STAGING_EXTENSION_ID, OTHER_EXTENSION_ID]
    assert allowed_extension_ids({"CHROME_EXTENSION_IDS": ""}) == []

    assert allowed_extension_ids({}) == [STAGING_EXTENSION_ID]

    assert allowed_extension_ids({"CHROME_EXTENSION_IDS": f"chrome-extension://{STAGING_EXTENSION_ID}"}) == [
        STAGING_EXTENSION_ID
    ]


def test_the_default_matches_the_settings_field_it_shadows() -> None:
    """The module's duplicated default store id matches the settings field."""
    from app.composition.identity_extension import DEFAULT_EXTENSION_ID
    from app.core.config import Settings

    field = Settings.model_fields["CHROME_EXTENSION_IDS"]
    assert field.default == DEFAULT_EXTENSION_ID
    assert DEFAULT_EXTENSION_ID == STAGING_EXTENSION_ID


def test_a_code_round_trips_to_an_access_token(client: Any, private_key: Any) -> None:
    """A code round trips to an access token carrying the same subject."""
    issued = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key, 'user-42')}"},
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert issued.status_code == 200

    exchanged = client.post(
        "/api/auth/extension/token",
        json={"code": issued.json()["code"]},
    )
    assert exchanged.status_code == 200
    body = exchanged.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0

    from webbpulse.identity import TokenService

    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    tokens = TokenService(build_identity_settings(app_settings), FakeKms(private_key))
    claims = tokens.verify_access_token(body["access_token"])
    assert claims["sub"] == "user-42"
    assert claims["typ"] == "access"


def test_an_access_token_cannot_be_exchanged_for_another(client: Any, private_key: Any) -> None:
    """An access token cannot be spent at the exchange for a fresh one."""
    response = client.post(
        "/api/auth/extension/token",
        json={"code": _access_token(private_key)},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_a_code_with_the_wrong_typ_is_refused(client: Any, private_key: Any) -> None:
    """A token with the right audience but the wrong typ is refused."""
    issued_at = int(time.time())
    forged = _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "something_else",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": forged})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_an_expired_code_is_refused(client: Any, private_key: Any) -> None:
    """A code minted outside the validity window is refused."""
    issued_at = int(time.time()) - 3600
    stale = _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "extension_handoff",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": stale})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_a_code_signed_by_another_key_is_refused(client: Any) -> None:
    """A correctly shaped code signed by an unknown key is refused."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issued_at = int(time.time())
    forged = _sign(
        other_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "extension_handoff",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": forged})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_the_exchange_needs_no_bearer_token(client: Any, private_key: Any) -> None:
    """The code is the credential, so the exchange requires no bearer token."""
    issued = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    response = client.post("/api/auth/extension/token", json={"code": issued.json()["code"]})
    assert response.status_code == 200


def test_the_parser_agrees_with_the_frontends_validation() -> None:
    """The redirect parser accepts and refuses the same targets the frontend does."""
    from app.composition.identity_extension import extension_id_for

    allowed = [STAGING_EXTENSION_ID]
    assert extension_id_for(_redirect_uri(), allowed) == STAGING_EXTENSION_ID
    assert extension_id_for(f"chrome-extension://{OTHER_EXTENSION_ID}/x", allowed) is None
    assert extension_id_for(f"https://{STAGING_EXTENSION_ID}/x", allowed) is None
    assert extension_id_for("", allowed) is None
    assert extension_id_for(_redirect_uri(), []) is None
