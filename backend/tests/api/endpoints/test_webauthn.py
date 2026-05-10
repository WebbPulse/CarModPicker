"""Tests for WebAuthn (passkey) endpoints.

Real WebAuthn verification requires a signed attestation/assertion from an
authenticator, which we can't produce cheaply in a unit test. We mock the two
`verify_*` entry points from py_webauthn and focus on:

- Options generation returns the spec-shaped payload + a challenge token.
- Verify endpoints persist/update credentials and mint tokens on success.
- Challenge tokens are purpose-scoped (a register token can't be used to log in).
- Replay rejection: once sign_count decreases, InvalidAuthenticationResponse
  is raised inside py_webauthn — we simulate it.
- list/rename/delete ownership checks.
- Unauthenticated requests are rejected where appropriate.
"""

import base64
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.core.config import settings


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _create_user(db: Session, username: str, password: str = "testpassword") -> DBUser:
    user = DBUser(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        email_verified=True,
        disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, username: str, password: str = "testpassword") -> str:
    resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_register_options_requires_auth(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/register/options",
        json={"nickname": "my key"},
    )
    assert resp.status_code == 401


def test_register_options_returns_challenge_and_options(client: TestClient, db_session: Session) -> None:
    username = _unique("passkey_opts_user")
    _create_user(db_session, username)
    token = _login(client, username)

    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/register/options",
        headers=_auth_headers(token),
        json={"nickname": "YubiKey"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "challenge_token" in body
    assert "options" in body
    opts = body["options"]
    assert opts["rp"]["id"] == settings.webauthn_rp_id
    assert opts["user"]["name"] == username
    assert "challenge" in opts


def test_register_verify_persists_credential(client: TestClient, db_session: Session) -> None:
    username = _unique("passkey_reg_verify")
    user = _create_user(db_session, username)
    token = _login(client, username)

    opts_resp = client.post(
        f"{settings.API_STR}/auth/webauthn/register/options",
        headers=_auth_headers(token),
        json={"nickname": "original"},
    )
    challenge_token = opts_resp.json()["challenge_token"]

    fake_cred_id = b"fake-credential-id-bytes-0000"
    fake_pubkey = b"fake-pubkey-cbor-bytes"
    verified = SimpleNamespace(
        credential_id=fake_cred_id,
        credential_public_key=fake_pubkey,
        sign_count=0,
        aaguid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        credential_backed_up=True,
    )

    with patch(
        "app.api.endpoints.auth.webauthn.verify_registration_response",
        return_value=verified,
    ):
        resp = client.post(
            f"{settings.API_STR}/auth/webauthn/register/verify",
            headers=_auth_headers(token),
            json={
                "challenge_token": challenge_token,
                "credential": {
                    "id": _b64url(fake_cred_id),
                    "rawId": _b64url(fake_cred_id),
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "xxx",
                        "attestationObject": "yyy",
                        "transports": ["usb", "nfc"],
                    },
                },
                "nickname": "YubiKey 5C",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nickname"] == "YubiKey 5C"
    assert body["aaguid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert body["transports"] == ["usb", "nfc"]

    stored = db_session.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).one()
    assert stored.credential_id == fake_cred_id
    assert stored.public_key == fake_pubkey
    assert stored.sign_count == 0


def test_register_verify_rejects_wrong_purpose_token(client: TestClient, db_session: Session) -> None:
    """A login challenge token must not be usable for registration."""
    username = _unique("passkey_purpose_check")
    _create_user(db_session, username)
    token = _login(client, username)

    login_opts = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={"username": username},
    )
    assert login_opts.status_code == 200
    login_challenge_token = login_opts.json()["challenge_token"]

    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/register/verify",
        headers=_auth_headers(token),
        json={
            "challenge_token": login_challenge_token,
            "credential": {"id": "x", "type": "public-key", "response": {}},
            "nickname": "nope",
        },
    )
    assert resp.status_code == 400


def test_login_options_discoverable_has_no_allow_credentials(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={},
    )
    assert resp.status_code == 200, resp.text
    opts = resp.json()["options"]
    assert opts.get("allowCredentials") in (None, [])


def test_login_verify_issues_token(client: TestClient, db_session: Session) -> None:
    username = _unique("passkey_login_verify")
    user = _create_user(db_session, username)

    fake_cred_id = b"login-credential-id-1234567890ab"
    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=fake_cred_id,
        public_key=b"pub",
        sign_count=5,
        transports=["internal"],
        aaguid=None,
        nickname="Built-in",
    )
    db_session.add(cred)
    db_session.commit()

    opts_resp = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={"username": username},
    )
    challenge_token = opts_resp.json()["challenge_token"]

    verified = SimpleNamespace(
        new_sign_count=6,
        credential_id=fake_cred_id,
        credential_backed_up=False,
        credential_device_type="single_device",
        user_verified=True,
    )
    with patch(
        "app.api.endpoints.auth.webauthn.verify_authentication_response",
        return_value=verified,
    ):
        resp = client.post(
            f"{settings.API_STR}/auth/webauthn/login/verify",
            json={
                "challenge_token": challenge_token,
                "credential": {
                    "id": _b64url(fake_cred_id),
                    "rawId": _b64url(fake_cred_id),
                    "type": "public-key",
                    "response": {"clientDataJSON": "x", "authenticatorData": "y", "signature": "z"},
                },
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["user"]["username"] == username

    db_session.refresh(cred)
    assert cred.sign_count == 6
    assert cred.last_used_at is not None


def test_login_verify_replay_rejected(client: TestClient, db_session: Session) -> None:
    """If py_webauthn raises InvalidAuthenticationResponse (e.g. sign_count replay), we 401."""
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    username = _unique("passkey_replay")
    user = _create_user(db_session, username)

    fake_cred_id = b"replay-credential-id-0000000000ab"
    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=fake_cred_id,
        public_key=b"pub",
        sign_count=100,
        transports=None,
        aaguid=None,
        nickname="Key",
    )
    db_session.add(cred)
    db_session.commit()

    opts_resp = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={"username": username},
    )
    challenge_token = opts_resp.json()["challenge_token"]

    with patch(
        "app.api.endpoints.auth.webauthn.verify_authentication_response",
        side_effect=InvalidAuthenticationResponse("sign_count went backwards"),
    ):
        resp = client.post(
            f"{settings.API_STR}/auth/webauthn/login/verify",
            json={
                "challenge_token": challenge_token,
                "credential": {
                    "id": _b64url(fake_cred_id),
                    "type": "public-key",
                    "response": {"clientDataJSON": "x"},
                },
            },
        )
    assert resp.status_code == 401


