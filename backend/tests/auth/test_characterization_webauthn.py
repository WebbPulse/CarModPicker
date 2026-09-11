"""Characterization of WebAuthn passkey registration and authentication.

The webauthn library is stubbed at the import boundary, since CI has no authenticator.
"""

import base64
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository, WebAuthnCredential, WebAuthnCredentialRepository


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _b64url(raw: bytes) -> str:
    """Unpadded base64url encoding of raw bytes."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _create_verified_user(db: Any) -> DBUser:
    """Create a verified, enabled user with a known password."""
    username = _uniq("wa_char")
    user = DBUser(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("testpass123!"),
        email_verified=True,
        disabled=False,
    )
    return UserRepository().create_user(user)


def _login(client: TestClient, user: DBUser) -> str:
    """Log the user in with their password and return the access token."""
    r = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": user.username, "password": "testpass123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@patch("app.api.endpoints.auth.webauthn.verify_authentication_response")
@patch("app.api.endpoints.auth.webauthn.generate_authentication_options")
@patch("app.api.endpoints.auth.webauthn.verify_registration_response")
@patch("app.api.endpoints.auth.webauthn.generate_registration_options")
def test_webauthn_register_and_authenticate(
    mock_gen_reg: Any,
    mock_ver_reg: Any,
    mock_gen_auth: Any,
    mock_ver_auth: Any,
    client: TestClient,
    db_session: Any,
) -> None:
    """A passkey registers and then authenticates through the full round trip."""
    user = _create_verified_user(db_session)
    token = _login(client, user)
    headers = {"Authorization": f"Bearer {token}"}

    fake_challenge = b"fake_challenge_bytes_0000_012345"
    import json

    import webauthn
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    real_options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user.id.bytes,
        user_name=user.username,
        user_display_name=user.username,
        challenge=fake_challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    mock_gen_reg.return_value = real_options

    r1 = client.post(
        f"{settings.API_STR}/auth/webauthn/register/options",
        headers=headers,
        json={"nickname": "CharKey"},
    )
    assert r1.status_code == 200, r1.text
    r1_body = r1.json()
    assert "challenge_token" in r1_body
    assert "options" in r1_body
    challenge_token = r1_body["challenge_token"]

    fake_cred_id = b"char-cred-id-bytes-0000"
    fake_pubkey = b"char-pubkey-cbor-bytes"
    mock_ver_reg.return_value = SimpleNamespace(
        credential_id=fake_cred_id,
        credential_public_key=fake_pubkey,
        sign_count=0,
        aaguid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        credential_backed_up=False,
    )
    r2 = client.post(
        f"{settings.API_STR}/auth/webauthn/register/verify",
        headers=headers,
        json={
            "challenge_token": challenge_token,
            "credential": {
                "id": _b64url(fake_cred_id),
                "rawId": _b64url(fake_cred_id),
                "type": "public-key",
                "response": {
                    "clientDataJSON": "xxx",
                    "attestationObject": "yyy",
                },
            },
            "nickname": "CharKey",
        },
    )
    assert r2.status_code == 200, r2.text

    creds = WebAuthnCredentialRepository().list_by_user(user.id)
    assert len(creds) == 1
    assert creds[0].credential_id == fake_cred_id
    assert creds[0].public_key == fake_pubkey

    fake_auth_challenge = b"fake_auth_challenge_bytes_01234"
    real_auth_options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=fake_auth_challenge,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    mock_gen_auth.return_value = real_auth_options

    r3 = client.post(
        f"{settings.API_STR}/auth/webauthn/login/options",
        json={"username": user.username},
    )
    assert r3.status_code == 200, r3.text
    login_challenge_token = r3.json()["challenge_token"]

    mock_ver_auth.return_value = SimpleNamespace(new_sign_count=1)
    r4 = client.post(
        f"{settings.API_STR}/auth/webauthn/login/verify",
        json={
            "challenge_token": login_challenge_token,
            "credential": {
                "id": _b64url(fake_cred_id),
                "rawId": _b64url(fake_cred_id),
                "type": "public-key",
                "response": {
                    "clientDataJSON": "xxx",
                    "authenticatorData": "yyy",
                    "signature": "zzz",
                },
            },
        },
    )
    assert r4.status_code == 200, r4.text
    r4_body = r4.json()
    assert "access_token" in r4_body
    assert r4_body.get("token_type") == "bearer"
