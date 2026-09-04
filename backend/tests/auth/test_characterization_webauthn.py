"""SAFE-06 flow 4: WebAuthn passkey registration + authentication.

Per D-18 the cryptographic boundary is stubbed at the `webauthn` library
boundary — NOT over HTTP. Real attestation signing requires a hardware
authenticator we cannot cheaply reproduce in CI.

The four library functions patched at the `app.api.endpoints.auth` import
boundary (T-06-06 mitigation — pin the exact import targets so a Phase-5
refactor that moves the imports will be caught by these patches failing):

  @patch("app.api.endpoints.auth.webauthn.generate_registration_options")
  @patch("app.api.endpoints.auth.webauthn.verify_registration_response")
  @patch("app.api.endpoints.auth.webauthn.generate_authentication_options")
  @patch("app.api.endpoints.auth.webauthn.verify_authentication_response")

Note: generate_* functions do not hit external HTTP (local PRNG only), but
we pin them here so that a future refactor breaking the import path causes an
explicit test failure rather than a silent stub miss.
"""

import base64
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository, WebAuthnCredential, WebAuthnCredentialRepository


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _create_verified_user(db: Session) -> DBUser:
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
    db_session: Session,
) -> None:
    """Flow 4: WebAuthn registration round-trip then authentication round-trip.

    Patch decorator order (outermost first, args innermost-first):
      @patch verify_authentication_response → mock_ver_auth (last arg)
      @patch generate_authentication_options → mock_gen_auth
      @patch verify_registration_response   → mock_ver_reg
      @patch generate_registration_options  → mock_gen_reg (first arg)
    """
    user = _create_verified_user(db_session)
    token = _login(client, user)
    headers = {"Authorization": f"Bearer {token}"}

    # ---- Registration: step 1 — request options ----
    fake_challenge = b"fake_challenge_bytes_0000_012345"
    # generate_registration_options must return an object that options_to_json accepts.
    # Use the real webauthn library to produce a proper options object, then swap in
    # our fake challenge by delegating to the real function via the mock side_effect.
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

    # ---- Registration: step 2 — submit credential (verify stubbed) ----
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

    # DB state: credential row exists for this user
    creds = WebAuthnCredentialRepository().list_by_user(user.id)
    assert len(creds) == 1
    assert creds[0].credential_id == fake_cred_id
    assert creds[0].public_key == fake_pubkey

    # ---- Authentication: step 1 — request challenge ----
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

    # ---- Authentication: step 2 — submit assertion (verify stubbed) ----
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