def test_login_verify_unknown_credential(client: TestClient) -> None:
    opts_resp = client.post(f"{settings.API_STR}/auth/webauthn/login/options", json={})
    challenge_token = opts_resp.json()["challenge_token"]

    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/login/verify",
        json={
            "challenge_token": challenge_token,
            "credential": {
                "id": _b64url(b"never-registered-id-00000000"),
                "type": "public-key",
                "response": {"clientDataJSON": "x"},
            },
        },
    )
    assert resp.status_code == 401


def test_list_rename_delete_flow(client: TestClient, db_session: Session) -> None:
    username = _unique("passkey_crud")
    user = _create_user(db_session, username)
    token = _login(client, username)

    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=b"crud-cred-id-x",
        public_key=b"pub",
        sign_count=0,
        nickname="old name",
    )
    db_session.add(cred)
    db_session.commit()
    db_session.refresh(cred)

    # list
    resp = client.get(
        f"{settings.API_STR}/auth/webauthn/credentials",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["nickname"] == "old name"

    # rename
    resp = client.patch(
        f"{settings.API_STR}/auth/webauthn/credentials/{cred.id}",
        headers=_auth_headers(token),
        json={"nickname": "new name"},
    )
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "new name"

    # delete
    resp = client.delete(
        f"{settings.API_STR}/auth/webauthn/credentials/{cred.id}",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200

    resp = client.get(
        f"{settings.API_STR}/auth/webauthn/credentials",
        headers=_auth_headers(token),
    )
    assert resp.json() == []


def test_cannot_rename_other_users_credential(client: TestClient, db_session: Session) -> None:
    owner = _create_user(db_session, _unique("passkey_owner"))
    other = _create_user(db_session, _unique("passkey_other"))

    cred = WebAuthnCredential(
        user_id=owner.id,
        credential_id=b"isolation-cred-id",
        public_key=b"pub",
        sign_count=0,
        nickname="owner's key",
    )
    db_session.add(cred)
    db_session.commit()
    db_session.refresh(cred)

    other_token = _login(client, other.username)
    resp = client.patch(
        f"{settings.API_STR}/auth/webauthn/credentials/{cred.id}",
        headers=_auth_headers(other_token),
        json={"nickname": "stolen"},
    )
    assert resp.status_code == 404


def test_list_credentials_requires_auth(client: TestClient) -> None:
    resp = client.get(f"{settings.API_STR}/auth/webauthn/credentials")
    assert resp.status_code == 401


def test_register_rejects_empty_nickname(client: TestClient, db_session: Session) -> None:
    username = _unique("passkey_empty_nick")
    _create_user(db_session, username)
    token = _login(client, username)

    resp = client.post(
        f"{settings.API_STR}/auth/webauthn/register/options",
        headers=_auth_headers(token),
        json={"nickname": "   "},
    )
    assert resp.status_code == 400


def test_login_verify_rejects_unverified_user(client: TestClient, db_session: Session) -> None:
    """An unverified user can't acquire a session via a passkey, even if signature verification
    would succeed. Matches the email_verified gate in get_current_user."""
    username = _unique("passkey_unverified")
    user = _create_user(db_session, username)
    user.email_verified = False
    db_session.commit()

    fake_cred_id = b"unverified-cred-id-123456789012"
    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=fake_cred_id,
        public_key=b"pub",
        sign_count=0,
        transports=None,
        aaguid=None,
        nickname="Key",
    )
    db_session.add(cred)
    db_session.commit()

    opts_resp = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={"username": username},
    )
    challenge_token = opts_resp.json()["challenge_token"]

    verified = SimpleNamespace(
        new_sign_count=1,
        credential_id=fake_cred_id,
        credential_backed_up=False,
        credential_device_type="single_device",
        user_verified=True,
    )
    with patch(
        "app.api.endpoints.auth.webauthn.verify_authentication_response",
        return_value=verified,
    ):
        resp = client.post(
            f"{settings.API_STR}/auth/webauthn/login/verify",
            json={
                "challenge_token": challenge_token,
                "credential": {
                    "id": _b64url(fake_cred_id),
                    "type": "public-key",
                    "response": {"clientDataJSON": "x", "authenticatorData": "y", "signature": "z"},
                },
            },
        )
    assert resp.status_code == 401, resp.text
    assert "email not verified" in resp.json()["message"].lower()

    db_session.refresh(cred)
    # sign_count must not advance when the login is rejected.
    assert cred.sign_count == 0
